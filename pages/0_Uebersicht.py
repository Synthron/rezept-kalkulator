import streamlit as st

from kalkulation.berechnung import Kalkulator
from oberflaeche import datenbank, endprodukt_tabelle, rezept_tabelle

st.set_page_config(page_title="Übersicht", layout="wide")
st.title("Übersicht")

db = datenbank()
artikel = db.lade_artikel()
rezepte = db.lade_rezepte()
endprodukte = db.lade_endprodukte()
kalkulator = Kalkulator(artikel, rezepte)

spalte1, spalte2, spalte3 = st.columns(3)
spalte1.metric("Einkaufsartikel", len(artikel))
spalte2.metric("Rezepte", len(rezepte))
spalte3.metric("Endprodukte", len(endprodukte))

st.subheader("Herstellkosten je Gebinde")
if endprodukte:
    st.caption("Zeile anklicken, um das Endprodukt bzw. Rezept zu öffnen.")
    gewaehlt = st.dataframe(
        endprodukt_tabelle(kalkulator.endprodukt(e) for e in endprodukte),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="uebersicht_endprodukte",
    )
    if zeilen := gewaehlt.selection.rows:
        st.session_state["_naechste_endprodukt_auswahl"] = endprodukte[zeilen[0]].id
        st.switch_page("pages/3_Endprodukte.py")
else:
    st.info(
        "Noch keine Endprodukte vorhanden. Vorgehen über die Seitenleiste:\n\n"
        "1. **Einkaufsartikel**: Zutaten und Verpackungen mit Gebindepreis anlegen\n"
        "2. **Rezepte**: Zutaten mit Mengen und Ausbeute erfassen\n"
        "3. **Endprodukte**: Rezept, Füllmenge und Verpackung festlegen"
    )

st.subheader("Rezepte")
if rezepte:
    gewaehlt = st.dataframe(
        rezept_tabelle(kalkulator.rezept(r.id) for r in rezepte),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="uebersicht_rezepte",
    )
    if zeilen := gewaehlt.selection.rows:
        st.session_state["_naechste_rezept_auswahl"] = rezepte[zeilen[0]].id
        st.switch_page("pages/2_Rezepte.py")
else:
    st.caption("Noch keine Rezepte vorhanden.")
