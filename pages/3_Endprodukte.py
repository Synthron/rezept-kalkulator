import pandas as pd
import streamlit as st

from kalkulation.anzeige import einzelpreis, euro, preis_je_anzeigeeinheit, zahl
from kalkulation.berechnung import Kalkulator
from kalkulation.einheiten import Gruppe, gruppe
from kalkulation.modelle import Endprodukt
from oberflaeche import (
    VERPACKUNGS_SPALTEN,
    datenbank,
    dezimal,
    endprodukt_tabelle,
    merke_meldung,
    tabelle_aus_verpackung,
    verpackung_aus_tabelle,
    verpackungs_optionen,
    zeige_meldung,
)

NEU = 0

st.set_page_config(page_title="Endprodukte", layout="wide")
st.title("Endprodukte")
zeige_meldung()

db = datenbank()
artikel = db.lade_artikel()
rezepte = db.lade_rezepte()
endprodukte = db.lade_endprodukte()
endprodukt_nach_id = {e.id: e for e in endprodukte}
kalkulator = Kalkulator(artikel, rezepte)

# --- Übersichtstabelle -----------------------------------------------------------

if endprodukte:
    st.dataframe(
        endprodukt_tabelle(kalkulator.endprodukt(e) for e in endprodukte), hide_index=True, width="stretch"
    )
else:
    st.info("Keine Endprodukte vorhanden. Lege unten das erste Endprodukt an.")

# --- Auswahl ---------------------------------------------------------------------

st.divider()

if "_naechste_endprodukt_auswahl" in st.session_state:
    st.session_state["endprodukt_auswahl"] = st.session_state.pop("_naechste_endprodukt_auswahl")
if st.session_state.get("endprodukt_auswahl") not in (NEU, *endprodukt_nach_id):
    st.session_state["endprodukt_auswahl"] = NEU

auswahl = st.selectbox(
    "Endprodukt bearbeiten oder neu anlegen",
    [NEU, *endprodukt_nach_id],
    format_func=lambda i: "Neues Endprodukt" if i == NEU else endprodukt_nach_id[i].name,
    key="endprodukt_auswahl",
)
aktuell = endprodukt_nach_id.get(auswahl)
version = st.session_state.setdefault("endprodukt_form_version", 0)
k = f"{auswahl}_{version}"

# --- Kopfdaten -------------------------------------------------------------------

abfuellbar = {r.id: r for r in rezepte if gruppe(r.ausbeute_einheit) == Gruppe.VOLUMEN}
if not abfuellbar:
    st.info("Es gibt noch kein Rezept mit Ausbeute in ml, cl oder l. Lege es zuerst auf der Seite „Rezepte“ an.")
    st.stop()

spalte1, spalte2, spalte3 = st.columns([2, 2, 1])
name = spalte1.text_input("Name", value=aktuell.name if aktuell else "", max_chars=100, key=f"ep_name_{k}")
rezept_ids = list(abfuellbar)
rezept_id = spalte2.selectbox(
    "Rezept",
    rezept_ids,
    index=rezept_ids.index(aktuell.rezept_id) if aktuell else 0,
    format_func=lambda i: abfuellbar[i].name,
    key=f"ep_rezept_{k}",
)
fuellmenge = spalte3.number_input(
    "Füllmenge (ml)",
    min_value=0.0,
    value=float(aktuell.fuellmenge_ml) if aktuell else 500.0,
    step=10.0,
    format="%.1f",
    key=f"ep_fuellmenge_{k}",
)

# --- Verpackung ------------------------------------------------------------------

optionen = verpackungs_optionen(artikel)

st.subheader("Verpackung")
if not optionen:
    st.info("Es gibt noch keine Verpackungen (Kategorie „Verpackung“, eingekauft in Stk).")

tabelle = st.data_editor(
    tabelle_aus_verpackung(aktuell.verpackung if aktuell else (), optionen),
    key=f"ep_verpackung_{k}",
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_order=VERPACKUNGS_SPALTEN,
    column_config={
        "Verpackung": st.column_config.SelectboxColumn(
            "Verpackung", options=list(optionen), required=True, width="large"
        ),
        "Anzahl": st.column_config.NumberColumn(
            "Anzahl je Gebinde", min_value=0.0, step=1.0, default=1.0, format="localized"
        ),
    },
)
st.caption(
    "Auswählbar sind Artikel der Kategorie „Verpackung“, die in Stk eingekauft werden. "
    "Neue Zeile: in die leere Zeile am Tabellenende klicken."
)

verpackung, fehler = verpackung_aus_tabelle(tabelle, optionen)

# --- Live-Kalkulation ------------------------------------------------------------

vorschau = None
if not fehler:
    try:
        vorschau = kalkulator.endprodukt(
            Endprodukt(aktuell.id if aktuell else None, name or "(ohne Name)", rezept_id, dezimal(fuellmenge, 1), verpackung)
        )
    except ValueError as f:
        fehler.append(str(f))

for meldung in fehler:
    st.warning(meldung)

if vorschau:
    st.subheader("Kalkulation")
    preis, einheit = preis_je_anzeigeeinheit(vorschau.rezept.preis_pro_basiseinheit, "ml")
    zeilen = [{
        "Position": f"Inhalt: {vorschau.rezept.rezept.name}",
        "Menge": f"{zahl(vorschau.endprodukt.fuellmenge_ml)} ml à {einzelpreis(preis)}/{einheit}",
        "Kosten": euro(vorschau.inhaltskosten),
    }]
    zeilen += [
        {"Position": v.name, "Menge": f"{zahl(v.position.anzahl)} Stk", "Kosten": euro(v.kosten)}
        for v in vorschau.verpackung
    ]
    st.dataframe(pd.DataFrame(zeilen), hide_index=True, width="stretch")

    spalte1, spalte2, spalte3 = st.columns(3)
    spalte1.metric("Inhalt", euro(vorschau.inhaltskosten))
    spalte2.metric("Verpackung", euro(vorschau.verpackungskosten))
    spalte3.metric("Herstellkosten je Gebinde", euro(vorschau.herstellkosten))

# --- Speichern / Löschen ---------------------------------------------------------

if st.button("Speichern", type="primary", disabled=bool(fehler), key=f"ep_speichern_{k}"):
    try:
        gespeichert = db.speichere_endprodukt(
            Endprodukt(aktuell.id if aktuell else None, name, rezept_id, dezimal(fuellmenge, 1), verpackung)
        )
    except ValueError as f:
        st.error(str(f))
    else:
        merke_meldung(f"Endprodukt „{gespeichert.name}“ gespeichert.")
        st.session_state["_naechste_endprodukt_auswahl"] = gespeichert.id
        st.session_state["endprodukt_form_version"] = version + 1
        st.rerun()

if aktuell:
    with st.popover("Endprodukt löschen"):
        st.write(f"„{aktuell.name}“ wirklich löschen?")
        if st.button("Endgültig löschen", type="primary", key="endprodukt_loeschen"):
            try:
                db.loesche_endprodukt(aktuell.id)
            except ValueError as f:
                st.error(str(f))
            else:
                merke_meldung(f"Endprodukt „{aktuell.name}“ gelöscht.")
                st.session_state["_naechste_endprodukt_auswahl"] = NEU
                st.rerun()
