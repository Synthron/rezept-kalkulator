"""Formatierung von Beträgen und Mengen für die Anzeige (deutsches Zahlenformat)."""

from decimal import ROUND_HALF_UP, Decimal

from kalkulation.einheiten import Gruppe, basiseinheit, einheiten_der_gruppe, gruppe, in_basis

_ANZEIGEEINHEIT = {Gruppe.MASSE: "kg", Gruppe.VOLUMEN: "l", Gruppe.STUECK: "Stk"}


def _deutsch(text: str) -> str:
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def euro(betrag: Decimal, max_stellen: int = 2) -> str:
    """Kaufmännisch gerundet; bei max_stellen > 2 werden überzählige Nullen ab der 3. Stelle entfernt."""
    gerundet = betrag.quantize(Decimal(1).scaleb(-max_stellen), rounding=ROUND_HALF_UP)
    ganz, _, nachkomma = f"{gerundet:,.{max_stellen}f}".partition(".")
    nachkomma = nachkomma[:2] + nachkomma[2:].rstrip("0")
    return _deutsch(f"{ganz}.{nachkomma}") + " €"


def einzelpreis(betrag: Decimal) -> str:
    """Preis je Einheit: 2 Nachkommastellen, bei kleinen Beträgen so viele, dass 2 gültige Ziffern sichtbar sind (max. 6)."""
    if betrag == 0 or abs(betrag) >= Decimal("0.1"):
        return euro(betrag)
    return euro(betrag, min(6, 1 - betrag.adjusted()))


def zahl(wert: Decimal) -> str:
    """Menge ohne überflüssige Nullen, z. B. 0,5 / 10 / 2.500."""
    return _deutsch(f"{wert.normalize():,f}")


def menge_text(menge_basis: Decimal, einheit: str) -> str:
    """Menge in kg/l (ab 1) bzw. g/ml, auf 3 Nachkommastellen gerundet, z. B. „13 kg“, „250 ml“."""
    anzeigeeinheit = _ANZEIGEEINHEIT[gruppe(einheit)]
    wert = menge_basis / in_basis(Decimal(1), anzeigeeinheit)
    if wert < 1:
        anzeigeeinheit, wert = basiseinheit(einheit), menge_basis
    return f"{zahl(wert.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))} {anzeigeeinheit}"


def preis_je_anzeigeeinheit(preis_pro_basis: Decimal, einheit: str) -> tuple[Decimal, str]:
    """Rechnet €/g bzw. €/ml in €/kg bzw. €/l um (Stück bleibt Stück)."""
    anzeigeeinheit = _ANZEIGEEINHEIT[gruppe(einheit)]
    return preis_pro_basis * in_basis(Decimal(1), anzeigeeinheit), anzeigeeinheit


def preise_je_einheit(preis_pro_basis: Decimal, einheit: str) -> list[tuple[Decimal, str]]:
    """Preis für jede Einheit der Gruppe, z. B. €/ml, €/cl, €/l."""
    return [(preis_pro_basis * in_basis(Decimal(1), e), e) for e in einheiten_der_gruppe(einheit)]


def preise_je_einheit_text(preis_pro_basis: Decimal, einheit: str) -> str:
    return " · ".join(f"{einzelpreis(p)}/{e}" for p, e in preise_je_einheit(preis_pro_basis, einheit))
