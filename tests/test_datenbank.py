from decimal import Decimal

import pytest

from kalkulation.berechnung import ReferenzFehler, ZirkelbezugFehler
from kalkulation.datenbank import Datenbank, DoppelterNameFehler, InVerwendungFehler
from kalkulation.einheiten import EinheitenFehler
from kalkulation.modelle import Artikel, Endprodukt, Kategorie, Rezept, RezeptPosition, VerpackungsPosition

D = Decimal


@pytest.fixture
def db(tmp_path):
    return Datenbank(tmp_path / "unterordner" / "test.db")


@pytest.fixture
def beispiel(db):
    """Beispielrechnung aus der README; gibt die vergebenen IDs zurück."""
    def artikel(name, kategorie, menge, einheit, preis):
        return db.speichere_artikel(Artikel(None, name, kategorie, D(menge), einheit, D(preis))).id

    ids = {
        "orangen": artikel("Orangen", Kategorie.ZUTAT, "10", "kg", "15.00"),
        "zucker": artikel("Zucker", Kategorie.ZUTAT, "1", "kg", "1.20"),
        "wasser": artikel("Wasser", Kategorie.ZUTAT, "1", "l", "0"),
        "alkohol": artikel("Alkohol 96 %", Kategorie.ZUTAT, "1", "l", "25.00"),
        "flasche": artikel("Flasche 0,5 l", Kategorie.VERPACKUNG, "100", "Stk", "60.00"),
        "verschluss": artikel("Verschluss", Kategorie.VERPACKUNG, "100", "Stk", "10.00"),
        "etikett": artikel("Etikett", Kategorie.VERPACKUNG, "100", "Stk", "15.00"),
    }
    ids["sirup"] = db.speichere_rezept(Rezept(None, "Orangensirup", D("2"), "l", (
        RezeptPosition(D("2"), "kg", artikel_id=ids["orangen"]),
        RezeptPosition(D("1"), "kg", artikel_id=ids["zucker"]),
        RezeptPosition(D("1"), "l", artikel_id=ids["wasser"]),
    ))).id
    ids["likoer"] = db.speichere_rezept(Rezept(None, "Orangenlikör", D("1"), "l", (
        RezeptPosition(D("0.3"), "l", artikel_id=ids["alkohol"]),
        RezeptPosition(D("0.6"), "l", zwischenprodukt_id=ids["sirup"]),
        RezeptPosition(D("0.1"), "l", artikel_id=ids["wasser"]),
    ))).id
    verpackung = tuple(VerpackungsPosition(ids[n]) for n in ("flasche", "verschluss", "etikett"))
    ids["sirup_flasche"] = db.speichere_endprodukt(
        Endprodukt(None, "Orangensirup 0,5 l", ids["sirup"], D("500"), verpackung)
    ).id
    ids["likoer_flasche"] = db.speichere_endprodukt(
        Endprodukt(None, "Orangenlikör 0,5 l", ids["likoer"], D("500"), verpackung)
    ).id
    return ids


def _artikel(db, artikel_id):
    return next(a for a in db.lade_artikel() if a.id == artikel_id)


def _rezept(db, rezept_id):
    return next(r for r in db.lade_rezepte() if r.id == rezept_id)


# --- Grundfunktionen -------------------------------------------------------------

def test_datei_und_ordner_werden_angelegt(tmp_path):
    pfad = tmp_path / "neu" / "kalkulation.db"
    Datenbank(pfad)
    assert pfad.exists()


def test_leere_datenbank(db):
    assert db.lade_artikel() == []
    assert db.lade_rezepte() == []
    assert db.lade_endprodukte() == []


def test_artikel_speichern_und_laden(db):
    gespeichert = db.speichere_artikel(
        Artikel(None, "  Zucker ", Kategorie.ZUTAT, D("1"), "kg", D("1.20"), "Großmarkt", "Notiz")
    )
    assert gespeichert.id is not None
    assert gespeichert.name == "Zucker"
    assert db.lade_artikel() == [gespeichert]


def test_namen_mit_leerzeichen(db):
    for name in ("Weißer Zucker", "Brauner Zucker", "Alkohol 96 %"):
        db.speichere_artikel(Artikel(None, name, Kategorie.ZUTAT, D("1"), "kg", D("1")))
    assert [a.name for a in db.lade_artikel()] == ["Alkohol 96 %", "Brauner Zucker", "Weißer Zucker"]


