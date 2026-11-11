import streamlit as st

st.set_page_config(page_title="Herstellkosten-Kalkulator", layout="wide")

# Explizite Navigation statt automatischer pages/-Erkennung, damit die Startseite „Übersicht“ heißt.
st.navigation([
    st.Page("pages/0_Uebersicht.py", title="Übersicht", default=True),
    st.Page("pages/1_Einkaufsartikel.py", title="Einkaufsartikel", url_path="einkaufsartikel"),
    st.Page("pages/2_Rezepte.py", title="Rezepte", url_path="rezepte"),
    st.Page("pages/3_Endprodukte.py", title="Endprodukte", url_path="endprodukte"),
    st.Page("pages/4_Einkaufsliste.py", title="Einkaufsliste", url_path="einkaufsliste"),
    st.Page("pages/5_Import_Export.py", title="Import / Export", url_path="import-export"),
]).run()
