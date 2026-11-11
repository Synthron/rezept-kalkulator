"""Export und Import von Rezepten als JSON.

Eine Exportdatei enthält die gewählten Rezepte samt aller Zwischenprodukte und der benötigten
Einkaufsartikel. Verweise erfolgen über Namen, damit die Datei in jede Datenbank passt.
Zahlen werden als Text gespeichert, damit sie exakt bleiben.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from kalkulation.modelle import Artikel, Rezept, RezeptPosition

FORMAT = "herstellkosten-kalkulator/rezepte"
VERSION = 1


class ImportFehler(ValueError):
    pass


@dataclass(frozen=True)
class PaketPosition:
    menge: Decimal
    einheit: str
    artikel: str | None = None
    zwischenprodukt: str | None = None


@dataclass(frozen=True)
class PaketRezept:
    kopf: Rezept  # ohne ID und Positionen
    positionen: tuple[PaketPosition, ...]


@dataclass(frozen=True)
class Paket:
    artikel: tuple[Artikel, ...]  # ohne ID
    rezepte: tuple[PaketRezept, ...]


# --- Export ----------------------------------------------------------------------

def exportiere(rezept_ids: Iterable[int], artikel: Iterable[Artikel], rezepte: Iterable[Rezept]) -> dict:
    """JSON-fähiges dict; Zwischenprodukte stehen vor den Rezepten, die sie verwenden."""
    artikel_nach_id = {a.id: a for a in artikel}
    rezept_nach_id = {r.id: r for r in rezepte}
    reihenfolge: list[Rezept] = []
    besucht: set[int] = set()

    def besuche(rezept_id: int) -> None:
        if rezept_id in besucht:
            return
        besucht.add(rezept_id)
        rezept = rezept_nach_id[rezept_id]
        for position in rezept.positionen:
            if position.zwischenprodukt_id is not None:
                besuche(position.zwischenprodukt_id)
        reihenfolge.append(rezept)

    for rezept_id in rezept_ids:
        besuche(rezept_id)

    benoetigt = {p.artikel_id for r in reihenfolge for p in r.positionen if p.artikel_id is not None}
    return {
        "format": FORMAT,
        "version": VERSION,
        "artikel": [
            {
                "name": a.name,
                "kategorie": a.kategorie.value,
                "gebinde_menge": str(a.gebinde_menge),
                "gebinde_einheit": a.gebinde_einheit,
                "gebinde_preis": str(a.gebinde_preis),
                "lieferant": a.lieferant,
                "notiz": a.notiz,
            }
            for a in sorted((artikel_nach_id[i] for i in benoetigt), key=lambda a: a.name.casefold())
        ],
        "rezepte": [
            {
                "name": r.name,
                "ausbeute_menge": str(r.ausbeute_menge),
                "ausbeute_einheit": r.ausbeute_einheit,
                "notiz": r.notiz,
                "positionen": [
                    {
                        **(
                            {"artikel": artikel_nach_id[p.artikel_id].name}
                            if p.artikel_id is not None
                            else {"zwischenprodukt": rezept_nach_id[p.zwischenprodukt_id].name}
                        ),
                        "menge": str(p.menge),
                        "einheit": p.einheit,
                    }
                    for p in r.positionen
                ],
            }
            for r in reihenfolge
        ],
    }


# --- Import ----------------------------------------------------------------------

def paket_aus_json(daten: object) -> Paket:
    """Prüft Aufbau und Werte einer eingelesenen Exportdatei."""
    if not isinstance(daten, dict) or daten.get("format") != FORMAT:
        raise ImportFehler("Die Datei ist keine Rezept-Exportdatei dieses Tools.")
    if daten.get("version") != VERSION:
        raise ImportFehler(f"Nicht unterstützte Dateiversion: {daten.get('version')!r}.")

    artikel = tuple(_artikel(e, nr) for nr, e in enumerate(_liste(daten, "artikel", "Datei"), start=1))
    rezepte = tuple(_rezept(e, nr) for nr, e in enumerate(_liste(daten, "rezepte", "Datei"), start=1))
    _pruefe_eindeutig((a.name for a in artikel), "Artikel")
    _pruefe_eindeutig((r.kopf.name for r in rezepte), "Rezept")
    return Paket(artikel, rezepte)


def _liste(obj: dict, schluessel: str, kontext: str) -> list:
    wert = obj.get(schluessel, [])
    if not isinstance(wert, list):
        raise ImportFehler(f"{kontext}: '{schluessel}' muss eine Liste sein.")
    return wert


def _text(obj: dict, schluessel: str, kontext: str, *, pflicht: bool = True) -> str:
    wert = obj.get(schluessel)
    if wert is None and not pflicht:
        return ""
    if not isinstance(wert, str):
        raise ImportFehler(f"{kontext}: '{schluessel}' fehlt oder ist kein Text.")
    return wert


def _zahl(obj: dict, schluessel: str, kontext: str) -> str:
    wert = obj.get(schluessel)
    if isinstance(wert, bool) or not isinstance(wert, (str, int, float)):
        raise ImportFehler(f"{kontext}: '{schluessel}' fehlt oder ist keine Zahl.")
    return str(wert)


def _objekt(eintrag: object, kontext: str) -> dict:
    if not isinstance(eintrag, dict):
        raise ImportFehler(f"{kontext}: ungültiger Eintrag.")
    return eintrag


def _artikel(eintrag: object, nr: int) -> Artikel:
    kontext = f"Artikel {nr}"
    e = _objekt(eintrag, kontext)
    try:
        return Artikel(
            None,
            _text(e, "name", kontext),
            _text(e, "kategorie", kontext),
            _zahl(e, "gebinde_menge", kontext),
            _text(e, "gebinde_einheit", kontext),
            _zahl(e, "gebinde_preis", kontext),
            _text(e, "lieferant", kontext, pflicht=False),
            _text(e, "notiz", kontext, pflicht=False),
        )
    except ImportFehler:
        raise
    except ValueError as fehler:
        raise ImportFehler(f"{kontext} ({e.get('name')}): {fehler}") from None


def _rezept(eintrag: object, nr: int) -> PaketRezept:
    kontext = f"Rezept {nr}"
    e = _objekt(eintrag, kontext)
    try:
        kopf = Rezept(
            None,
            _text(e, "name", kontext),
            _zahl(e, "ausbeute_menge", kontext),
            _text(e, "ausbeute_einheit", kontext),
            notiz=_text(e, "notiz", kontext, pflicht=False),
        )
    except ImportFehler:
        raise
    except ValueError as fehler:
        raise ImportFehler(f"{kontext} ({e.get('name')}): {fehler}") from None

    kontext = f"Rezept '{kopf.name}'"
    positionen = tuple(
        _position(p, f"{kontext}, Position {i}") for i, p in enumerate(_liste(e, "positionen", kontext), start=1)
    )
    return PaketRezept(kopf, positionen)


def _position(eintrag: object, kontext: str) -> PaketPosition:
    e = _objekt(eintrag, kontext)
    artikel = _text(e, "artikel", kontext, pflicht=False) or None
    zwischenprodukt = _text(e, "zwischenprodukt", kontext, pflicht=False) or None
    if (artikel is None) == (zwischenprodukt is None):
        raise ImportFehler(f"{kontext}: braucht genau 'artikel' oder 'zwischenprodukt'.")
    try:
        # Platzhalter-ID, nur um Menge und Einheit wie beim Speichern zu prüfen
        geprueft = RezeptPosition(_zahl(e, "menge", kontext), _text(e, "einheit", kontext), artikel_id=0)
    except ImportFehler:
        raise
    except ValueError as fehler:
        raise ImportFehler(f"{kontext}: {fehler}") from None
    return PaketPosition(geprueft.menge, geprueft.einheit, artikel, zwischenprodukt)


def _pruefe_eindeutig(namen: Iterable[str], art: str) -> None:
    gesehen: set[str] = set()
    for name in namen:
        if name.casefold() in gesehen:
            raise ImportFehler(f"{art} '{name}' kommt in der Datei mehrfach vor.")
        gesehen.add(name.casefold())
