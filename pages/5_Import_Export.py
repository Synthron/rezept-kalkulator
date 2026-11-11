import json
from datetime import date

import streamlit as st

from kalkulation.austausch import paket_aus_json
from oberflaeche import datenbank, merke_meldung, zeige_meldung

st.set_page_config(page_title="Import / Export", layout="wide")
st.title("Import / Export")
zeige_meldung()

db = datenbank()
rezept_nach_id = {r.id: r for r in db.lade_rezepte()}

# --- Export ----------------------------------------------------------------------

st.subheader("Rezepte exportieren")
st.caption(
    "Die Exportdatei enthält die gewählten Rezepte, alle darin verwendeten Zwischenprodukte "
    "und die benötigten Einkaufsartikel mit ihren Preisen."
)
auswahl = st.multiselect(
    "Rezepte",
    list(rezept_nach_id),
    format_func=lambda i: rezept_nach_id[i].name,
    placeholder="Rezepte auswählen",
    key="export_auswahl",
)
if auswahl:
    export = db.exportiere_rezepte(auswahl)
    st.caption(f"Enthält {len(export['rezepte'])} Rezept(e) und {len(export['artikel'])} Einkaufsartikel.")
    st.download_button(
        "Exportdatei herunterladen",
        json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"rezepte_{date.today().isoformat()}.json",
        mime="application/json",
        type="primary",
    )

# --- Import ----------------------------------------------------------------------

st.divider()
st.subheader("Rezepte importieren")
st.caption(
    "Artikel und Rezepte, deren Name hier bereits existiert, werden nicht verändert, sondern verwendet. "
    "Der Import erfolgt ganz oder gar nicht."
)

version = st.session_state.setdefault("import_version", 0)
datei = st.file_uploader("Exportdatei (JSON)", type=["json"], key=f"import_datei_{version}")

if datei is not None:
    try:
        paket = paket_aus_json(json.loads(datei.getvalue().decode("utf-8")))
        vorschau = db.importiere(paket, nur_pruefen=True)
    except ValueError as fehler:  # inkl. JSON- und Kodierungsfehlern
        st.error(f"Import nicht möglich: {fehler}")
    else:
        spalte1, spalte2 = st.columns(2)
        with spalte1:
            st.markdown("**Wird neu angelegt**")
            st.write("Rezepte: " + (", ".join(vorschau.rezepte_neu) or "–"))
            st.write("Artikel: " + (", ".join(vorschau.artikel_neu) or "–"))
        with spalte2:
            st.markdown("**Bereits vorhanden, wird verwendet**")
            st.write("Rezepte: " + (", ".join(vorschau.rezepte_vorhanden) or "–"))
            st.write("Artikel: " + (", ".join(vorschau.artikel_vorhanden) or "–"))

        if not vorschau.rezepte_neu and not vorschau.artikel_neu:
            st.info("Alles aus der Datei ist bereits vorhanden.")
        elif st.button("Importieren", type="primary", key="import_starten"):
            try:
                bericht = db.importiere(paket)
            except ValueError as fehler:
                st.error(f"Import nicht möglich: {fehler}")
            else:
                merke_meldung(
                    f"Importiert: {len(bericht.rezepte_neu)} Rezept(e), {len(bericht.artikel_neu)} Artikel."
                )
                st.session_state["import_version"] = version + 1
                st.rerun()
