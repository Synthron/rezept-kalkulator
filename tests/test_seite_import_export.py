import json
from decimal import Decimal

import streamlit as st

from kalkulation.datenbank import Datenbank
from kalkulation.modelle import Artikel, Kategorie, Rezept, RezeptPosition
from seitenhilfe import klicke, starte_seite


class HochgeladeneDatei:
    def __init__(self, inhalt: bytes) -> None:
        self._inhalt = inhalt

    def getvalue(self) -> bytes:
        return self._inhalt


def lade_hoch(monkeypatch, inhalt: bytes) -> None:
    # AppTest kann st.file_uploader nicht bedienen, daher wird der Upload simuliert.
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: HochgeladeneDatei(inhalt))


def exportdatei(tmp_path) -> bytes:
    quelle = Datenbank(tmp_path / "quelle.db")
    zucker = quelle.speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, Decimal(1), "kg", Decimal("1.20")))
    sirup = quelle.speichere_rezept(Rezept(None, "Läuterzucker", Decimal(1), "l", (
        RezeptPosition(Decimal("0.5"), "kg", artikel_id=zucker.id),
    )))
    return json.dumps(quelle.exportiere_rezepte([sirup.id]), ensure_ascii=False).encode("utf-8")


def starte(**session_state):
    return starte_seite("5_Import_Export.py", **session_state)


def test_seite_ohne_daten(ui_db):
    at = starte()
    assert not at.exception
    assert at.multiselect(key="export_auswahl").options == []


def test_export_zeigt_umfang(beispiel_komplett):
    at = starte()
    at.multiselect(key="export_auswahl").set_value([beispiel_komplett["likoer"].id]).run()
    assert not at.exception
    assert any("Enthält 2 Rezept(e) und 4 Einkaufsartikel" in c.value for c in at.caption)


def test_import_mit_vorschau(ui_db, tmp_path, monkeypatch):
    lade_hoch(monkeypatch, exportdatei(tmp_path))
    at = starte()
    assert not at.exception
    assert ui_db.lade_rezepte() == []  # Vorschau ändert nichts
    assert any("Rezepte: Läuterzucker" in m.value for m in at.markdown)

    klicke(at, "Importieren")
    assert not at.exception
    assert [r.name for r in ui_db.lade_rezepte()] == ["Läuterzucker"]
    assert "1 Rezept(e), 1 Artikel" in at.success[0].value


def test_import_ungueltige_datei(ui_db, monkeypatch):
    lade_hoch(monkeypatch, b"kein json")
    at = starte()
    assert not at.exception
    assert "Import nicht möglich" in at.error[0].value
