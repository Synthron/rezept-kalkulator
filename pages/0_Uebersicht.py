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
    st.dataframe(endprodukt_tabelle(kalkulator.endprodukt(e) for e in endprodukte), hide_index=True, width="stretch")
else:
    st.info(
        "Noch keine Endprodukte vorhanden. Vorgehen über die Seitenleiste:\n\n"
        "1. **Einkaufsartikel**: Zutaten und Verpackungen mit Gebindepreis anlegen\n"
        "2. **Rezepte**: Zutaten mit Mengen und Ausbeute erfassen\n"
        "3. **Endprodukte**: Rezept, Füllmenge und Verpackung festlegen"
    )

st.subheader("Rezepte")
if rezepte:
    st.dataframe(rezept_tabelle(kalkulator.rezept(r.id) for r in rezepte), hide_index=True, width="stretch")
else:
    st.caption("Noch keine Rezepte vorhanden.")
