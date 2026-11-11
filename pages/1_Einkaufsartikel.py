import pandas as pd
import streamlit as st

from kalkulation.anzeige import einzelpreis, euro, preis_je_anzeigeeinheit, zahl
from kalkulation.berechnung import preis_pro_basiseinheit
from kalkulation.einheiten import EINHEITEN
from kalkulation.modelle import Artikel, Kategorie
from oberflaeche import auswahl_tabelle, datenbank, dezimal, merke_meldung, zeige_meldung

KATEGORIE_TEXT = {Kategorie.ZUTAT: "Zutat", Kategorie.VERPACKUNG: "Verpackung"}
FILTER = {"Alle": None, "Zutaten": Kategorie.ZUTAT, "Verpackungen": Kategorie.VERPACKUNG}
NEU = 0

st.set_page_config(page_title="Einkaufsartikel", layout="wide")
st.title("Einkaufsartikel")
zeige_meldung()

db = datenbank()
artikel_nach_id = {a.id: a for a in db.lade_artikel()}

# --- Übersichtstabelle -----------------------------------------------------------

filter_text = st.segmented_control("Anzeigen", list(FILTER), default="Alle", key="artikel_filter")
filter_kategorie = FILTER.get(filter_text or "Alle")
sichtbar = [a for a in artikel_nach_id.values() if filter_kategorie in (None, a.kategorie)]


def tabellenzeile(artikel: Artikel) -> dict[str, str]:
    preis, einheit = preis_je_anzeigeeinheit(preis_pro_basiseinheit(artikel), artikel.gebinde_einheit)
    return {
        "Name": artikel.name,
        "Kategorie": KATEGORIE_TEXT[artikel.kategorie],
        "Gebinde": f"{zahl(artikel.gebinde_menge)} {artikel.gebinde_einheit}",
        "Gebindepreis": euro(artikel.gebinde_preis),
        "Preis je Einheit": f"{einzelpreis(preis)}/{einheit}",
        "Lieferant": artikel.lieferant,
        "Notiz": artikel.notiz,
    }


if sichtbar:
    auswahl_tabelle(
        pd.DataFrame([tabellenzeile(a) for a in sichtbar]), [a.id for a in sichtbar], "artikel_auswahl"
    )
else:
    st.info("Keine Artikel vorhanden. Lege unten den ersten Artikel an.")

# --- Anlegen / Bearbeiten --------------------------------------------------------

st.divider()

# Auswahl darf nur vor dem Erzeugen des Widgets gesetzt werden, daher der Umweg über _naechste_artikel_auswahl.
if "_naechste_artikel_auswahl" in st.session_state:
    st.session_state["artikel_auswahl"] = st.session_state.pop("_naechste_artikel_auswahl")
if st.session_state.get("artikel_auswahl") not in (NEU, *artikel_nach_id):
    st.session_state["artikel_auswahl"] = NEU

auswahl = st.selectbox(
    "Artikel bearbeiten oder neu anlegen",
    [NEU, *artikel_nach_id],
    format_func=lambda i: "Neuer Artikel" if i == NEU else artikel_nach_id[i].name,
    key="artikel_auswahl",
)
aktuell = artikel_nach_id.get(auswahl)
# Neue Version nach dem Speichern leert das Formular für den nächsten neuen Artikel.
version = st.session_state.setdefault("artikel_form_version", 0)
k = f"{auswahl}_{version}"

with st.form(f"artikel_form_{k}"):
    spalte1, spalte2 = st.columns(2)
    name = spalte1.text_input("Name", value=aktuell.name if aktuell else "", max_chars=100, key=f"name_{k}")
    kategorie = spalte2.radio(
        "Kategorie",
        list(Kategorie),
        index=list(Kategorie).index(aktuell.kategorie) if aktuell else 0,
        format_func=KATEGORIE_TEXT.get,
        horizontal=True,
        key=f"kategorie_{k}",
    )
    spalte1, spalte2, spalte3 = st.columns(3)
    menge = spalte1.number_input(
        "Gebindegröße",
        min_value=0.0,
        value=float(aktuell.gebinde_menge) if aktuell else 1.0,
        step=1.0,
        format="%.3f",
        key=f"menge_{k}",
    )
    einheit = spalte2.selectbox(
        "Einheit",
        EINHEITEN,
        index=EINHEITEN.index(aktuell.gebinde_einheit) if aktuell else 0,
        key=f"einheit_{k}",
    )
    preis = spalte3.number_input(
        "Gebindepreis (€)",
        min_value=0.0,
        value=float(aktuell.gebinde_preis) if aktuell else 0.0,
        step=0.10,
        format="%.2f",
        key=f"preis_{k}",
    )
    lieferant = st.text_input("Lieferant (optional)", value=aktuell.lieferant if aktuell else "", key=f"lieferant_{k}")
    notiz = st.text_area("Notiz (optional)", value=aktuell.notiz if aktuell else "", key=f"notiz_{k}")
    speichern = st.form_submit_button("Speichern", type="primary")

if speichern:
    try:
        gespeichert = db.speichere_artikel(
            Artikel(
                aktuell.id if aktuell else None,
                name,
                kategorie,
                dezimal(menge, 3),
                einheit,
                dezimal(preis, 2),
                lieferant,
                notiz,
            )
        )
    except ValueError as fehler:
        st.error(str(fehler))
    else:
        merke_meldung(f"Artikel „{gespeichert.name}“ gespeichert.")
        # Nach dem Anlegen leeres Formular für den nächsten Artikel, beim Bearbeiten Auswahl behalten.
        st.session_state["_naechste_artikel_auswahl"] = gespeichert.id if aktuell else NEU
        st.session_state["artikel_form_version"] = version + 1
        st.rerun()

# --- Löschen ---------------------------------------------------------------------

if aktuell:
    verwendungen = db.verwendungen_artikel(aktuell.id)
    if verwendungen:
        st.caption("Löschen nicht möglich, wird verwendet in: " + ", ".join(verwendungen))
    else:
        with st.popover("Artikel löschen"):
            st.write(f"„{aktuell.name}“ wirklich löschen?")
            if st.button("Endgültig löschen", type="primary", key="artikel_loeschen"):
                try:
                    db.loesche_artikel(aktuell.id)
                except ValueError as fehler:
                    st.error(str(fehler))
                else:
                    merke_meldung(f"Artikel „{aktuell.name}“ gelöscht.")
                    st.session_state["_naechste_artikel_auswahl"] = NEU
                    st.rerun()
