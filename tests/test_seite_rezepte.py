import json
from decimal import Decimal

import pytest

from kalkulation.modelle import Artikel, Endprodukt, Kategorie, Rezept, RezeptPosition
from seitenhilfe import klicke, starte_seite

D = Decimal


@pytest.fixture
def db(ui_db):
    return ui_db


@pytest.fixture
def beispiel(db):
    """Orangensirup und -likör (Beispielrechnung aus der README)."""
    def artikel(name, menge, einheit, preis, kategorie=Kategorie.ZUTAT):
        return db.speichere_artikel(Artikel(None, name, kategorie, D(menge), einheit, D(preis))).id

    orangen = artikel("Orangen", "10", "kg", "15.00")
    zucker = artikel("Weißer Zucker", "1", "kg", "1.20")
    wasser = artikel("Wasser", "1", "l", "0")
    alkohol = artikel("Alkohol 96 %", "1", "l", "25.00")
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
    return {"sirup": sirup, "likoer": likoer, "zucker": zucker}


def starte(**session_state):
    return starte_seite("2_Rezepte.py", **session_state)


def metriken(at):
    return {m.label: m.value for m in at.metric}


def test_leere_seite(db):
    at = starte()
    assert not at.exception
    assert any("Keine Rezepte" in i.value for i in at.info)


def test_uebersicht_mit_kosten_je_einheit(db, beispiel):
    at = starte()
    assert not at.exception
    tabelle = at.dataframe[0].value.set_index("Name")
    assert tabelle.loc["Orangensirup", "Chargenkosten"] == "4,20 €"
    assert tabelle.loc["Orangensirup", "Kosten je Einheit"] == "0,0021 €/ml · 0,021 €/cl · 2,10 €/l"
    assert tabelle.loc["Orangenlikör", "Kosten je Einheit"] == "0,0088 €/ml · 0,088 €/cl · 8,76 €/l"


def test_rezept_mit_zwischenprodukt_anzeigen(db, beispiel):
    at = starte(rezept_auswahl=beispiel["likoer"].id)
    assert not at.exception
    assert metriken(at) == {
        "Chargenkosten": "8,76 €",
        "Kosten je ml": "0,0088 €",
        "Kosten je cl": "0,088 €",
        "Kosten je l": "8,76 €",
    }
    positionen = next(d.value for d in at.dataframe if "Kosten" in d.value.columns)
    assert list(positionen["Zutat"]) == ["Alkohol 96 %", "Orangensirup", "Wasser"]
    assert list(positionen["Kosten"]) == ["7,50 €", "1,26 €", "0,00 €"]
    assert any("Summe der Zutatenmengen: 1 l" in c.value for c in at.caption)


def test_ausbeute_aendern_rechnet_live_und_speichert(db, beispiel):
    rezept = beispiel["sirup"]
    k = f"{rezept.id}_0"
    at = starte(rezept_auswahl=rezept.id)
    at.number_input(key=f"rezept_ausbeute_{k}").set_value(1.5).run()
    assert metriken(at)["Kosten je l"] == "2,80 €"

    klicke(at, "Speichern")
    assert not at.exception
    assert next(r for r in db.lade_rezepte() if r.id == rezept.id).ausbeute_menge == D("1.5")


def test_ausbeute_in_stueck(db, beispiel):
    rezept = beispiel["sirup"]
    k = f"{rezept.id}_0"
    at = starte(rezept_auswahl=rezept.id)
    at.selectbox(key=f"rezept_einheit_{k}").select("Stk").run()
    at.number_input(key=f"rezept_ausbeute_{k}").set_value(20.0).run()
    assert metriken(at) == {"Chargenkosten": "4,20 €", "Kosten je Stk": "0,21 €"}


def test_ausbeute_null_sperrt_speichern(db, beispiel):
    rezept = beispiel["sirup"]
    at = starte(rezept_auswahl=rezept.id)
    at.number_input(key=f"rezept_ausbeute_{rezept.id}_0").set_value(0.0).run()
    assert any("Ausbeute" in w.value for w in at.warning)
    assert next(b for b in at.button if b.label == "Speichern").disabled


def test_neues_rezept_ohne_zutaten_anlegen(db):
    at = starte()
    at.text_input(key="rezept_name_0_0").input("Läuterzucker")
    klicke(at, "Speichern")
    assert not at.exception
    assert [r.name for r in db.lade_rezepte()] == ["Läuterzucker"]
    assert "gespeichert" in at.success[0].value


def test_fehler_beim_speichern_wird_angezeigt(db, beispiel):
    # Sirup wird als Endprodukt abgefüllt: Umstellen auf kg muss abgelehnt werden.
    db.speichere_endprodukt(Endprodukt(None, "Sirup 0,5 l", beispiel["sirup"].id, D("500")))
    rezept = beispiel["sirup"]
    at = starte(rezept_auswahl=rezept.id)
    at.selectbox(key=f"rezept_einheit_{rezept.id}_0").select("kg").run()
    klicke(at, "Speichern")
    assert "Volumen" in at.error[0].value
    assert next(r for r in db.lade_rezepte() if r.id == rezept.id).ausbeute_einheit == "l"


def test_aktuelles_rezept_nicht_als_zutat_waehlbar(db, beispiel):
    at = starte(rezept_auswahl=beispiel["sirup"].id)
    editor = next(d for d in at.dataframe if d.editing_mode == "dynamic")
    optionen = json.loads(editor.proto.columns)["Zutat"]["type_config"]["options"]
    assert "Orangenlikör (Rezept)" in optionen
    assert "Orangensirup (Rezept)" not in optionen


def test_rezept_loeschen(db, beispiel):
    likoer = beispiel["likoer"]
    at = starte(rezept_auswahl=likoer.id)
    klicke(at, "Endgültig löschen")
    assert not at.exception
    assert [r.name for r in db.lade_rezepte()] == ["Orangensirup"]


def test_verwendetes_rezept_nicht_loeschbar(db, beispiel):
    at = starte(rezept_auswahl=beispiel["sirup"].id)
    assert any("Rezept 'Orangenlikör'" in c.value for c in at.caption)
    assert "Endgültig löschen" not in [b.label for b in at.button]


def test_rezept_duplizieren(db, beispiel):
    at = starte(rezept_auswahl=beispiel["likoer"].id)
    klicke(at, "Rezept duplizieren")
    assert not at.exception
    kopie = next(r for r in db.lade_rezepte() if r.name == "Orangenlikör (Kopie)")
    assert at.selectbox(key="rezept_auswahl").value == kopie.id
    assert "Kopie" in at.success[0].value
    assert {m.label: m.value for m in at.metric}["Chargenkosten"] == "8,76 €"
