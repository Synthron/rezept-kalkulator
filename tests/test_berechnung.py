from decimal import Decimal

import pytest

from kalkulation.berechnung import (
    EinkaufsPosition,
    Kalkulator,
    ReferenzFehler,
    ZirkelbezugFehler,
    mengen_summe,
    preis_pro_basiseinheit,
)
from kalkulation.einheiten import EinheitenFehler, Gruppe
from kalkulation.modelle import (
    Artikel,
    Endprodukt,
    Kategorie,
    Rezept,
    RezeptPosition,
    VerpackungsPosition,
)

D = Decimal

# Beispieldaten aus der README, Abschnitt „Beispielrechnung“
ORANGEN, ZUCKER, WASSER, ALKOHOL, FLASCHE, VERSCHLUSS, ETIKETT, ORANGEN_STK = range(1, 9)
SIRUP, LIKOER, SAFT = range(1, 4)

ARTIKEL = [
    Artikel(ORANGEN, "Orangen", Kategorie.ZUTAT, D("10"), "kg", D("15.00")),
    Artikel(ZUCKER, "Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1.20")),
    Artikel(WASSER, "Wasser", Kategorie.ZUTAT, D("1"), "l", D("0")),
    Artikel(ALKOHOL, "Alkohol 96 %", Kategorie.ZUTAT, D("1"), "l", D("25.00")),
    Artikel(FLASCHE, "Flasche 0,5 l", Kategorie.VERPACKUNG, D("100"), "Stk", D("60.00")),
    Artikel(VERSCHLUSS, "Verschluss", Kategorie.VERPACKUNG, D("100"), "Stk", D("10.00")),
    Artikel(ETIKETT, "Etikett", Kategorie.VERPACKUNG, D("100"), "Stk", D("15.00")),
    Artikel(ORANGEN_STK, "Orangen (Stück)", Kategorie.ZUTAT, D("20"), "Stk", D("8.00")),
]

REZEPTE = [
    Rezept(SIRUP, "Orangensirup", D("2"), "l", (
        RezeptPosition(D("2"), "kg", artikel_id=ORANGEN),
        RezeptPosition(D("1"), "kg", artikel_id=ZUCKER),
        RezeptPosition(D("1"), "l", artikel_id=WASSER),
    )),
    Rezept(LIKOER, "Orangenlikör", D("1"), "l", (
        RezeptPosition(D("0.3"), "l", artikel_id=ALKOHOL),
        RezeptPosition(D("0.6"), "l", zwischenprodukt_id=SIRUP),
        RezeptPosition(D("0.1"), "l", artikel_id=WASSER),
    )),
    Rezept(SAFT, "Orangensaft", D("800"), "ml", (
        RezeptPosition(D("10"), "Stk", artikel_id=ORANGEN_STK),
    )),
]

VERPACKUNG = (
    VerpackungsPosition(FLASCHE),
    VerpackungsPosition(VERSCHLUSS),
    VerpackungsPosition(ETIKETT),
)


@pytest.fixture
def kalkulator():
    return Kalkulator(ARTIKEL, REZEPTE)


# --- Einkaufsartikel -------------------------------------------------------------

@pytest.mark.parametrize(
    ("artikel_id", "erwartet"),
    [
        (ORANGEN, "0.0015"),
        (ZUCKER, "0.0012"),
        (WASSER, "0"),
        (ALKOHOL, "0.025"),
        (FLASCHE, "0.60"),
        (VERSCHLUSS, "0.10"),
        (ETIKETT, "0.15"),
        (ORANGEN_STK, "0.40"),
    ],
)
def test_preis_pro_basiseinheit(artikel_id, erwartet):
    artikel = next(a for a in ARTIKEL if a.id == artikel_id)
    assert preis_pro_basiseinheit(artikel) == D(erwartet)


# --- Rezepte ---------------------------------------------------------------------

