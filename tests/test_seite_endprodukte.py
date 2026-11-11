from decimal import Decimal

import pytest

from seitenhilfe import klicke, starte_seite

D = Decimal


@pytest.fixture
def db(ui_db):
    return ui_db


@pytest.fixture
def beispiel(beispiel_komplett):
    return beispiel_komplett


def starte(**session_state):
    return starte_seite("3_Endprodukte.py", **session_state)


def metriken(at):
    return {m.label: m.value for m in at.metric}


def test_ohne_rezepte(db):
    at = starte()
    assert not at.exception
    assert any("kein Rezept" in i.value for i in at.info)


def test_uebersicht(db, beispiel):
    at = starte()
    assert not at.exception
    tabelle = at.dataframe[0].value.set_index("Endprodukt")
    assert tabelle.loc["Orangensirup 0,5 l", "Herstellkosten je Gebinde"] == "1,90 €"
    assert tabelle.loc["Orangenlikör 0,5 l", "Herstellkosten je Gebinde"] == "5,23 €"
    assert tabelle.loc["Orangenlikör 0,5 l", "Inhalt"] == "4,38 €"
    assert tabelle.loc["Orangenlikör 0,5 l", "Verpackung"] == "0,85 €"


def test_endprodukt_anzeigen(db, beispiel):
    at = starte(endprodukt_auswahl=beispiel["likoer_flasche"].id)
    assert not at.exception
    assert metriken(at) == {"Inhalt": "4,38 €", "Verpackung": "0,85 €", "Herstellkosten je Gebinde": "5,23 €"}
    aufstellung = next(d.value for d in at.dataframe if "Position" in d.value.columns)
    assert list(aufstellung["Position"]) == ["Inhalt: Orangenlikör", "Flasche 0,5 l", "Verschluss", "Etikett"]
    assert aufstellung["Menge"][0] == "500 ml à 8,76 €/l"


def test_nur_rezepte_mit_volumen_waehlbar(db, beispiel):
    at = starte()
    optionen = at.selectbox(key="ep_rezept_0_0").options
    assert "Gelee" not in optionen
    assert set(optionen) == {"Orangensirup", "Orangenlikör"}


def test_fuellmenge_aendern_rechnet_live_und_speichert(db, beispiel):
    endprodukt = beispiel["sirup_flasche"]
    at = starte(endprodukt_auswahl=endprodukt.id)
    at.number_input(key=f"ep_fuellmenge_{endprodukt.id}_0").set_value(250.0).run()
    # 250 ml × 2,10 €/l = 0,525 € + 0,85 € Verpackung
    assert metriken(at)["Herstellkosten je Gebinde"] == "1,38 €"

    klicke(at, "Speichern")
    assert not at.exception
    assert next(e for e in db.lade_endprodukte() if e.id == endprodukt.id).fuellmenge_ml == D("250")


def test_neues_endprodukt_anlegen(db, beispiel):
    at = starte()
    at.text_input(key="ep_name_0_0").input("Likör Probierflasche")
    at.selectbox(key="ep_rezept_0_0").set_value(beispiel["likoer"].id)
    at.number_input(key="ep_fuellmenge_0_0").set_value(40.0).run()
    assert metriken(at)["Inhalt"] == "0,35 €"

    klicke(at, "Speichern")
    assert not at.exception
    neu = next(e for e in db.lade_endprodukte() if e.name == "Likör Probierflasche")
    assert (neu.rezept_id, neu.fuellmenge_ml, neu.verpackung) == (beispiel["likoer"].id, D("40"), ())
    assert "gespeichert" in at.success[0].value
    assert at.selectbox(key="endprodukt_auswahl").value == 0
    assert at.text_input(key="ep_name_0_1").value == ""


def test_klick_in_tabelle_waehlt_endprodukt(db, beispiel):
    at = starte()
    zeile = list(at.dataframe[0].value["Endprodukt"]).index("Orangenlikör 0,5 l")
    at.session_state["endprodukt_auswahl_tabelle_0"] = {"selection": {"rows": [zeile], "columns": []}}
    at.run()
    assert not at.exception
    assert at.selectbox(key="endprodukt_auswahl").value == beispiel["likoer_flasche"].id


def test_fuellmenge_null_sperrt_speichern(db, beispiel):
    endprodukt = beispiel["sirup_flasche"]
    at = starte(endprodukt_auswahl=endprodukt.id)
    at.number_input(key=f"ep_fuellmenge_{endprodukt.id}_0").set_value(0.0).run()
    assert any("Füllmenge" in w.value for w in at.warning)
    assert next(b for b in at.button if b.label == "Speichern").disabled


def test_doppelter_name(db, beispiel):
    at = starte()
    at.text_input(key="ep_name_0_0").input("Orangensirup 0,5 l")
    klicke(at, "Speichern")
    assert "bereits vergeben" in at.error[0].value


def test_endprodukt_loeschen(db, beispiel):
    at = starte(endprodukt_auswahl=beispiel["sirup_flasche"].id)
    klicke(at, "Endgültig löschen")
    assert not at.exception
    assert [e.name for e in db.lade_endprodukte()] == ["Orangenlikör 0,5 l"]
    assert at.selectbox(key="endprodukt_auswahl").value == 0
