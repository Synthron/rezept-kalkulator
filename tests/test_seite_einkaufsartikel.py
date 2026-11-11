from decimal import Decimal

import pytest

from kalkulation.modelle import Artikel, Kategorie, Rezept, RezeptPosition
from seitenhilfe import klicke, starte_seite

D = Decimal


@pytest.fixture
def db(ui_db):
    return ui_db


def starte(**session_state):
    return starte_seite("1_Einkaufsartikel.py", **session_state)


def test_leere_seite(db):
    at = starte()
    assert not at.exception
    assert "Keine Artikel" in at.info[0].value


def test_artikel_anlegen(db):
    at = starte()
    at.text_input(key="name_0_0").input("Weißer Zucker")
    at.number_input(key="menge_0_0").set_value(2.5)
    at.selectbox(key="einheit_0_0").select("kg")
    at.number_input(key="preis_0_0").set_value(3.0)
    at.text_input(key="lieferant_0_0").input("Großmarkt")
    klicke(at, "Speichern")

    assert not at.exception
    [artikel] = db.lade_artikel()
    assert (artikel.name, artikel.gebinde_menge, artikel.gebinde_preis) == ("Weißer Zucker", D("2.5"), D("3"))
    assert artikel.lieferant == "Großmarkt"
    zeile = at.dataframe[0].value.iloc[0]
    assert zeile["Gebinde"] == "2,5 kg"
    assert zeile["Preis je Einheit"] == "1,20 €/kg"
    assert "gespeichert" in at.success[0].value
    assert at.selectbox(key="artikel_auswahl").value == artikel.id


def test_artikel_bearbeiten(db):
    artikel = db.speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1.20")))
    at = starte(artikel_auswahl=artikel.id)
    assert at.text_input(key=f"name_{artikel.id}_0").value == "Zucker"
    at.number_input(key=f"preis_{artikel.id}_0").set_value(1.5)
    klicke(at, "Speichern")

    assert not at.exception
    assert db.lade_artikel()[0].gebinde_preis == D("1.50")


def test_fehlermeldung_bei_leerem_namen(db):
    at = starte()
    klicke(at, "Speichern")
    assert "Name" in at.error[0].value
    assert db.lade_artikel() == []


def test_doppelter_name(db):
    db.speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1")))
    at = starte()
    at.text_input(key="name_0_0").input("Zucker")
    klicke(at, "Speichern")
    assert "bereits vergeben" in at.error[0].value


def test_artikel_loeschen(db):
    artikel = db.speichere_artikel(Artikel(None, "Zimt", Kategorie.ZUTAT, D("50"), "g", D("2")))
    at = starte(artikel_auswahl=artikel.id)
    klicke(at, "Endgültig löschen")

    assert not at.exception
    assert db.lade_artikel() == []
    assert at.selectbox(key="artikel_auswahl").value == 0


def test_verwendeter_artikel_nicht_loeschbar(db):
    zucker = db.speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1")))
    db.speichere_rezept(Rezept(None, "Sirup", D("1"), "l", (RezeptPosition(D("1"), "kg", artikel_id=zucker.id),)))
    at = starte(artikel_auswahl=zucker.id)

    assert "Rezept 'Sirup'" in at.caption[0].value
    assert "Endgültig löschen" not in [b.label for b in at.button]


def test_filter_verpackungen(db):
    db.speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1")))
    db.speichere_artikel(Artikel(None, "Flasche", Kategorie.VERPACKUNG, D("10"), "Stk", D("5")))
    at = starte(artikel_filter="Verpackungen")
    assert list(at.dataframe[0].value["Name"]) == ["Flasche"]
