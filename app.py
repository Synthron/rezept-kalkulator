import streamlit as st

st.set_page_config(page_title="Herstellkosten-Kalkulator", layout="wide")

# Explizite Navigation statt automatischer pages/-Erkennung, damit die Startseite „Übersicht“ heißt.
seiten = [
    st.Page("pages/0_Uebersicht.py", title="Übersicht", icon=":material/dashboard:", default=True),
    st.Page("pages/1_Einkaufsartikel.py", title="Einkaufsartikel", icon=":material/shopping_basket:",
            url_path="einkaufsartikel"),
    st.Page("pages/2_Rezepte.py", title="Rezepte", icon=":material/menu_book:", url_path="rezepte"),
    st.Page("pages/3_Endprodukte.py", title="Endprodukte", icon=":material/liquor:", url_path="endprodukte"),
    st.Page("pages/4_Einkaufsliste.py", title="Einkaufsliste", icon=":material/checklist:", url_path="einkaufsliste"),
    st.Page("pages/5_Import_Export.py", title="Import / Export", icon=":material/sync_alt:", url_path="import-export"),
]
aktuelle_seite = st.navigation(seiten, position="hidden")

# Eigene Seitenleiste mit Schaltflächen statt der Standard-Linkliste.
with st.sidebar:
    for seite in seiten:
        aktiv = seite.title == aktuelle_seite.title
        if st.button(seite.title, icon=seite.icon, type="primary" if aktiv else "secondary", width="stretch",
                     key=f"navigation_{seite.title}"):
            st.switch_page(seite)

aktuelle_seite.run()
