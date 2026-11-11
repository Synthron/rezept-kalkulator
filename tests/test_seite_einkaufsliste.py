from seitenhilfe import klicke, starte_seite


def starte(**session_state):
    return starte_seite("4_Einkaufsliste.py", **session_state)


def test_ohne_auswahl(ui_db):
    at = starte()
    assert not at.exception
    assert "Wähle Endprodukte" in at.info[0].value


def test_hochrechnung_fuer_endprodukte(beispiel_komplett):
    b = beispiel_komplett
    at = starte()
    at.multiselect(key="ek_endprodukte").set_value([b["sirup_flasche"].id, b["likoer_flasche"].id]).run()
    at.number_input(key=f"ek_anzahl_{b['sirup_flasche'].id}").set_value(20).run()
    assert not at.exception

    assert {m.label: m.value for m in at.metric} == {
        "Einkauf (ganze Gebinde)": "173,40 €",
        "Materialverbrauch": "90,30 €",
    }
    einkauf, herstellen = (d.value for d in at.dataframe)
    zeilen = einkauf.set_index("Artikel")
    assert zeilen.loc["Orangen", "Bedarf"] == "13 kg"
    assert zeilen.loc["Orangen", "Anzahl Gebinde"] == 2
    assert zeilen.loc["Weißer Zucker", "Bedarf"] == "6,5 kg"
    assert zeilen.loc["Flasche 0,5 l", "Bedarf"] == "30 Stk"
    assert dict(zip(herstellen["Rezept"], herstellen["Chargen"])) == {"Orangensirup": "6,5", "Orangenlikör": "5"}


def test_hochrechnung_fuer_rezept(beispiel_komplett):
    sirup = beispiel_komplett["sirup"]
    at = starte()
    at.multiselect(key="ek_rezepte").set_value([sirup.id]).run()
    at.number_input(key=f"ek_menge_{sirup.id}").set_value(4.0).run()
    assert not at.exception
    einkauf = at.dataframe[0].value.set_index("Artikel")
    assert einkauf.loc["Orangen", "Bedarf"] == "4 kg"
    assert einkauf.loc["Wasser", "Bedarf"] == "2 l"
    assert "Flasche 0,5 l" not in einkauf.index


def test_anzahl_null_wird_ignoriert(beispiel_komplett):
    endprodukt = beispiel_komplett["sirup_flasche"]
    at = starte()
    at.multiselect(key="ek_endprodukte").set_value([endprodukt.id]).run()
    at.number_input(key=f"ek_anzahl_{endprodukt.id}").set_value(0).run()
    assert "Wähle Endprodukte" in at.info[0].value
