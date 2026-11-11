from decimal import Decimal

import pytest

from kalkulation.einheiten import EINHEITEN, EinheitenFehler, Gruppe, basiseinheit, gruppe, in_basis


@pytest.mark.parametrize(
    ("menge", "einheit", "erwartet"),
    [
        ("2", "kg", "2000"),
        ("250", "g", "250"),
        ("0.7", "l", "700"),
        ("4", "cl", "40"),
        ("100", "ml", "100"),
        ("3", "Stk", "3"),
    ],
)
def test_in_basis(menge, einheit, erwartet):
    assert in_basis(Decimal(menge), einheit) == Decimal(erwartet)


@pytest.mark.parametrize(
    ("einheit", "erwartete_gruppe", "erwartete_basis"),
    [
        ("kg", Gruppe.MASSE, "g"),
        ("cl", Gruppe.VOLUMEN, "ml"),
        ("Stk", Gruppe.STUECK, "Stk"),
    ],
)
def test_gruppe_und_basiseinheit(einheit, erwartete_gruppe, erwartete_basis):
    assert gruppe(einheit) == erwartete_gruppe
    assert basiseinheit(einheit) == erwartete_basis


def test_alle_einheiten_haben_eine_gruppe():
    for einheit in EINHEITEN:
        assert isinstance(gruppe(einheit), Gruppe)


@pytest.mark.parametrize("einheit", ["Liter", "KG", "", "stk"])
def test_unbekannte_einheit(einheit):
    with pytest.raises(EinheitenFehler, match="Unbekannte Einheit"):
        gruppe(einheit)
