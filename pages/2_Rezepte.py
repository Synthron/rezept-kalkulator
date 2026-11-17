from decimal import Decimal

import pandas as pd
import streamlit as st

from kalkulation.anzeige import einzelpreis, euro, preise_je_einheit, zahl
from kalkulation.berechnung import Kalkulator, mengen_summe
from kalkulation.einheiten import EINHEITEN, einheiten_der_gruppe, gruppe, in_basis
from kalkulation.modelle import Rezept
from oberflaeche import (
    POSITIONS_SPALTEN,
    auswahl_tabelle,
    datenbank,
    dezimal,
    merke_meldung,
    positionen_aus_tabelle,
    quellen,
    rezept_tabelle,
    tabelle_aus_positionen,
    zeige_meldung,
)

NEU = 0
VORSCHAU_ID = -1  # Platzhalter-ID, solange ein neues Rezept noch nicht gespeichert ist

st.set_page_config(page_title="Rezepte", layout="wide")
st.title("Rezepte")
zeige_meldung()

db = datenbank()
artikel = db.lade_artikel()
rezepte = db.lade_rezepte()
rezept_nach_id = {r.id: r for r in rezepte}
kalkulator = Kalkulator(artikel, rezepte)

# --- Übersichtstabelle -----------------------------------------------------------

if rezepte:
    auswahl_tabelle(rezept_tabelle(kalkulator.rezept(r.id) for r in rezepte), [r.id for r in rezepte], "rezept_auswahl")
else:
    st.info("Keine Rezepte vorhanden. Lege unten das erste Rezept an.")

# --- Auswahl ---------------------------------------------------------------------

st.divider()

if "_naechste_rezept_auswahl" in st.session_state:
    st.session_state["rezept_auswahl"] = st.session_state.pop("_naechste_rezept_auswahl")
if st.session_state.get("rezept_auswahl") not in (NEU, *rezept_nach_id):
    st.session_state["rezept_auswahl"] = NEU

auswahl = st.selectbox(
    "Rezept bearbeiten oder neu anlegen",
    [NEU, *rezept_nach_id],
    format_func=lambda i: "Neues Rezept" if i == NEU else rezept_nach_id[i].name,
    key="rezept_auswahl",
)
aktuell = rezept_nach_id.get(auswahl)
version = st.session_state.setdefault("rezept_form_version", 0)
k = f"{auswahl}_{version}"

# --- Kopfdaten -------------------------------------------------------------------

spalte1, spalte2, spalte3 = st.columns([3, 1, 1])
name = spalte1.text_input("Name", value=aktuell.name if aktuell else "", max_chars=100, key=f"rezept_name_{k}")
ausbeute = spalte2.number_input(
    "Ausbeute",
    min_value=0.0,
    value=float(aktuell.ausbeute_menge) if aktuell else 1.0,
    step=0.1,
    format="%.3f",
    key=f"rezept_ausbeute_{k}",
)
ausbeute_einheit = spalte3.selectbox(
    "Einheit",
    EINHEITEN,
    index=EINHEITEN.index(aktuell.ausbeute_einheit if aktuell else "l"),
    filter_mode=None,
    key=f"rezept_einheit_{k}",
)

# --- Positionen ------------------------------------------------------------------

auswahl_quellen = quellen(artikel, rezepte, ohne_rezept_id=aktuell.id if aktuell else None)

st.subheader("Zutaten")
if not auswahl_quellen:
    st.info("Es gibt noch keine Einkaufsartikel. Lege sie zuerst auf der Seite „Einkaufsartikel“ an.")

zutaten = list(auswahl_quellen)
start = tabelle_aus_positionen(aktuell.positionen if aktuell else (), auswahl_quellen).to_dict("records")
zeilen = st.session_state.setdefault(f"rezept_zeilen_{k}", list(range(len(start))))
eingaben = []
for nr, z in enumerate(zeilen):
    vorgabe = start[z] if z < len(start) else {"Zutat": None, "Menge": None, "Einheit": None}
    beschriftung = "visible" if nr == 0 else "collapsed"
    s_zutat, s_menge, s_einheit, s_weg = st.columns([5, 2, 1, 0.4], vertical_alignment="bottom")
    zutat = s_zutat.selectbox(
        "Zutat / Zwischenprodukt",
        zutaten,
        index=zutaten.index(vorgabe["Zutat"]) if vorgabe["Zutat"] in zutaten else None,
        placeholder="Zutat auswählen",
        label_visibility=beschriftung,
        key=f"rezept_zutat_{k}_{z}",
    )
    menge = s_menge.number_input(
        "Menge",
        min_value=0.0,
        value=vorgabe["Menge"],
        step=0.1,
        format="%g",
        label_visibility=beschriftung,
        key=f"rezept_menge_{k}_{z}",
    )
    einheit = None
    if zutat:
        quell_einheit = auswahl_quellen[zutat].einheit
        standard = vorgabe["Einheit"] if zutat == vorgabe["Zutat"] else quell_einheit
        optionen = einheiten_der_gruppe(quell_einheit)
        if standard not in optionen:  # unpassende gespeicherte Einheit sichtbar lassen, damit der Fehler erscheint
            optionen = (*optionen, standard)
        einheit = s_einheit.selectbox(
            "Einheit",
            optionen,
            index=optionen.index(standard),
            filter_mode=None,
            label_visibility=beschriftung,
            # Zutat im Schlüssel: Zutatwechsel setzt die Einheit auf deren Standard zurück.
            key=f"rezept_pos_einheit_{k}_{z}_{zutat}",
        )
    if s_weg.button(":material/delete:", key=f"rezept_zeile_weg_{k}_{z}", help="Zutat entfernen"):
        zeilen.remove(z)
        st.rerun()
    eingaben.append({"Zutat": zutat, "Menge": menge, "Einheit": einheit})

