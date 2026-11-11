"""Datenklassen für Einkaufsartikel, Rezepte und Endprodukte (nur Eingabedaten, keine berechneten Preise)."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from kalkulation.einheiten import gruppe


class Kategorie(Enum):
    ZUTAT = "zutat"
    VERPACKUNG = "verpackung"


def _dezimal(wert: object) -> Decimal:
    if isinstance(wert, Decimal):
        ergebnis = wert
    else:
        # float über str, damit z. B. 0.1 nicht als 0.1000000000000000055… ankommt
        try:
            ergebnis = Decimal(str(wert))
        except InvalidOperation:
            raise ValueError(f"'{wert}' ist keine gültige Zahl.") from None
    if not ergebnis.is_finite():
        raise ValueError(f"'{wert}' ist keine gültige Zahl.")
    return ergebnis


def _setze_zahl(obj: object, feld: str, bezeichnung: str, *, darf_null: bool = False) -> None:
    wert = _dezimal(getattr(obj, feld))
    if wert < 0 or (wert == 0 and not darf_null):
        grenze = "mindestens 0" if darf_null else "größer als 0"
        raise ValueError(f"{bezeichnung} muss {grenze} sein (ist {wert}).")
    object.__setattr__(obj, feld, wert)


def _setze_name(obj: object) -> None:
    name = (getattr(obj, "name") or "").strip()
    if not name:
        raise ValueError("Name darf nicht leer sein.")
    object.__setattr__(obj, "name", name)


@dataclass(frozen=True)
class Artikel:
    id: int | None  # None = noch nicht gespeichert
    name: str
    kategorie: Kategorie
    gebinde_menge: Decimal
    gebinde_einheit: str
    gebinde_preis: Decimal
    lieferant: str = ""
    notiz: str = ""

    def __post_init__(self) -> None:
        _setze_name(self)
        object.__setattr__(self, "kategorie", Kategorie(self.kategorie))
        gruppe(self.gebinde_einheit)
        _setze_zahl(self, "gebinde_menge", "Gebindegröße")
        _setze_zahl(self, "gebinde_preis", "Gebindepreis", darf_null=True)


@dataclass(frozen=True)
class RezeptPosition:
    menge: Decimal
    einheit: str
    artikel_id: int | None = None
    zwischenprodukt_id: int | None = None

    def __post_init__(self) -> None:
        if (self.artikel_id is None) == (self.zwischenprodukt_id is None):
            raise ValueError("Eine Rezeptposition braucht genau einen Artikel oder ein Zwischenprodukt.")
        gruppe(self.einheit)
        _setze_zahl(self, "menge", "Menge")


@dataclass(frozen=True)
class Rezept:
    id: int | None  # None = noch nicht gespeichert
    name: str
    ausbeute_menge: Decimal
    ausbeute_einheit: str
    positionen: tuple[RezeptPosition, ...] = ()
    notiz: str = ""

    def __post_init__(self) -> None:
        _setze_name(self)
        gruppe(self.ausbeute_einheit)
        _setze_zahl(self, "ausbeute_menge", "Ausbeute")
        object.__setattr__(self, "positionen", tuple(self.positionen))


@dataclass(frozen=True)
class VerpackungsPosition:
    artikel_id: int
    anzahl: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        _setze_zahl(self, "anzahl", "Anzahl")


@dataclass(frozen=True)
class Endprodukt:
    id: int | None  # None = noch nicht gespeichert
    name: str
    rezept_id: int
    fuellmenge_ml: Decimal
    verpackung: tuple[VerpackungsPosition, ...] = ()

    def __post_init__(self) -> None:
        _setze_name(self)
        _setze_zahl(self, "fuellmenge_ml", "Füllmenge")
        object.__setattr__(self, "verpackung", tuple(self.verpackung))
