"""Gemeinsame Hilfen für die Streamlit-Seiten."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import streamlit as st

from kalkulation.anzeige import euro, preise_je_einheit_text, zahl
from kalkulation.berechnung import EndproduktKalkulation, RezeptKalkulation
from kalkulation.datenbank import Datenbank
from kalkulation.einheiten import Gruppe, gruppe
from kalkulation.modelle import Artikel, Kategorie, Rezept, RezeptPosition, VerpackungsPosition

POSITIONS_SPALTEN = ["Zutat", "Menge", "Einheit"]
VERPACKUNGS_SPALTEN = ["Verpackung", "Anzahl"]


@st.cache_resource
def datenbank() -> Datenbank:
    return Datenbank()


def dezimal(wert: float, stellen: int) -> Decimal:
    # Rundung fängt float-Artefakte der Plus/Minus-Knöpfe ab (z. B. 1.2000000000000002)
    return Decimal(str(wert)).quantize(Decimal(1).scaleb(-stellen))


def merke_meldung(text: str) -> None:
    """Erfolgsmeldung, die nach st.rerun() angezeigt wird."""
    st.session_state["_meldung"] = text


def zeige_meldung() -> None:
    if meldung := st.session_state.pop("_meldung", None):
        st.success(meldung)


# --- Rezeptpositionen ↔ Tabelle --------------------------------------------------

@dataclass(frozen=True)
class Quelle:
    """Auswählbare Zutat einer Rezeptposition: Einkaufsartikel oder Zwischenprodukt."""

    artikel_id: int | None
    zwischenprodukt_id: int | None
    einheit: str  # Einkaufs- bzw. Ausbeute-Einheit, Standard für leere Einheit


def quellen(artikel: Iterable[Artikel], rezepte: Iterable[Rezept], ohne_rezept_id: int | None) -> dict[str, Quelle]:
    """Beschriftung → Quelle; das gerade bearbeitete Rezept wird ausgelassen."""
    ergebnis = {a.name: Quelle(a.id, None, a.gebinde_einheit) for a in artikel}
    for r in rezepte:
        if r.id != ohne_rezept_id:
            ergebnis[f"{r.name} (Rezept)"] = Quelle(None, r.id, r.ausbeute_einheit)
    return ergebnis


def tabelle_aus_positionen(positionen: Iterable[RezeptPosition], quellen: dict[str, Quelle]) -> pd.DataFrame:
    beschriftung = {(q.artikel_id, q.zwischenprodukt_id): name for name, q in quellen.items()}
    zeilen = [
        {"Zutat": beschriftung[(p.artikel_id, p.zwischenprodukt_id)], "Menge": float(p.menge), "Einheit": p.einheit}
        for p in positionen
    ]
    return pd.DataFrame(zeilen, columns=POSITIONS_SPALTEN).astype({"Menge": "float64"})


def _leer(wert: object) -> bool:
    return wert is None or (isinstance(wert, str) and not wert.strip()) or bool(pd.isna(wert))


def positionen_aus_tabelle(
    tabelle: pd.DataFrame, quellen: dict[str, Quelle]
) -> tuple[list[RezeptPosition], list[str]]:
    """Liest die bearbeitete Tabelle; gibt Positionen und Fehlermeldungen je Zeile zurück."""
    positionen: list[RezeptPosition] = []
    fehler: list[str] = []
    for nr, (zutat, menge, einheit) in enumerate(tabelle[POSITIONS_SPALTEN].itertuples(index=False), start=1):
        if _leer(zutat) and _leer(menge):
            continue
        if _leer(zutat) or zutat not in quellen:
            fehler.append(f"Zeile {nr}: Bitte eine Zutat auswählen.")
            continue
        if _leer(menge):
            fehler.append(f"Zeile {nr} ({zutat}): Bitte eine Menge eingeben.")
            continue
        quelle = quellen[zutat]
        try:
            positionen.append(
                RezeptPosition(
                    dezimal(menge, 3),
                    quelle.einheit if _leer(einheit) else einheit,
                    artikel_id=quelle.artikel_id,
                    zwischenprodukt_id=quelle.zwischenprodukt_id,
                )
            )
        except ValueError as f:
            fehler.append(f"Zeile {nr} ({zutat}): {f}")
    return positionen, fehler


# --- Verpackung ↔ Tabelle --------------------------------------------------------

def verpackungs_optionen(artikel: Iterable[Artikel]) -> dict[str, int]:
    """Name → Artikel-ID aller Verpackungen, die in Stk eingekauft werden."""
    return {
        a.name: a.id
        for a in artikel
        if a.kategorie == Kategorie.VERPACKUNG and gruppe(a.gebinde_einheit) == Gruppe.STUECK
    }


def tabelle_aus_verpackung(verpackung: Iterable[VerpackungsPosition], optionen: dict[str, int]) -> pd.DataFrame:
    namen = {artikel_id: name for name, artikel_id in optionen.items()}
    zeilen = [{"Verpackung": namen[v.artikel_id], "Anzahl": float(v.anzahl)} for v in verpackung]
    return pd.DataFrame(zeilen, columns=VERPACKUNGS_SPALTEN).astype({"Anzahl": "float64"})


def verpackung_aus_tabelle(
    tabelle: pd.DataFrame, optionen: dict[str, int]
) -> tuple[list[VerpackungsPosition], list[str]]:
    """Leere Anzahl zählt als 1."""
    positionen: list[VerpackungsPosition] = []
    fehler: list[str] = []
    for nr, (name, anzahl) in enumerate(tabelle[VERPACKUNGS_SPALTEN].itertuples(index=False), start=1):
        if _leer(name) and _leer(anzahl):
            continue
        if _leer(name) or name not in optionen:
            fehler.append(f"Verpackung Zeile {nr}: Bitte eine Verpackung auswählen.")
            continue
        try:
            positionen.append(VerpackungsPosition(optionen[name], Decimal(1) if _leer(anzahl) else dezimal(anzahl, 3)))
        except ValueError as f:
            fehler.append(f"Verpackung Zeile {nr} ({name}): {f}")
    return positionen, fehler


# --- Übersichtstabellen ----------------------------------------------------------

def rezept_tabelle(kalkulationen: Iterable[RezeptKalkulation]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Name": k.rezept.name,
            "Ausbeute": f"{zahl(k.rezept.ausbeute_menge)} {k.rezept.ausbeute_einheit}",
            "Zutaten": len(k.rezept.positionen),
            "Chargenkosten": euro(k.chargenkosten),
            "Kosten je Einheit": preise_je_einheit_text(k.preis_pro_basiseinheit, k.rezept.ausbeute_einheit),
            "Notiz": k.rezept.notiz,
        }
        for k in kalkulationen
    ])


def endprodukt_tabelle(kalkulationen: Iterable[EndproduktKalkulation]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Endprodukt": k.endprodukt.name,
            "Rezept": k.rezept.rezept.name,
            "Füllmenge": f"{zahl(k.endprodukt.fuellmenge_ml)} ml",
            "Inhalt": euro(k.inhaltskosten),
            "Verpackung": euro(k.verpackungskosten),
            "Herstellkosten je Gebinde": euro(k.herstellkosten),
        }
        for k in kalkulationen
    ])
