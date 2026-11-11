from decimal import Decimal

import pandas as pd

from kalkulation.modelle import Artikel, Kategorie, Rezept, RezeptPosition, VerpackungsPosition
from oberflaeche import (
    Quelle,
    positionen_aus_tabelle,
    quellen,
    tabelle_aus_positionen,
    tabelle_aus_verpackung,
    verpackung_aus_tabelle,
    verpackungs_optionen,
)

D = Decimal

ARTIKEL = [
    Artikel(1, "Weißer Zucker", Kategorie.ZUTAT, D("1"), "kg", D("1.20")),
    Artikel(2, "Wasser", Kategorie.ZUTAT, D("1"), "l", D("0")),
]
REZEPTE = [
    Rezept(10, "Sirup", D("2"), "l"),
    Rezept(11, "Likör", D("1"), "l"),
]


def test_quellen_ohne_aktuelles_rezept():
    ergebnis = quellen(ARTIKEL, REZEPTE, ohne_rezept_id=11)
    assert ergebnis == {
        "Weißer Zucker": Quelle(1, None, "kg"),
        "Wasser": Quelle(2, None, "l"),
        "Sirup (Rezept)": Quelle(None, 10, "l"),
    }


def test_tabelle_hin_und_zurueck():
    q = quellen(ARTIKEL, REZEPTE, ohne_rezept_id=None)
    positionen = [
        RezeptPosition(D("500"), "g", artikel_id=1),
        RezeptPosition(D("0.6"), "l", zwischenprodukt_id=10),
    ]
    tabelle = tabelle_aus_positionen(positionen, q)
    assert list(tabelle["Zutat"]) == ["Weißer Zucker", "Sirup (Rezept)"]
    assert positionen_aus_tabelle(tabelle, q) == (positionen, [])


def test_leere_tabelle():
    tabelle = tabelle_aus_positionen([], {})
    assert list(tabelle.columns) == ["Zutat", "Menge", "Einheit"]
    assert positionen_aus_tabelle(tabelle, {}) == ([], [])


def test_leere_einheit_nimmt_einkaufseinheit():
    q = quellen(ARTIKEL, REZEPTE, ohne_rezept_id=None)
    tabelle = pd.DataFrame([{"Zutat": "Weißer Zucker", "Menge": 0.5, "Einheit": None}])
    [position], fehler = positionen_aus_tabelle(tabelle, q)
    assert fehler == []
    assert (position.menge, position.einheit) == (D("0.5"), "kg")


def test_float_artefakte_werden_gerundet():
    q = quellen(ARTIKEL, REZEPTE, ohne_rezept_id=None)
    tabelle = pd.DataFrame([{"Zutat": "Wasser", "Menge": 0.1 + 0.2, "Einheit": "l"}])
    [position], _ = positionen_aus_tabelle(tabelle, q)
    assert position.menge == D("0.300")


def test_fehler_je_zeile():
    q = quellen(ARTIKEL, REZEPTE, ohne_rezept_id=None)
    tabelle = pd.DataFrame([
        {"Zutat": None, "Menge": None, "Einheit": None},          # komplett leer: ignoriert
        {"Zutat": None, "Menge": 1.0, "Einheit": "l"},            # Zutat fehlt
        {"Zutat": "Wasser", "Menge": float("nan"), "Einheit": "l"},  # Menge fehlt
        {"Zutat": "Wasser", "Menge": 0.0, "Einheit": "l"},        # Menge 0
        {"Zutat": "Gibt es nicht", "Menge": 1.0, "Einheit": "l"},  # unbekannte Zutat
        {"Zutat": "Wasser", "Menge": 1.0, "Einheit": "l"},        # gültig
    ])
    positionen, fehler = positionen_aus_tabelle(tabelle, q)
    assert len(positionen) == 1
    assert [f.split(":")[0] for f in fehler] == ["Zeile 2", "Zeile 3 (Wasser)", "Zeile 4 (Wasser)", "Zeile 5"]


# --- Verpackung ------------------------------------------------------------------

VERPACKUNGEN = [
    Artikel(20, "Flasche 0,5 l", Kategorie.VERPACKUNG, D("100"), "Stk", D("60")),
    Artikel(21, "Etikett", Kategorie.VERPACKUNG, D("100"), "Stk", D("15")),
    Artikel(22, "Folie", Kategorie.VERPACKUNG, D("10"), "g", D("1")),
]


def test_verpackungs_optionen_nur_verpackung_in_stueck():
    assert verpackungs_optionen([*ARTIKEL, *VERPACKUNGEN]) == {"Flasche 0,5 l": 20, "Etikett": 21}


def test_verpackung_hin_und_zurueck():
    optionen = verpackungs_optionen(VERPACKUNGEN)
    verpackung = [VerpackungsPosition(20, D("1")), VerpackungsPosition(21, D("2"))]
    tabelle = tabelle_aus_verpackung(verpackung, optionen)
    assert list(tabelle["Verpackung"]) == ["Flasche 0,5 l", "Etikett"]
    assert verpackung_aus_tabelle(tabelle, optionen) == (verpackung, [])


def test_verpackung_leere_tabelle():
    tabelle = tabelle_aus_verpackung([], {})
    assert list(tabelle.columns) == ["Verpackung", "Anzahl"]
    assert verpackung_aus_tabelle(tabelle, {}) == ([], [])


def test_verpackung_fehler_und_standardanzahl():
    optionen = verpackungs_optionen(VERPACKUNGEN)
    tabelle = pd.DataFrame([
        {"Verpackung": None, "Anzahl": None},             # komplett leer: ignoriert
        {"Verpackung": "Etikett", "Anzahl": None},        # Anzahl leer → 1
        {"Verpackung": None, "Anzahl": 2.0},              # Verpackung fehlt
        {"Verpackung": "Etikett", "Anzahl": 0.0},         # Anzahl 0
    ])
    verpackung, fehler = verpackung_aus_tabelle(tabelle, optionen)
    assert verpackung == [VerpackungsPosition(21, D("1"))]
    assert [f.split(":")[0] for f in fehler] == ["Verpackung Zeile 3", "Verpackung Zeile 4 (Etikett)"]
