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