def test_rezept_orangensirup(kalkulator):
    ergebnis = kalkulator.rezept(SIRUP)
    assert [p.kosten for p in ergebnis.positionen] == [D("3.00"), D("1.20"), D("0")]
    assert ergebnis.chargenkosten == D("4.20")
    assert ergebnis.preis_pro_basiseinheit * 1000 == D("2.10")
    assert ergebnis.basiseinheit == "ml"


def test_rezept_mit_zwischenprodukt(kalkulator):
    ergebnis = kalkulator.rezept(LIKOER)
    assert [p.name for p in ergebnis.positionen] == ["Alkohol 96 %", "Orangensirup", "Wasser"]
    assert [p.kosten for p in ergebnis.positionen] == [D("7.50"), D("1.26"), D("0")]
    assert ergebnis.chargenkosten == D("8.76")
    assert ergebnis.preis_pro_basiseinheit * 1000 == D("8.76")


def test_einheitenwechsel_stueck_zu_ml(kalkulator):
    saft = kalkulator.rezept(SAFT)
    assert saft.chargenkosten == D("4.00")
    assert saft.preis_pro_basiseinheit * 1000 == D("5.00")
    assert saft.basiseinheit == "ml"
    assert D("500") * saft.preis_pro_basiseinheit == D("2.50")


def test_rezept_ohne_positionen_kostet_nichts():
    kalk = Kalkulator([], [Rezept(1, "Leer", D("1"), "l")])
    assert kalk.rezept(1).chargenkosten == 0


def test_einheitenkonflikt_bei_artikel():
    rezept = Rezept(99, "Falsch", D("1"), "l", (RezeptPosition(D("500"), "ml", artikel_id=ZUCKER),))
    with pytest.raises(EinheitenFehler, match="Zucker"):
        Kalkulator(ARTIKEL, [rezept]).rezept(99)


def test_einheitenkonflikt_bei_zwischenprodukt():
    rezept = Rezept(99, "Falsch", D("1"), "l", (RezeptPosition(D("100"), "g", zwischenprodukt_id=SIRUP),))
    with pytest.raises(EinheitenFehler, match="Orangensirup"):
        Kalkulator(ARTIKEL, [*REZEPTE, rezept]).rezept(99)


def test_zirkelbezug_zwei_rezepte():
    a = Rezept(10, "A", D("1"), "l", (RezeptPosition(D("1"), "l", zwischenprodukt_id=11),))
    b = Rezept(11, "B", D("1"), "l", (RezeptPosition(D("1"), "l", zwischenprodukt_id=10),))
    with pytest.raises(ZirkelbezugFehler, match="A → B → A"):
        Kalkulator([], [a, b]).rezept(10)


def test_zirkelbezug_auf_sich_selbst():
    a = Rezept(10, "A", D("1"), "l", (RezeptPosition(D("1"), "l", zwischenprodukt_id=10),))
    with pytest.raises(ZirkelbezugFehler, match="A → A"):
        Kalkulator([], [a]).rezept(10)


def test_unbekannter_artikel():
    rezept = Rezept(1, "X", D("1"), "l", (RezeptPosition(D("1"), "l", artikel_id=999),))
    with pytest.raises(ReferenzFehler, match="999"):
        Kalkulator([], [rezept]).rezept(1)


def test_unbekanntes_rezept(kalkulator):
    with pytest.raises(ReferenzFehler, match="999"):
        kalkulator.rezept(999)


# --- Endprodukte -----------------------------------------------------------------

def test_endprodukt_orangensirup(kalkulator):
    ergebnis = kalkulator.endprodukt(Endprodukt(1, "Orangensirup 0,5 l", SIRUP, D("500"), VERPACKUNG))
    assert ergebnis.inhaltskosten == D("1.05")
    assert ergebnis.verpackungskosten == D("0.85")
    assert ergebnis.herstellkosten == D("1.90")


