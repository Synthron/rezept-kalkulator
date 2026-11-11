"""SQLite-Zugriff: Schema anlegen, Daten laden, speichern und löschen.

Zahlen werden als TEXT gespeichert, damit Decimal-Werte exakt erhalten bleiben.
Jede Änderung wird vor dem Commit gegen alle Rezepte und Endprodukte durchgerechnet;
erzeugt sie einen Fehler (Einheitenkonflikt, Zirkelbezug, …), wird sie zurückgerollt.
"""

import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from kalkulation.austausch import Paket, PaketRezept, exportiere
from kalkulation.berechnung import Kalkulator, ReferenzFehler, ZirkelbezugFehler
from kalkulation.modelle import Artikel, Endprodukt, Rezept, RezeptPosition, VerpackungsPosition

STANDARD_PFAD = Path(__file__).resolve().parent.parent / "daten" / "kalkulation.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artikel (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kategorie       TEXT NOT NULL CHECK (kategorie IN ('zutat', 'verpackung')),
    gebinde_menge   TEXT NOT NULL,
    gebinde_einheit TEXT NOT NULL,
    gebinde_preis   TEXT NOT NULL,
    lieferant       TEXT NOT NULL DEFAULT '',
    notiz           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rezept (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    ausbeute_menge   TEXT NOT NULL,
    ausbeute_einheit TEXT NOT NULL,
    notiz            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rezept_position (
    id                 INTEGER PRIMARY KEY,
    rezept_id          INTEGER NOT NULL REFERENCES rezept(id) ON DELETE CASCADE,
    reihenfolge        INTEGER NOT NULL,
    artikel_id         INTEGER REFERENCES artikel(id) ON DELETE RESTRICT,
    zwischenprodukt_id INTEGER REFERENCES rezept(id) ON DELETE RESTRICT,
    menge              TEXT NOT NULL,
    einheit            TEXT NOT NULL,
    CHECK ((artikel_id IS NULL) <> (zwischenprodukt_id IS NULL))
);

CREATE TABLE IF NOT EXISTS endprodukt (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    rezept_id     INTEGER NOT NULL REFERENCES rezept(id) ON DELETE RESTRICT,
    fuellmenge_ml TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS endprodukt_verpackung (
    id            INTEGER PRIMARY KEY,
    endprodukt_id INTEGER NOT NULL REFERENCES endprodukt(id) ON DELETE CASCADE,
    reihenfolge   INTEGER NOT NULL,
    artikel_id    INTEGER NOT NULL REFERENCES artikel(id) ON DELETE RESTRICT,
    anzahl        TEXT NOT NULL
);
"""


class DoppelterNameFehler(ValueError):
    pass


class InVerwendungFehler(ValueError):
    pass


@dataclass
class ImportBericht:
    artikel_neu: list[str] = field(default_factory=list)
    artikel_vorhanden: list[str] = field(default_factory=list)
    rezepte_neu: list[str] = field(default_factory=list)
    rezepte_vorhanden: list[str] = field(default_factory=list)


class Datenbank:
    def __init__(self, pfad: Path | str = STANDARD_PFAD) -> None:
        self.pfad = Path(pfad)
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        with self._verbindung() as con:
            con.executescript(_SCHEMA)

    @contextmanager
    def _verbindung(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.pfad)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:  # Commit bei Erfolg, Rollback bei Ausnahme
                yield con
        except sqlite3.IntegrityError as fehler:
            meldung = str(fehler)
            if "UNIQUE" in meldung:
                raise DoppelterNameFehler("Dieser Name ist bereits vergeben.") from fehler
            if "FOREIGN KEY" in meldung:
                raise ReferenzFehler("Verweis auf einen nicht vorhandenen Artikel oder ein Rezept.") from fehler
            raise
        finally:
            con.close()

    # --- Laden -------------------------------------------------------------------

    def lade_artikel(self) -> list[Artikel]:
        with self._verbindung() as con:
            return _lade_artikel(con)

    def lade_rezepte(self) -> list[Rezept]:
        with self._verbindung() as con:
            return _lade_rezepte(con)

    def lade_endprodukte(self) -> list[Endprodukt]:
        with self._verbindung() as con:
            return _lade_endprodukte(con)

    def kalkulator(self) -> Kalkulator:
        with self._verbindung() as con:
            return Kalkulator(_lade_artikel(con), _lade_rezepte(con))

    # --- Speichern ---------------------------------------------------------------

    def speichere_artikel(self, artikel: Artikel) -> Artikel:
        with self._verbindung() as con:
            artikel_id = _schreibe_artikel(con, artikel)
            _pruefe_konsistenz(con)
        return replace(artikel, id=artikel_id)

    def speichere_rezept(self, rezept: Rezept) -> Rezept:
        with self._verbindung() as con:
            rezept_id = _schreibe_rezept(con, rezept)
            _pruefe_konsistenz(con)
        return replace(rezept, id=rezept_id)

    def speichere_endprodukt(self, endprodukt: Endprodukt) -> Endprodukt:
        werte = (endprodukt.name, endprodukt.rezept_id, str(endprodukt.fuellmenge_ml))
        with self._verbindung() as con:
            if endprodukt.id is None:
                endprodukt_id = con.execute(
                    "INSERT INTO endprodukt (name, rezept_id, fuellmenge_ml) VALUES (?, ?, ?)", werte
                ).lastrowid
            else:
                endprodukt_id = endprodukt.id
                _aendere(
                    con,
                    "UPDATE endprodukt SET name = ?, rezept_id = ?, fuellmenge_ml = ? WHERE id = ?",
                    (*werte, endprodukt_id),
                    f"Endprodukt (ID {endprodukt_id})",
                )
                con.execute("DELETE FROM endprodukt_verpackung WHERE endprodukt_id = ?", (endprodukt_id,))
            con.executemany(
                "INSERT INTO endprodukt_verpackung (endprodukt_id, reihenfolge, artikel_id, anzahl) VALUES (?, ?, ?, ?)",
                [(endprodukt_id, i, v.artikel_id, str(v.anzahl)) for i, v in enumerate(endprodukt.verpackung)],
            )
            _pruefe_konsistenz(con)
        return replace(endprodukt, id=endprodukt_id)

    def dupliziere_rezept(self, rezept_id: int) -> Rezept:
        """Legt eine Kopie mit Namen „… (Kopie)“ bzw. „… (Kopie 2)“ usw. an."""
        with self._verbindung() as con:
            rezepte = _lade_rezepte(con)
            original = next((r for r in rezepte if r.id == rezept_id), None)
            if original is None:
                raise ReferenzFehler(f"Rezept (ID {rezept_id}) nicht gefunden.")
            vergeben = {r.name.casefold() for r in rezepte}
            nummer = 1
            name = f"{original.name} (Kopie)"
            while name.casefold() in vergeben:
                nummer += 1
                name = f"{original.name} (Kopie {nummer})"
            kopie = replace(original, id=None, name=name)
            kopie_id = _schreibe_rezept(con, kopie)
        return replace(kopie, id=kopie_id)

    # --- Export & Import ---------------------------------------------------------

    def exportiere_rezepte(self, rezept_ids: Iterable[int]) -> dict:
        with self._verbindung() as con:
            return exportiere(rezept_ids, _lade_artikel(con), _lade_rezepte(con))

    def importiere(self, paket: Paket, *, nur_pruefen: bool = False) -> ImportBericht:
        """Importiert alles oder nichts. Vorhandene Namen werden verwendet, aber nicht verändert.

        Mit nur_pruefen=True wird alles durchgespielt und anschließend zurückgerollt (Vorschau).
        """
        bericht = ImportBericht()
        with self._verbindung() as con:
            artikel_ids = {a.name.casefold(): a.id for a in _lade_artikel(con)}
            rezept_ids = {r.name.casefold(): r.id for r in _lade_rezepte(con)}

            for artikel in paket.artikel:
                if artikel.name.casefold() in artikel_ids:
                    bericht.artikel_vorhanden.append(artikel.name)
                else:
                    artikel_ids[artikel.name.casefold()] = _schreibe_artikel(con, artikel)
                    bericht.artikel_neu.append(artikel.name)

            offen = []
            for paket_rezept in paket.rezepte:
                if paket_rezept.kopf.name.casefold() in rezept_ids:
                    bericht.rezepte_vorhanden.append(paket_rezept.kopf.name)
                else:
                    offen.append(paket_rezept)
            _pruefe_verweise(offen, artikel_ids, rezept_ids)

            # Rezepte erst anlegen, wenn alle ihre Zwischenprodukte existieren
            while offen:
                bereit = [
                    r for r in offen
                    if all(p.zwischenprodukt is None or p.zwischenprodukt.casefold() in rezept_ids for p in r.positionen)
                ]
                if not bereit:
                    raise ZirkelbezugFehler(
                        "Zirkelbezug zwischen den Rezepten: " + ", ".join(r.kopf.name for r in offen)
                    )
                for paket_rezept in bereit:
                    positionen = tuple(
                        RezeptPosition(
                            p.menge,
                            p.einheit,
                            artikel_id=artikel_ids[p.artikel.casefold()] if p.artikel else None,
                            zwischenprodukt_id=rezept_ids[p.zwischenprodukt.casefold()] if p.zwischenprodukt else None,
                        )
                        for p in paket_rezept.positionen
                    )
                    name = paket_rezept.kopf.name
                    rezept_ids[name.casefold()] = _schreibe_rezept(con, replace(paket_rezept.kopf, positionen=positionen))
                    bericht.rezepte_neu.append(name)
                offen = [r for r in offen if r.kopf.name.casefold() not in rezept_ids]

            _pruefe_konsistenz(con)
            if nur_pruefen:
                con.rollback()
        return bericht

    # --- Verwendungen & Löschen --------------------------------------------------

    def verwendungen_artikel(self, artikel_id: int) -> list[str]:
        with self._verbindung() as con:
            return _verwendungen_artikel(con, artikel_id)

    def verwendungen_rezept(self, rezept_id: int) -> list[str]:
        with self._verbindung() as con:
            return _verwendungen_rezept(con, rezept_id)

    def loesche_artikel(self, artikel_id: int) -> None:
        with self._verbindung() as con:
            _pruefe_unbenutzt(_verwendungen_artikel(con, artikel_id))
            _aendere(con, "DELETE FROM artikel WHERE id = ?", (artikel_id,), f"Artikel (ID {artikel_id})")

    def loesche_rezept(self, rezept_id: int) -> None:
        with self._verbindung() as con:
            _pruefe_unbenutzt(_verwendungen_rezept(con, rezept_id))
            _aendere(con, "DELETE FROM rezept WHERE id = ?", (rezept_id,), f"Rezept (ID {rezept_id})")

    def loesche_endprodukt(self, endprodukt_id: int) -> None:
        with self._verbindung() as con:
            _aendere(con, "DELETE FROM endprodukt WHERE id = ?", (endprodukt_id,), f"Endprodukt (ID {endprodukt_id})")


def _lade_artikel(con: sqlite3.Connection) -> list[Artikel]:
    return [
        Artikel(
            z["id"], z["name"], z["kategorie"], z["gebinde_menge"], z["gebinde_einheit"],
            z["gebinde_preis"], z["lieferant"], z["notiz"],
        )
        for z in con.execute("SELECT * FROM artikel ORDER BY name")
    ]


def _lade_rezepte(con: sqlite3.Connection) -> list[Rezept]:
    positionen: dict[int, list[RezeptPosition]] = defaultdict(list)
    for z in con.execute("SELECT * FROM rezept_position ORDER BY rezept_id, reihenfolge"):
        positionen[z["rezept_id"]].append(
            RezeptPosition(z["menge"], z["einheit"], z["artikel_id"], z["zwischenprodukt_id"])
        )
    return [
        Rezept(z["id"], z["name"], z["ausbeute_menge"], z["ausbeute_einheit"], tuple(positionen[z["id"]]), z["notiz"])
        for z in con.execute("SELECT * FROM rezept ORDER BY name")
    ]


def _lade_endprodukte(con: sqlite3.Connection) -> list[Endprodukt]:
    verpackung: dict[int, list[VerpackungsPosition]] = defaultdict(list)
    for z in con.execute("SELECT * FROM endprodukt_verpackung ORDER BY endprodukt_id, reihenfolge"):
        verpackung[z["endprodukt_id"]].append(VerpackungsPosition(z["artikel_id"], z["anzahl"]))
    return [
        Endprodukt(z["id"], z["name"], z["rezept_id"], z["fuellmenge_ml"], tuple(verpackung[z["id"]]))
        for z in con.execute("SELECT * FROM endprodukt ORDER BY name")
    ]


def _schreibe_artikel(con: sqlite3.Connection, artikel: Artikel) -> int:
    werte = (
        artikel.name, artikel.kategorie.value, str(artikel.gebinde_menge), artikel.gebinde_einheit,
        str(artikel.gebinde_preis), artikel.lieferant.strip(), artikel.notiz.strip(),
    )
    if artikel.id is None:
        return con.execute(
            "INSERT INTO artikel (name, kategorie, gebinde_menge, gebinde_einheit, gebinde_preis, "
            "lieferant, notiz) VALUES (?, ?, ?, ?, ?, ?, ?)",
            werte,
        ).lastrowid
    _aendere(
        con,
        "UPDATE artikel SET name = ?, kategorie = ?, gebinde_menge = ?, gebinde_einheit = ?, "
        "gebinde_preis = ?, lieferant = ?, notiz = ? WHERE id = ?",
        (*werte, artikel.id),
        f"Artikel (ID {artikel.id})",
    )
    return artikel.id


def _schreibe_rezept(con: sqlite3.Connection, rezept: Rezept) -> int:
    werte = (rezept.name, str(rezept.ausbeute_menge), rezept.ausbeute_einheit, rezept.notiz.strip())
    if rezept.id is None:
        rezept_id = con.execute(
            "INSERT INTO rezept (name, ausbeute_menge, ausbeute_einheit, notiz) VALUES (?, ?, ?, ?)", werte
        ).lastrowid
    else:
        rezept_id = rezept.id
        _aendere(
            con,
            "UPDATE rezept SET name = ?, ausbeute_menge = ?, ausbeute_einheit = ?, notiz = ? WHERE id = ?",
            (*werte, rezept_id),
            f"Rezept (ID {rezept_id})",
        )
        con.execute("DELETE FROM rezept_position WHERE rezept_id = ?", (rezept_id,))
    con.executemany(
        "INSERT INTO rezept_position (rezept_id, reihenfolge, artikel_id, zwischenprodukt_id, menge, einheit) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (rezept_id, i, p.artikel_id, p.zwischenprodukt_id, str(p.menge), p.einheit)
            for i, p in enumerate(rezept.positionen)
        ],
    )
    return rezept_id


def _pruefe_verweise(
    rezepte: list[PaketRezept], artikel_ids: dict[str, int], rezept_ids: dict[str, int]
) -> None:
    """Jeder Verweis muss auf einen vorhandenen oder mitimportierten Artikel bzw. ein Rezept zeigen."""
    importierte = {r.kopf.name.casefold() for r in rezepte}
    for rezept in rezepte:
        for p in rezept.positionen:
            if p.artikel and p.artikel.casefold() not in artikel_ids:
                raise ReferenzFehler(f"Rezept '{rezept.kopf.name}': Artikel '{p.artikel}' fehlt in Datei und Datenbank.")
            name = (p.zwischenprodukt or "").casefold()
            if p.zwischenprodukt and name not in rezept_ids and name not in importierte:
                raise ReferenzFehler(
                    f"Rezept '{rezept.kopf.name}': Zwischenprodukt '{p.zwischenprodukt}' fehlt in Datei und Datenbank."
                )


def _pruefe_konsistenz(con: sqlite3.Connection) -> None:
    rezepte = _lade_rezepte(con)
    kalkulator = Kalkulator(_lade_artikel(con), rezepte)
    for rezept in rezepte:
        kalkulator.rezept(rezept.id)
    for endprodukt in _lade_endprodukte(con):
        kalkulator.endprodukt(endprodukt)


def _aendere(con: sqlite3.Connection, sql: str, parameter: tuple, bezeichnung: str) -> None:
    if con.execute(sql, parameter).rowcount == 0:
        raise ReferenzFehler(f"{bezeichnung} nicht gefunden.")


def _namen(con: sqlite3.Connection, sql: str, parameter: tuple) -> list[str]:
    return [z[0] for z in con.execute(sql, parameter)]


def _verwendungen_artikel(con: sqlite3.Connection, artikel_id: int) -> list[str]:
    rezepte = _namen(
        con,
        "SELECT DISTINCT r.name FROM rezept_position p JOIN rezept r ON r.id = p.rezept_id "
        "WHERE p.artikel_id = ? ORDER BY r.name",
        (artikel_id,),
    )
    endprodukte = _namen(
        con,
        "SELECT DISTINCT e.name FROM endprodukt_verpackung v JOIN endprodukt e ON e.id = v.endprodukt_id "
        "WHERE v.artikel_id = ? ORDER BY e.name",
        (artikel_id,),
    )
    return [f"Rezept '{n}'" for n in rezepte] + [f"Endprodukt '{n}'" for n in endprodukte]


def _verwendungen_rezept(con: sqlite3.Connection, rezept_id: int) -> list[str]:
    rezepte = _namen(
        con,
        "SELECT DISTINCT r.name FROM rezept_position p JOIN rezept r ON r.id = p.rezept_id "
        "WHERE p.zwischenprodukt_id = ? ORDER BY r.name",
        (rezept_id,),
    )
    endprodukte = _namen(con, "SELECT name FROM endprodukt WHERE rezept_id = ? ORDER BY name", (rezept_id,))
    return [f"Rezept '{n}'" for n in rezepte] + [f"Endprodukt '{n}'" for n in endprodukte]


def _pruefe_unbenutzt(verwendungen: list[str]) -> None:
    if verwendungen:
        raise InVerwendungFehler("Kann nicht gelöscht werden, wird noch verwendet in: " + ", ".join(verwendungen))