if st.button("Zutat hinzufügen", icon=":material/add:", disabled=not zutaten, key=f"rezept_zeile_neu_{k}"):
    naechste = st.session_state.get(f"rezept_naechste_zeile_{k}", len(start))
    zeilen.append(naechste)
    st.session_state[f"rezept_naechste_zeile_{k}"] = naechste + 1
    st.rerun()

positionen, fehler = positionen_aus_tabelle(pd.DataFrame(eingaben, columns=POSITIONS_SPALTEN), auswahl_quellen)
notiz = st.text_area("Notiz (optional)", value=aktuell.notiz if aktuell else "", key=f"rezept_notiz_{k}")

# --- Live-Kalkulation ------------------------------------------------------------

vorschau = None
if not fehler:
    try:
        entwurf = Rezept(
            aktuell.id if aktuell else VORSCHAU_ID,
            name or "(ohne Name)",
            dezimal(ausbeute, 3),
            ausbeute_einheit,
            positionen,
        )
        andere = [r for r in rezepte if r.id != entwurf.id]
        vorschau = Kalkulator(artikel, [*andere, entwurf]).rezept(entwurf.id)
    except ValueError as f:
        fehler.append(str(f))

for meldung in fehler:
    st.warning(meldung)

if vorschau:
    st.subheader("Kalkulation")
    if vorschau.positionen:
        st.dataframe(
            pd.DataFrame([
                {"Zutat": p.name, "Menge": f"{zahl(p.position.menge)} {p.position.einheit}", "Kosten": euro(p.kosten)}
                for p in vorschau.positionen
            ]),
            hide_index=True,
            width="stretch",
        )
    preise = preise_je_einheit(vorschau.preis_pro_basiseinheit, ausbeute_einheit)
    spalten = st.columns(1 + len(preise))
    spalten[0].metric("Chargenkosten", euro(vorschau.chargenkosten))
    for spalte, (preis, einheit) in zip(spalten[1:], preise):
        spalte.metric(f"Kosten je {einheit}", einzelpreis(preis))

    summe = mengen_summe(positionen)
    if summe and summe[1] == gruppe(ausbeute_einheit):
        st.caption(
            f"Summe der Zutatenmengen: {zahl(summe[0] / in_basis(Decimal(1), ausbeute_einheit))} {ausbeute_einheit}. "
            "Die tatsächliche Ausbeute ist durch Verdunstung, Schalen o. Ä. meist geringer."
        )

# --- Speichern / Löschen ---------------------------------------------------------

if st.button("Speichern", type="primary", disabled=bool(fehler), key=f"rezept_speichern_{k}"):
    try:
        gespeichert = db.speichere_rezept(
            Rezept(aktuell.id if aktuell else None, name, dezimal(ausbeute, 3), ausbeute_einheit, positionen, notiz)
        )
    except ValueError as f:
        st.error(str(f))
    else:
        merke_meldung(f"Rezept „{gespeichert.name}“ gespeichert.")
        # Nach dem Anlegen leeres Formular für das nächste Rezept, beim Bearbeiten Auswahl behalten.
        st.session_state["_naechste_rezept_auswahl"] = gespeichert.id if aktuell else NEU
        st.session_state["rezept_form_version"] = version + 1
        st.rerun()

if aktuell:
    if st.button("Rezept duplizieren", key="rezept_duplizieren", help="Kopiert den gespeicherten Stand des Rezepts."):
        kopie = db.dupliziere_rezept(aktuell.id)
        merke_meldung(f"Kopie „{kopie.name}“ angelegt.")
        st.session_state["_naechste_rezept_auswahl"] = kopie.id
        st.session_state["rezept_form_version"] = version + 1
        st.rerun()

    verwendungen = db.verwendungen_rezept(aktuell.id)
    if verwendungen:
        st.caption("Löschen nicht möglich, wird verwendet in: " + ", ".join(verwendungen))
    else:
        with st.popover("Rezept löschen"):
            st.write(f"„{aktuell.name}“ wirklich löschen?")
            if st.button("Endgültig löschen", type="primary", key="rezept_loeschen"):
                try:
                    db.loesche_rezept(aktuell.id)
                except ValueError as f:
                    st.error(str(f))
                else:
                    merke_meldung(f"Rezept „{aktuell.name}“ gelöscht.")
                    st.session_state["_naechste_rezept_auswahl"] = NEU
                    st.rerun()