def test_dezimalwerte_bleiben_exakt(db):
    gespeichert = db.speichere_artikel(Artikel(None, "X", Kategorie.ZUTAT, D("0.1"), "l", D("0.30")))
    geladen = _artikel(db, gespeichert.id)
    assert geladen.gebinde_menge == D("0.1")
    assert str(geladen.gebinde_preis) == "0.30"


def test_daten_bleiben_nach_neustart_erhalten(tmp_path):
    pfad = tmp_path / "test.db"
    Datenbank(pfad).speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1.20")))
    assert [a.name for a in Datenbank(pfad).lade_artikel()] == ["Zucker"]


def test_artikel_aendern(db, beispiel):
    zucker = _artikel(db, beispiel["zucker"])
    db.speichere_artikel(Artikel(zucker.id, "Zucker fein", zucker.kategorie, D("2"), "kg", D("3.00")))
    geaendert = _artikel(db, beispiel["zucker"])
    assert geaendert.name == "Zucker fein"
    assert geaendert.gebinde_preis == D("3.00")


def test_unbekannte_id_aendern(db):
    with pytest.raises(ReferenzFehler):
        db.speichere_artikel(Artikel(999, "X", Kategorie.ZUTAT, D("1"), "kg", D("1")))


def test_doppelter_name(db):
    db.speichere_artikel(Artikel(None, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1")))
    with pytest.raises(DoppelterNameFehler):
        db.speichere_artikel(Artikel(None, "zucker", Kategorie.ZUTAT, D("1"), "kg", D("1")))


# --- Rezepte & Endprodukte -------------------------------------------------------

def test_rezept_mit_positionen_laden(db, beispiel):
    likoer = _rezept(db, beispiel["likoer"])
    assert [(p.artikel_id, p.zwischenprodukt_id, p.menge) for p in likoer.positionen] == [
        (beispiel["alkohol"], None, D("0.3")),
        (None, beispiel["sirup"], D("0.6")),
        (beispiel["wasser"], None, D("0.1")),
    ]


def test_rezept_aendern_ersetzt_positionen(db, beispiel):
    sirup = _rezept(db, beispiel["sirup"])
    db.speichere_rezept(Rezept(sirup.id, sirup.name, D("1"), "l", (
        RezeptPosition(D("1"), "kg", artikel_id=beispiel["zucker"]),
    )))
    geaendert = _rezept(db, beispiel["sirup"])
    assert len(geaendert.positionen) == 1
    assert geaendert.ausbeute_menge == D("1")


def test_beispielrechnung_aus_datenbank(db, beispiel):
    kalkulator = db.kalkulator()
    kosten = {e.name: kalkulator.endprodukt(e).herstellkosten for e in db.lade_endprodukte()}
    assert kosten == {"Orangenlikör 0,5 l": D("5.23"), "Orangensirup 0,5 l": D("1.90")}


def test_preisaenderung_wirkt_sofort(db, beispiel):
    zucker = _artikel(db, beispiel["zucker"])
    db.speichere_artikel(Artikel(zucker.id, zucker.name, zucker.kategorie, D("1"), "kg", D("2.20")))
    kalkulator = db.kalkulator()
    sirup = next(e for e in db.lade_endprodukte() if e.id == beispiel["sirup_flasche"])
    # Sirup: 5,20 € / 2 l → 1,30 € pro 0,5 l + 0,85 € Verpackung
    assert kalkulator.endprodukt(sirup).herstellkosten == D("2.15")


# --- Konsistenzprüfung beim Speichern --------------------------------------------

def test_zirkelbezug_wird_nicht_gespeichert(db, beispiel):
    sirup = _rezept(db, beispiel["sirup"])
    mit_kreis = Rezept(sirup.id, sirup.name, sirup.ausbeute_menge, sirup.ausbeute_einheit, (
        *sirup.positionen,
        RezeptPosition(D("0.1"), "l", zwischenprodukt_id=beispiel["likoer"]),
    ))
    with pytest.raises(ZirkelbezugFehler):
        db.speichere_rezept(mit_kreis)
    assert _rezept(db, beispiel["sirup"]) == sirup


def test_einheitenkonflikt_wird_nicht_gespeichert(db, beispiel):
    with pytest.raises(EinheitenFehler):
        db.speichere_rezept(Rezept(None, "Falsch", D("1"), "l", (
            RezeptPosition(D("500"), "ml", artikel_id=beispiel["zucker"]),
        )))
    assert "Falsch" not in [r.name for r in db.lade_rezepte()]


def test_artikelaenderung_die_rezepte_bricht_wird_abgelehnt(db, beispiel):
    zucker = _artikel(db, beispiel["zucker"])
    with pytest.raises(EinheitenFehler):
        db.speichere_artikel(Artikel(zucker.id, zucker.name, zucker.kategorie, D("1"), "l", D("1.20")))
    assert _artikel(db, beispiel["zucker"]) == zucker


def test_endprodukt_mit_masse_rezept_wird_abgelehnt(db, beispiel):
    gelee = db.speichere_rezept(Rezept(None, "Gelee", D("1"), "kg", (
        RezeptPosition(D("1"), "kg", artikel_id=beispiel["zucker"]),
    )))
    with pytest.raises(EinheitenFehler):
        db.speichere_endprodukt(Endprodukt(None, "Gelee-Glas", gelee.id, D("200")))
    assert "Gelee-Glas" not in [e.name for e in db.lade_endprodukte()]


def test_verweis_auf_unbekannten_artikel(db):
    with pytest.raises(ReferenzFehler):
        db.speichere_rezept(Rezept(None, "X", D("1"), "l", (RezeptPosition(D("1"), "l", artikel_id=999),)))
    assert db.lade_rezepte() == []


# --- Löschen ---------------------------------------------------------------------

def test_verwendeten_artikel_nicht_loeschen(db, beispiel):
    assert db.verwendungen_artikel(beispiel["wasser"]) == ["Rezept 'Orangenlikör'", "Rezept 'Orangensirup'"]
    with pytest.raises(InVerwendungFehler, match="Orangenlikör"):
        db.loesche_artikel(beispiel["wasser"])


def test_verwendete_verpackung_nicht_loeschen(db, beispiel):
    assert db.verwendungen_artikel(beispiel["flasche"]) == [
        "Endprodukt 'Orangenlikör 0,5 l'", "Endprodukt 'Orangensirup 0,5 l'",
    ]
    with pytest.raises(InVerwendungFehler):
        db.loesche_artikel(beispiel["flasche"])


def test_unbenutzten_artikel_loeschen(db):
    artikel = db.speichere_artikel(Artikel(None, "Zimt", Kategorie.ZUTAT, D("50"), "g", D("2")))
    db.loesche_artikel(artikel.id)
    assert db.lade_artikel() == []


def test_verwendetes_rezept_nicht_loeschen(db, beispiel):
    assert db.verwendungen_rezept(beispiel["sirup"]) == ["Rezept 'Orangenlikör'", "Endprodukt 'Orangensirup 0,5 l'"]
    with pytest.raises(InVerwendungFehler):
        db.loesche_rezept(beispiel["sirup"])


def test_loeschreihenfolge(db, beispiel):
    db.loesche_endprodukt(beispiel["likoer_flasche"])
    db.loesche_rezept(beispiel["likoer"])
    assert [r.name for r in db.lade_rezepte()] == ["Orangensirup"]
    # Positionen des Likörs sind mitgelöscht, Alkohol ist jetzt frei
    db.loesche_artikel(beispiel["alkohol"])


def test_unbekannte_id_loeschen(db):
    with pytest.raises(ReferenzFehler):
        db.loesche_endprodukt(999)


# --- Duplizieren -----------------------------------------------------------------

def test_rezept_duplizieren(db, beispiel):
    original = _rezept(db, beispiel["likoer"])
    kopie = db.dupliziere_rezept(original.id)
    assert kopie.id != original.id
    assert kopie.name == "Orangenlikör (Kopie)"
    assert _rezept(db, kopie.id).positionen == original.positionen
    assert db.kalkulator().rezept(kopie.id).chargenkosten == D("8.76")


def test_mehrfach_duplizieren_zaehlt_hoch(db, beispiel):
    namen = [db.dupliziere_rezept(beispiel["sirup"]).name for _ in range(3)]
    assert namen == ["Orangensirup (Kopie)", "Orangensirup (Kopie 2)", "Orangensirup (Kopie 3)"]


def test_unbekanntes_rezept_duplizieren(db):
    with pytest.raises(ReferenzFehler):
        db.dupliziere_rezept(999)
