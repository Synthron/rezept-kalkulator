"""Einheiten, Einheitengruppen und Umrechnung in Basiseinheiten."""

from decimal import Decimal
from enum import Enum


class Gruppe(Enum):
    MASSE = "Masse"
    VOLUMEN = "Volumen"
    STUECK = "Stück"


class EinheitenFehler(ValueError):
    pass


BASISEINHEIT: dict[Gruppe, str] = {
    Gruppe.MASSE: "g",
    Gruppe.VOLUMEN: "ml",
    Gruppe.STUECK: "Stk",
}

# Einheit -> (Gruppe, Faktor zur Basiseinheit)
_EINHEITEN: dict[str, tuple[Gruppe, Decimal]] = {
    "g": (Gruppe.MASSE, Decimal(1)),
    "kg": (Gruppe.MASSE, Decimal(1000)),
    "ml": (Gruppe.VOLUMEN, Decimal(1)),
    "cl": (Gruppe.VOLUMEN, Decimal(10)),
    "l": (Gruppe.VOLUMEN, Decimal(1000)),
    "Stk": (Gruppe.STUECK, Decimal(1)),
}

EINHEITEN: tuple[str, ...] = tuple(_EINHEITEN)


def _eintrag(einheit: str) -> tuple[Gruppe, Decimal]:
    try:
        return _EINHEITEN[einheit]
    except KeyError:
        raise EinheitenFehler(
            f"Unbekannte Einheit '{einheit}'. Erlaubt: {', '.join(EINHEITEN)}"
        ) from None


def gruppe(einheit: str) -> Gruppe:
    return _eintrag(einheit)[0]


def basiseinheit(einheit: str) -> str:
    return BASISEINHEIT[gruppe(einheit)]


def einheiten_der_gruppe(einheit: str) -> tuple[str, ...]:
    """Alle Einheiten derselben Gruppe, von klein nach groß (z. B. ml, cl, l)."""
    ziel = gruppe(einheit)
    return tuple(sorted((e for e, (g, _) in _EINHEITEN.items() if g == ziel), key=lambda e: _EINHEITEN[e][1]))


def in_basis(menge: Decimal, einheit: str) -> Decimal:
    return menge * _eintrag(einheit)[1]
