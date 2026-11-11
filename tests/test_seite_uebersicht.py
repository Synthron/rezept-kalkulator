from seitenhilfe import starte_app, starte_seite


def starte():
    return starte_seite("0_Uebersicht.py")


def metriken(at):
    return {m.label: m.value for m in at.metric}


def test_leere_uebersicht(ui_db):
    at = starte()
    assert not at.exception
    assert metriken(at) == {"Einkaufsartikel": "0", "Rezepte": "0", "Endprodukte": "0"}
    assert "Einkaufsartikel" in at.info[0].value


def test_uebersicht_mit_daten(beispiel_komplett):
    at = starte()
    assert not at.exception
    assert metriken(at) == {"Einkaufsartikel": "7", "Rezepte": "3", "Endprodukte": "2"}

    endprodukte, rezepte = (d.value for d in at.dataframe)
    assert dict(zip(endprodukte["Endprodukt"], endprodukte["Herstellkosten je Gebinde"])) == {
        "Orangenlikör 0,5 l": "5,23 €",
        "Orangensirup 0,5 l": "1,90 €",
    }
    assert dict(zip(rezepte["Name"], rezepte["Kosten je Einheit"])) == {
        "Gelee": "0,0012 €/g · 1,20 €/kg",
        "Orangenlikör": "0,0088 €/ml · 0,088 €/cl · 8,76 €/l",
        "Orangensirup": "0,0021 €/ml · 0,021 €/cl · 2,10 €/l",
    }


def test_app_startet_mit_uebersicht(ui_db):
    at = starte_app()
    assert not at.exception
    assert at.title[0].value == "Übersicht"


def waehle_zeile(at, tabelle, spalte, name):
    nr = {"uebersicht_endprodukte": 0, "uebersicht_rezepte": 1}[tabelle]
    zeile = list(at.dataframe[nr].value[spalte]).index(name)
    at.session_state[tabelle] = {"selection": {"rows": [zeile], "columns": []}}
    return at.run()


def test_klick_auf_endprodukt_oeffnet_endprodukt(beispiel_komplett):
    at = waehle_zeile(starte_app(), "uebersicht_endprodukte", "Endprodukt", "Orangenlikör 0,5 l")
    assert not at.exception
    assert at.title[0].value == "Endprodukte"
    assert at.selectbox(key="endprodukt_auswahl").value == beispiel_komplett["likoer_flasche"].id

    # Zurück zur Übersicht darf nicht erneut weiterleiten.
    at.switch_page("pages/0_Uebersicht.py").run()
    assert at.title[0].value == "Übersicht"


def test_klick_auf_rezept_oeffnet_rezept(beispiel_komplett):
    at = waehle_zeile(starte_app(), "uebersicht_rezepte", "Name", "Orangensirup")
    assert not at.exception
    assert at.title[0].value == "Rezepte"
    assert at.selectbox(key="rezept_auswahl").value == beispiel_komplett["sirup"].id
