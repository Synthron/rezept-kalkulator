import json
from decimal import Decimal

import pytest

from kalkulation.austausch import FORMAT, ImportFehler, paket_aus_json
from kalkulation.berechnung import ReferenzFehler, ZirkelbezugFehler
from kalkulation.datenbank import Datenbank
from kalkulation.einheiten import EinheitenFehler
from kalkulation.modelle import Artikel, Kategorie, Rezept, RezeptPosition

D = Decimal


@pytest.fixture
def quelle(tmp_path):
    """Datenbank mit Orangensirup und -likör (Likör nutzt Sirup als Zwischenprodukt)."""
    db = Datenbank(tmp_path / "quelle.db")

    def artikel(name, menge, einheit, preis, lieferant=""):
        return db.speichere_artikel(Artikel(None, name, Kategorie.ZUTAT, D(menge), einheit, D(preis), lieferant)).id

    orangen = artikel("Orangen", "10", "kg", "15.00", "Großmarkt")
    zucker = artikel("Weißer Zucker", "1", "kg", "1.20")
    wasser = artikel("Wasser", "1", "l", "0")
    alkohol = artikel("Alkohol 96 %", "1", "l", "25.00")
    artikel("Zimt", "50", "g", "2.00")  # wird von keinem exportierten Rezept verwendet
    sirup = db.speichere_rezept(Rezept(None, "Orangensirup", D("2"), "l", (
        RezeptPosition(D("2"), "kg", artikel_id=orangen),
        RezeptPosition(D("1"), "kg", artikel_id=zucker),
        RezeptPosition(D("1"), "l", artikel_id=wasser),
    ), "Schalen mitkochen"))
    likoer = db.speichere_rezept(Rezept(None, "Orangenlikör", D("1"), "l", (
        RezeptPosition(D("0.3"), "l", artikel_id=alkohol),
        RezeptPosition(D("0.6"), "l", zwischenprodukt_id=sirup.id),
        RezeptPosition(D("0.1"), "l", artikel_id=wasser),
    )))
    return db, sirup, likoer


@pytest.fixture
def ziel(tmp_path):
    return Datenbank(tmp_path / "ziel.db")


def ueber_json(daten: dict) -> dict:
    """Simuliert Schreiben und Lesen der Datei."""
    return json.loads(json.dumps(daten, ensure_ascii=False))


def kosten_je_liter(db: Datenbank) -> dict[str, Decimal]:
    kalkulator = db.kalkulator()
    return {r.name: kalkulator.rezept(r.id).preis_pro_basiseinheit * 1000 for r in db.lade_rezepte()}


# --- Export ----------------------------------------------------------------------

def test_export_enthaelt_zwischenprodukte_und_benoetigte_artikel(quelle):
    db, _, likoer = quelle
    daten = db.exportiere_rezepte([likoer.id])
    assert daten["format"] == FORMAT
    assert [r["name"] for r in daten["rezepte"]] == ["Orangensirup", "Orangenlikör"]
    assert [a["name"] for a in daten["artikel"]] == ["Alkohol 96 %", "Orangen", "Wasser", "Weißer Zucker"]
    assert daten["rezepte"][1]["positionen"][1] == {"zwischenprodukt": "Orangensirup", "menge": "0.6", "einheit": "l"}
    assert daten["artikel"][1]["gebinde_preis"] == "15.00"


def test_export_ohne_doppelte_rezepte(quelle):
    db, sirup, likoer = quelle
    daten = db.exportiere_rezepte([sirup.id, likoer.id])
    assert [r["name"] for r in daten["rezepte"]] == ["Orangensirup", "Orangenlikör"]


# --- Import ----------------------------------------------------------------------

def test_export_und_import_in_leere_datenbank(quelle, ziel):
    db, _, likoer = quelle
    bericht = ziel.importiere(paket_aus_json(ueber_json(db.exportiere_rezepte([likoer.id]))))

    assert bericht.rezepte_neu == ["Orangensirup", "Orangenlikör"]
    assert len(bericht.artikel_neu) == 4
    assert bericht.artikel_vorhanden == bericht.rezepte_vorhanden == []
    assert kosten_je_liter(ziel) == {"Orangenlikör": D("8.76"), "Orangensirup": D("2.10")}
    sirup = next(r for r in ziel.lade_rezepte() if r.name == "Orangensirup")
    assert sirup.notiz == "Schalen mitkochen"
    assert next(a for a in ziel.lade_artikel() if a.name == "Orangen").lieferant == "Großmarkt"


def test_vorhandene_artikel_werden_verwendet_nicht_ueberschrieben(quelle, ziel):
    db, _, likoer = quelle
    ziel.speichere_artikel(Artikel(None, "alkohol 96 %", Kategorie.ZUTAT, D("1"), "l", D("30.00")))
    bericht = ziel.importiere(paket_aus_json(db.exportiere_rezepte([likoer.id])))

    assert bericht.artikel_vorhanden == ["Alkohol 96 %"]
    assert next(a for a in ziel.lade_artikel() if a.name == "alkohol 96 %").gebinde_preis == D("30.00")
    # 0,3 l × 30 €/l + 1,26 € Sirup
    assert kosten_je_liter(ziel)["Orangenlikör"] == D("10.26")


def test_vorhandene_rezepte_werden_uebersprungen(quelle):
    db, _, likoer = quelle
    vorher = db.lade_rezepte()
    bericht = db.importiere(paket_aus_json(db.exportiere_rezepte([likoer.id])))
    assert bericht.rezepte_vorhanden == ["Orangensirup", "Orangenlikör"]
    assert bericht.rezepte_neu == bericht.artikel_neu == []
    assert db.lade_rezepte() == vorher


