from decimal import Decimal

import pytest

from kalkulation.anzeige import (
    einzelpreis,
    euro,
    menge_text,
    preis_je_anzeigeeinheit,
    preise_je_einheit,
    preise_je_einheit_text,
    zahl,
)
from kalkulation.einheiten import einheiten_der_gruppe

D = Decimal


@pytest.mark.parametrize(
    ("menge", "einheit", "erwartet"),
    [
        ("13000", "kg", "13 kg"),
        ("6500", "g", "6,5 kg"),
        ("500", "kg", "500 g"),
        ("7000", "ml", "7 l"),
        ("250", "l", "250 ml"),
        ("333.33333", "l", "333,333 ml"),
        ("30", "Stk", "30 Stk"),
        ("0.5", "Stk", "0,5 Stk"),
    ],
)
def test_menge_text(menge, einheit, erwartet):
    assert menge_text(D(menge), einheit) == erwartet


@pytest.mark.parametrize(
    ("betrag", "erwartet"),
    [
        ("0", "0,00 €"),
        ("2.1", "2,10 €"),
        ("0.6", "0,60 €"),
        ("0.0021", "0,0021 €"),
        ("0.025", "0,025 €"),
        ("0.05", "0,05 €"),
        ("0.00876", "0,0088 €"),
        ("0.00004", "0,00004 €"),
        ("0.0000001", "0,00 €"),
    ],
)
def test_einzelpreis(betrag, erwartet):
    assert einzelpreis(D(betrag)) == erwartet


@pytest.mark.parametrize(
    ("einheit", "erwartet"),
    [("l", ("ml", "cl", "l")), ("g", ("g", "kg")), ("kg", ("g", "kg")), ("Stk", ("Stk",))],
)
def test_einheiten_der_gruppe(einheit, erwartet):
    assert einheiten_der_gruppe(einheit) == erwartet


def test_preise_je_einheit_volumen():
    assert preise_je_einheit(D("0.0021"), "l") == [(D("0.0021"), "ml"), (D("0.021"), "cl"), (D("2.1"), "l")]


def test_preise_je_einheit_stueck():
    assert preise_je_einheit(D("0.35"), "Stk") == [(D("0.35"), "Stk")]


def test_preise_je_einheit_text():
    assert preise_je_einheit_text(D("0.0015"), "kg") == "0,0015 €/g · 1,50 €/kg"


@pytest.mark.parametrize(
    ("betrag", "max_stellen", "erwartet"),
    [
        ("1.5", 2, "1,50 €"),
        ("0", 2, "0,00 €"),
        ("1234.567", 2, "1.234,57 €"),
        ("0.005", 2, "0,01 €"),
        ("0.6", 4, "0,60 €"),
        ("0.004", 4, "0,004 €"),
        ("0.00123456", 4, "0,0012 €"),
        ("1500", 4, "1.500,00 €"),
    ],
)
def test_euro(betrag, max_stellen, erwartet):
    assert euro(D(betrag), max_stellen) == erwartet


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [("0.500", "0,5"), ("10", "10"), ("10.000", "10"), ("2500", "2.500"), ("0", "0"), ("1.25", "1,25")],
)
def test_zahl(wert, erwartet):
    assert zahl(D(wert)) == erwartet


@pytest.mark.parametrize(
    ("preis", "einheit", "erwartet"),
    [
        ("0.0015", "kg", (D("1.5"), "kg")),
        ("0.025", "ml", (D("25"), "l")),
        ("0.60", "Stk", (D("0.60"), "Stk")),
    ],
)
def test_preis_je_anzeigeeinheit(preis, einheit, erwartet):
    assert preis_je_anzeigeeinheit(D(preis), einheit) == erwartet