def test_endprodukt_orangenlikoer(kalkulator):
    ergebnis = kalkulator.endprodukt(Endprodukt(2, "Orangenlikör 0,5 l", LIKOER, D("500"), VERPACKUNG))
    assert ergebnis.inhaltskosten == D("4.38")
    assert ergebnis.verpackungskosten == D("0.85")
    assert ergebnis.herstellkosten == D("5.23")


def test_endprodukt_verpackungsanzahl(kalkulator):
    endprodukt = Endprodukt(3, "Doppel-Etikett", SIRUP, D("500"), (VerpackungsPosition(ETIKETT, D("2")),))
    assert kalkulator.endprodukt(endprodukt).verpackungskosten == D("0.30")


def test_endprodukt_verpackung_je_position(kalkulator):
    ergebnis = kalkulator.endprodukt(Endprodukt(1, "Orangensirup 0,5 l", SIRUP, D("500"), VERPACKUNG))
    assert [(v.name, v.kosten) for v in ergebnis.verpackung] == [
        ("Flasche 0,5 l", D("0.60")),
        ("Verschluss", D("0.10")),
        ("Etikett", D("0.15")),
    ]


def test_endprodukt_braucht_volumen_ausbeute():
    rezept = Rezept(1, "Gelee", D("1"), "kg", (RezeptPosition(D("1"), "kg", artikel_id=ZUCKER),))
    with pytest.raises(EinheitenFehler, match="Volumen"):
        Kalkulator(ARTIKEL, [rezept]).endprodukt(Endprodukt(1, "Gelee-Glas", 1, D("200")))


def test_endprodukt_verpackung_muss_verpackung_sein(kalkulator):
    endprodukt = Endprodukt(1, "X", SIRUP, D("500"), (VerpackungsPosition(ZUCKER),))
    with pytest.raises(ValueError, match="keine Verpackung"):
        kalkulator.endprodukt(endprodukt)


def test_endprodukt_verpackung_muss_in_stueck_sein():
    folie = Artikel(50, "Folie", Kategorie.VERPACKUNG, D("10"), "g", D("1"))
    rezept = Rezept(1, "R", D("1"), "l")
    endprodukt = Endprodukt(1, "X", 1, D("500"), (VerpackungsPosition(50),))
    with pytest.raises(EinheitenFehler, match="Stk"):
        Kalkulator([folie], [rezept]).endprodukt(endprodukt)


# --- Hochrechnung & Einkaufsliste ------------------------------------------------

SIRUP_FLASCHE = Endprodukt(1, "Orangensirup 0,5 l", SIRUP, D("500"), VERPACKUNG)
LIKOER_FLASCHE = Endprodukt(2, "Orangenlikör 0,5 l", LIKOER, D("500"), VERPACKUNG)


def test_bedarf_fuer_endprodukte(kalkulator):
    # 20 × 0,5 l Sirup + 10 × 0,5 l Likör; der Likör braucht zusätzlich 3 l Sirup
    bedarf = kalkulator.bedarf([(SIRUP_FLASCHE, D(20)), (LIKOER_FLASCHE, D(10))])
    assert bedarf.rezepte == {SIRUP: D("13000"), LIKOER: D("5000")}
    assert bedarf.artikel == {
        ORANGEN: D("13000"),
        ZUCKER: D("6500"),
        WASSER: D("7000"),
        ALKOHOL: D("1500"),
        FLASCHE: D("30"),
        VERSCHLUSS: D("30"),
        ETIKETT: D("30"),
    }


def test_einkaufsliste(kalkulator):
    bedarf = kalkulator.bedarf([(SIRUP_FLASCHE, D(20)), (LIKOER_FLASCHE, D(10))])
    liste = kalkulator.einkaufsliste(bedarf)
    assert [(p.artikel.name, p.gebinde_anzahl, p.einkaufskosten) for p in liste] == [
        ("Alkohol 96 %", 2, D("50.00")),
        ("Orangen", 2, D("30.00")),
        ("Wasser", 7, D("0")),
        ("Zucker", 7, D("8.40")),
        ("Etikett", 1, D("15.00")),
        ("Flasche 0,5 l", 1, D("60.00")),
        ("Verschluss", 1, D("10.00")),
    ]
    # Verbrauch = Herstellkosten je Gebinde × Anzahl: 20 × 1,90 € + 10 × 5,23 €
    assert sum(p.verbrauchskosten for p in liste) == D("90.30")