def test_nur_pruefen_aendert_nichts(quelle, ziel):
    db, _, likoer = quelle
    bericht = ziel.importiere(paket_aus_json(db.exportiere_rezepte([likoer.id])), nur_pruefen=True)
    assert bericht.rezepte_neu == ["Orangensirup", "Orangenlikör"]
    assert ziel.lade_rezepte() == []
    assert ziel.lade_artikel() == []


def test_reihenfolge_in_datei_egal(quelle, ziel):
    db, _, likoer = quelle
    daten = db.exportiere_rezepte([likoer.id])
    daten["rezepte"].reverse()
    ziel.importiere(paket_aus_json(daten))
    assert set(kosten_je_liter(ziel)) == {"Orangensirup", "Orangenlikör"}


def test_import_ist_alles_oder_nichts(quelle, ziel):
    db, _, likoer = quelle
    # Vorhandener Zucker in l passt nicht zum Rezept (kg) → gesamter Import wird zurückgerollt
    ziel.speichere_artikel(Artikel(None, "Weißer Zucker", Kategorie.ZUTAT, D("1"), "l", D("1")))
    with pytest.raises(EinheitenFehler):
        ziel.importiere(paket_aus_json(db.exportiere_rezepte([likoer.id])))
    assert ziel.lade_rezepte() == []
    assert [a.name for a in ziel.lade_artikel()] == ["Weißer Zucker"]


def test_fehlender_artikel(quelle, ziel):
    db, _, likoer = quelle
    daten = db.exportiere_rezepte([likoer.id])
    daten["artikel"] = [a for a in daten["artikel"] if a["name"] != "Wasser"]
    with pytest.raises(ReferenzFehler, match="Wasser"):
        ziel.importiere(paket_aus_json(daten))


def test_fehlendes_zwischenprodukt(quelle, ziel):
    db, _, likoer = quelle
    daten = db.exportiere_rezepte([likoer.id])
    daten["rezepte"] = [r for r in daten["rezepte"] if r["name"] != "Orangensirup"]
    with pytest.raises(ReferenzFehler, match="Orangensirup"):
        ziel.importiere(paket_aus_json(daten))


def test_zirkelbezug_in_datei(ziel):
    daten = {
        "format": FORMAT, "version": 1, "artikel": [],
        "rezepte": [
            {"name": "A", "ausbeute_menge": "1", "ausbeute_einheit": "l",
             "positionen": [{"zwischenprodukt": "B", "menge": "1", "einheit": "l"}]},
            {"name": "B", "ausbeute_menge": "1", "ausbeute_einheit": "l",
             "positionen": [{"zwischenprodukt": "A", "menge": "1", "einheit": "l"}]},
        ],
    }
    with pytest.raises(ZirkelbezugFehler):
        ziel.importiere(paket_aus_json(daten))
    assert ziel.lade_rezepte() == []


# --- Prüfung der Datei -----------------------------------------------------------

GUELTIG = {
    "format": FORMAT,
    "version": 1,
    "artikel": [{"name": "Zucker", "kategorie": "zutat", "gebinde_menge": "1", "gebinde_einheit": "kg",
                 "gebinde_preis": "1.20"}],
    "rezepte": [{"name": "Sirup", "ausbeute_menge": 1, "ausbeute_einheit": "l",
                 "positionen": [{"artikel": "Zucker", "menge": 0.5, "einheit": "kg"}]}],
}


def test_minimale_datei_mit_zahlen_als_json_zahl():
    paket = paket_aus_json(GUELTIG)
    assert paket.artikel[0].gebinde_preis == D("1.20")
    assert paket.rezepte[0].positionen[0].menge == D("0.5")


def mit(**aenderungen) -> dict:
    return {**GUELTIG, **aenderungen}


@pytest.mark.parametrize(
    ("daten", "meldung"),
    [
        ([], "keine Rezept-Exportdatei"),
        ({"format": "anderes"}, "keine Rezept-Exportdatei"),
        (mit(version=2), "Dateiversion"),
        (mit(artikel="x"), "Liste"),
        (mit(artikel=[{"name": "Zucker"}]), "kategorie"),
        (mit(artikel=[{**GUELTIG["artikel"][0], "gebinde_einheit": "Liter"}]), "Unbekannte Einheit"),
        (mit(artikel=[{**GUELTIG["artikel"][0], "gebinde_preis": "-1"}]), "Gebindepreis"),
        (mit(artikel=[{**GUELTIG["artikel"][0], "gebinde_menge": True}]), "keine Zahl"),
        (mit(artikel=GUELTIG["artikel"] * 2), "mehrfach"),
        (mit(rezepte=[{"name": "Sirup", "ausbeute_menge": "0", "ausbeute_einheit": "l"}]), "Ausbeute"),
        (mit(rezepte=[{**GUELTIG["rezepte"][0], "positionen": [{"menge": "1", "einheit": "l"}]}]), "genau"),
        (mit(rezepte=[{**GUELTIG["rezepte"][0],
                        "positionen": [{"artikel": "Zucker", "menge": "abc", "einheit": "kg"}]}]), "Zahl"),
        (mit(rezepte=[{**GUELTIG["rezepte"][0], "positionen": ["x"]}]), "ungültiger Eintrag"),
    ],
)
def test_ungueltige_dateien(daten, meldung):
    with pytest.raises(ImportFehler, match=meldung):
        paket_aus_json(daten)
