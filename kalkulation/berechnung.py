"""Kostenberechnung für Einkaufsartikel, Rezepte und Endprodukte."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal

from kalkulation.einheiten import EinheitenFehler, Gruppe, basiseinheit, gruppe, in_basis
from kalkulation.modelle import Artikel, Endprodukt, Kategorie, Rezept, RezeptPosition, VerpackungsPosition


class ZirkelbezugFehler(ValueError):
    pass


class ReferenzFehler(ValueError):
    pass


def preis_pro_basiseinheit(artikel: Artikel) -> Decimal:
    return artikel.gebinde_preis / in_basis(artikel.gebinde_menge, artikel.gebinde_einheit)


def mengen_summe(positionen: Iterable[RezeptPosition]) -> tuple[Decimal, Gruppe] | None:
    """Summe der Positionsmengen in Basiseinheit als Ausbeute-Vorschlag.

    Gibt None zurück, wenn es keine Positionen gibt oder sie zu verschiedenen Einheitengruppen gehören.
    """
    positionen = list(positionen)
    gruppen = {gruppe(p.einheit) for p in positionen}
    if len(gruppen) != 1:
        return None
    return sum((in_basis(p.menge, p.einheit) for p in positionen), Decimal(0)), gruppen.pop()


@dataclass(frozen=True)
class PositionsKosten:
    position: RezeptPosition
    name: str
    kosten: Decimal


@dataclass(frozen=True)
class RezeptKalkulation:
    rezept: Rezept
    positionen: tuple[PositionsKosten, ...]
    chargenkosten: Decimal
    preis_pro_basiseinheit: Decimal

    @property
    def basiseinheit(self) -> str:
        return basiseinheit(self.rezept.ausbeute_einheit)


@dataclass(frozen=True)
class VerpackungsKosten:
    position: VerpackungsPosition
    name: str
    kosten: Decimal


@dataclass(frozen=True)
class EndproduktKalkulation:
    endprodukt: Endprodukt
    rezept: RezeptKalkulation
    inhaltskosten: Decimal
    verpackung: tuple[VerpackungsKosten, ...]

    @property
    def verpackungskosten(self) -> Decimal:
        return sum((v.kosten for v in self.verpackung), Decimal(0))

    @property
    def herstellkosten(self) -> Decimal:
        return self.inhaltskosten + self.verpackungskosten


@dataclass
class Bedarf:
    """Benötigte Mengen in Basiseinheit: Einkaufsartikel und herzustellende Rezepte (inkl. Zwischenprodukte)."""

    artikel: dict[int, Decimal] = field(default_factory=dict)
    rezepte: dict[int, Decimal] = field(default_factory=dict)


def _addiere(ziel: dict[int, Decimal], schluessel: int, menge: Decimal) -> None:
    ziel[schluessel] = ziel.get(schluessel, Decimal(0)) + menge


@dataclass(frozen=True)
class EinkaufsPosition:
    artikel: Artikel
    menge_basis: Decimal

    @property
    def gebinde_anzahl(self) -> int:
        verhaeltnis = self.menge_basis / in_basis(self.artikel.gebinde_menge, self.artikel.gebinde_einheit)
        # Vorher runden, damit Rechenreste wie 2,0000000000000000001 nicht ein ganzes Gebinde mehr ergeben
        return int(verhaeltnis.quantize(Decimal("1e-9")).to_integral_value(rounding=ROUND_CEILING))

    @property
    def einkaufskosten(self) -> Decimal:
        return self.gebinde_anzahl * self.artikel.gebinde_preis

    @property
    def verbrauchskosten(self) -> Decimal:
        return self.menge_basis * preis_pro_basiseinheit(self.artikel)


class Kalkulator:
    """Berechnet Kosten auf Basis einer Momentaufnahme aller Artikel und Rezepte.

    Bei geänderten Daten einen neuen Kalkulator erzeugen (Ergebnisse werden zwischengespeichert).
    """

    def __init__(self, artikel: Iterable[Artikel], rezepte: Iterable[Rezept]) -> None:
        self._artikel = {a.id: a for a in artikel}
        self._rezepte = {r.id: r for r in rezepte}
        self._cache: dict[int, RezeptKalkulation] = {}

    def rezept(self, rezept_id: int) -> RezeptKalkulation:
        return self._rezept(rezept_id, ())

    def endprodukt(self, endprodukt: Endprodukt) -> EndproduktKalkulation:
        rezept = self.rezept(endprodukt.rezept_id)
        ausbeute_einheit = rezept.rezept.ausbeute_einheit
        if gruppe(ausbeute_einheit) != Gruppe.VOLUMEN:
            raise EinheitenFehler(
                f"Endprodukt '{endprodukt.name}': Rezept '{rezept.rezept.name}' hat eine Ausbeute in "
                f"'{ausbeute_einheit}', abgefüllt werden kann nur ein Rezept mit Ausbeute in Volumen."
            )

        verpackung = []
        for position in endprodukt.verpackung:
            artikel = self._hole_artikel(position.artikel_id)
            if artikel.kategorie != Kategorie.VERPACKUNG:
                raise ValueError(f"Endprodukt '{endprodukt.name}': '{artikel.name}' ist keine Verpackung.")
            if gruppe(artikel.gebinde_einheit) != Gruppe.STUECK:
                raise EinheitenFehler(
                    f"Endprodukt '{endprodukt.name}': Verpackung '{artikel.name}' muss in Stk eingekauft werden."
                )
            verpackung.append(
                VerpackungsKosten(position, artikel.name, position.anzahl * preis_pro_basiseinheit(artikel))
            )

        return EndproduktKalkulation(
            endprodukt=endprodukt,
            rezept=rezept,
            inhaltskosten=endprodukt.fuellmenge_ml * rezept.preis_pro_basiseinheit,
            verpackung=tuple(verpackung),
        )

    def bedarf(
        self,
        endprodukte: Iterable[tuple[Endprodukt, Decimal]] = (),
        rezepte: Iterable[tuple[int, Decimal]] = (),
    ) -> Bedarf:
        """Hochrechnung für (Endprodukt, Anzahl Gebinde) und (Rezept-ID, Menge in Basiseinheit)."""
        bedarf = Bedarf()
        for endprodukt, anzahl in endprodukte:
            self.endprodukt(endprodukt)  # prüft Rezept und Verpackung
            self._rezept_bedarf(endprodukt.rezept_id, anzahl * endprodukt.fuellmenge_ml, bedarf)
            for position in endprodukt.verpackung:
                _addiere(bedarf.artikel, position.artikel_id, anzahl * position.anzahl)
        for rezept_id, menge in rezepte:
            self._rezept_bedarf(rezept_id, menge, bedarf)
        return bedarf

    def einkaufsliste(self, bedarf: Bedarf) -> list[EinkaufsPosition]:
        positionen = [EinkaufsPosition(self._hole_artikel(i), menge) for i, menge in bedarf.artikel.items()]
        return sorted(positionen, key=lambda p: (p.artikel.kategorie != Kategorie.ZUTAT, p.artikel.name.casefold()))

    def _rezept_bedarf(self, rezept_id: int, menge_basis: Decimal, bedarf: Bedarf) -> None:
        rezept = self.rezept(rezept_id).rezept  # prüft Einheiten und Zirkelbezüge
        _addiere(bedarf.rezepte, rezept_id, menge_basis)
        faktor = menge_basis / in_basis(rezept.ausbeute_menge, rezept.ausbeute_einheit)
        for position in rezept.positionen:
            menge = in_basis(position.menge, position.einheit) * faktor
            if position.artikel_id is not None:
                _addiere(bedarf.artikel, position.artikel_id, menge)
            else:
                self._rezept_bedarf(position.zwischenprodukt_id, menge, bedarf)

    def _rezept(self, rezept_id: int, pfad: tuple[int, ...]) -> RezeptKalkulation:
        if rezept_id in self._cache:
            return self._cache[rezept_id]
        rezept = self._hole_rezept(rezept_id)
        if rezept_id in pfad:
            kreis = (*pfad[pfad.index(rezept_id):], rezept_id)
            raise ZirkelbezugFehler("Zirkelbezug: " + " → ".join(self._rezepte[i].name for i in kreis))

        pfad = (*pfad, rezept_id)
        positionen = tuple(self._position(rezept, p, pfad) for p in rezept.positionen)
        chargenkosten = sum((p.kosten for p in positionen), Decimal(0))
        ergebnis = RezeptKalkulation(
            rezept=rezept,
            positionen=positionen,
            chargenkosten=chargenkosten,
            preis_pro_basiseinheit=chargenkosten / in_basis(rezept.ausbeute_menge, rezept.ausbeute_einheit),
        )
        self._cache[rezept_id] = ergebnis
        return ergebnis

    def _position(self, rezept: Rezept, position: RezeptPosition, pfad: tuple[int, ...]) -> PositionsKosten:
        if position.artikel_id is not None:
            artikel = self._hole_artikel(position.artikel_id)
            name, quell_einheit, preis = artikel.name, artikel.gebinde_einheit, preis_pro_basiseinheit(artikel)
        else:
            zwischen = self._rezept(position.zwischenprodukt_id, pfad)
            name = zwischen.rezept.name
            quell_einheit = zwischen.rezept.ausbeute_einheit
            preis = zwischen.preis_pro_basiseinheit

        if gruppe(position.einheit) != gruppe(quell_einheit):
            raise EinheitenFehler(
                f"Rezept '{rezept.name}', Position '{name}': Einheit '{position.einheit}' "
                f"({gruppe(position.einheit).value}) passt nicht zu '{quell_einheit}' "
                f"({gruppe(quell_einheit).value})."
            )
        return PositionsKosten(position, name, in_basis(position.menge, position.einheit) * preis)

    def _hole_artikel(self, artikel_id: int) -> Artikel:
        try:
            return self._artikel[artikel_id]
        except KeyError:
            raise ReferenzFehler(f"Unbekannter Artikel (ID {artikel_id}).") from None

    def _hole_rezept(self, rezept_id: int) -> Rezept:
        try:
            return self._rezepte[rezept_id]
        except KeyError:
            raise ReferenzFehler(f"Unbekanntes Rezept (ID {rezept_id}).") from None