def test_bedarf_fuer_rezept_direkt(kalkulator):
    bedarf = kalkulator.bedarf(rezepte=[(SAFT, D("2000"))])
    assert bedarf.artikel == {ORANGEN_STK: D("25")}
    assert kalkulator.einkaufsliste(bedarf)[0].gebinde_anzahl == 2


def test_gebinde_anzahl_ignoriert_rechenreste():
    zucker = next(a for a in ARTIKEL if a.id == ZUCKER)
    assert EinkaufsPosition(zucker, D("1000.0000000000000000000001")).gebinde_anzahl == 1
    assert EinkaufsPosition(zucker, D("1000.01")).gebinde_anzahl == 2
    assert EinkaufsPosition(zucker, D("0")).gebinde_anzahl == 0


def test_bedarf_prueft_endprodukt():
    rezept = Rezept(1, "Gelee", D("1"), "kg")
    with pytest.raises(EinheitenFehler):
        Kalkulator([], [rezept]).bedarf([(Endprodukt(1, "Glas", 1, D("200")), D(5))])


# --- Ausbeute-Vorschlag ----------------------------------------------------------

def test_mengen_summe_gleiche_gruppe():
    positionen = [RezeptPosition(D("0.3"), "l", artikel_id=1), RezeptPosition(D("70"), "cl", artikel_id=2)]
    assert mengen_summe(positionen) == (D("1000"), Gruppe.VOLUMEN)


def test_mengen_summe_gemischte_gruppen():
    positionen = [RezeptPosition(D("1"), "kg", artikel_id=1), RezeptPosition(D("1"), "l", artikel_id=2)]
    assert mengen_summe(positionen) is None


def test_mengen_summe_leer():
    assert mengen_summe([]) is None


# --- Eingabeprüfung der Modelle --------------------------------------------------

def test_modelle_wandeln_zahlen_in_decimal():
    artikel = Artikel(1, "Zucker", "zutat", 1, "kg", 1.2)
    assert artikel.gebinde_preis == D("1.2")
    assert artikel.kategorie is Kategorie.ZUTAT


@pytest.mark.parametrize(
    "erzeuge",
    [
        lambda: Artikel(1, "", Kategorie.ZUTAT, D("1"), "kg", D("1")),
        lambda: Artikel(1, "X", Kategorie.ZUTAT, D("0"), "kg", D("1")),
        lambda: Artikel(1, "X", Kategorie.ZUTAT, D("1"), "kg", D("-1")),
        lambda: Artikel(1, "X", "unbekannt", D("1"), "kg", D("1")),
        lambda: Artikel(1, "X", Kategorie.ZUTAT, D("1"), "kg", "abc"),
        lambda: Artikel(1, "X", Kategorie.ZUTAT, D("NaN"), "kg", D("1")),
        lambda: RezeptPosition(D("1"), "l"),
        lambda: RezeptPosition(D("1"), "l", artikel_id=1, zwischenprodukt_id=2),
        lambda: RezeptPosition(D("0"), "l", artikel_id=1),
        lambda: Rezept(1, "R", D("0"), "l"),
        lambda: Endprodukt(1, "E", 1, D("0")),
        lambda: VerpackungsPosition(1, D("0")),
    ],
)
def test_ungueltige_eingaben(erzeuge):
    with pytest.raises(ValueError):
        erzeuge()


def test_unbekannte_einheit_im_modell():
    with pytest.raises(EinheitenFehler):
        Artikel(1, "X", Kategorie.ZUTAT, D("1"), "Liter", D("1"))
