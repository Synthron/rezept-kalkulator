from decimal import Decimal

import pytest

import oberflaeche
from kalkulation.datenbank import Datenbank
from kalkulation.modelle import Artikel, Endprodukt, Kategorie, Rezept, RezeptPosition, VerpackungsPosition

D = Decimal


@pytest.fixture
def ui_db(tmp_path, monkeypatch):
    """Leere Test-Datenbank, die von den Streamlit-Seiten statt der echten verwendet wird."""
    test_db = Datenbank(tmp_path / "ui.db")
    monkeypatch.setattr(oberflaeche, "datenbank", lambda: test_db)
    return test_db


@pytest.fixture
def beispiel_komplett(ui_db):
    """Orangensirup und -likör inkl. Endprodukte aus PLANUNG.md, Abschnitt 5.4, plus ein Rezept in kg."""
    db = ui_db

    def artikel(name, menge, einheit, preis, kategorie=Kategorie.ZUTAT):
        return db.speichere_artikel(Artikel(None, name, kategorie, D(menge), einheit, D(preis))).id

    orangen = artikel("Orangen", "10", "kg", "15.00")
    zucker = artikel("Weißer Zucker", "1", "kg", "1.20")
    wasser = artikel("Wasser", "1", "l", "0")
    alkohol = artikel("Alkohol 96 %", "1", "l", "25.00")
    verpackung = tuple(
        VerpackungsPosition(artikel(name, "100", "Stk", preis, Kategorie.VERPACKUNG))
        for name, preis in (("Flasche 0,5 l", "60.00"), ("Verschluss", "10.00"), ("Etikett", "15.00"))
    )
    sirup = db.speichere_rezept(Rezept(None, "Orangensirup", D("2"), "l", (
        RezeptPosition(D("2"), "kg", artikel_id=orangen),
        RezeptPosition(D("1"), "kg", artikel_id=zucker),
        RezeptPosition(D("1"), "l", artikel_id=wasser),
    )))
    likoer = db.speichere_rezept(Rezept(None, "Orangenlikör", D("1"), "l", (
        RezeptPosition(D("0.3"), "l", artikel_id=alkohol),
        RezeptPosition(D("0.6"), "l", zwischenprodukt_id=sirup.id),
        RezeptPosition(D("0.1"), "l", artikel_id=wasser),
    )))
    gelee = db.speichere_rezept(Rezept(None, "Gelee", D("1"), "kg", (
        RezeptPosition(D("1"), "kg", artikel_id=zucker),
    )))
    return {
        "sirup": sirup,
        "likoer": likoer,
        "gelee": gelee,
        "sirup_flasche": db.speichere_endprodukt(Endprodukt(None, "Orangensirup 0,5 l", sirup.id, D("500"), verpackung)),
        "likoer_flasche": db.speichere_endprodukt(Endprodukt(None, "Orangenlikör 0,5 l", likoer.id, D("500"), verpackung)),
    }
