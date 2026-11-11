from decimal import Decimal

import pandas as pd
import streamlit as st

from kalkulation.anzeige import euro, menge_text, zahl
from kalkulation.berechnung import Kalkulator
from kalkulation.einheiten import in_basis
from kalkulation.modelle import Kategorie
from oberflaeche import datenbank, dezimal

KATEGORIE_TEXT = {Kategorie.ZUTAT: "Zutat", Kategorie.VERPACKUNG: "Verpackung"}

st.set_page_config(page_title="Einkaufsliste", layout="wide")
st.title("Einkaufsliste")
st.caption("Hochrechnung: Was muss für eine gewünschte Menge eingekauft und hergestellt werden?")

db = datenbank()
artikel = db.lade_artikel()
rezepte = db.lade_rezepte()
endprodukt_nach_id = {e.id: e for e in db.lade_endprodukte()}
rezept_nach_id = {r.id: r for r in rezepte}
kalkulator = Kalkulator(artikel, rezepte)

# --- Eingabe ---------------------------------------------------------------------

spalte_ep, spalte_rezept = st.columns(2)

with spalte_ep:
    gewaehlte_endprodukte = st.multiselect(
        "Endprodukte",
        list(endprodukt_nach_id),
        format_func=lambda i: endprodukt_nach_id[i].name,
        placeholder="Endprodukte auswählen",
        key="ek_endprodukte",
    )
    endprodukt_auftraege = []
    for endprodukt_id in gewaehlte_endprodukte:
        anzahl = st.number_input(
            f"Anzahl „{endprodukt_nach_id[endprodukt_id].name}“",
            min_value=0,
            value=10,
            step=1,
            key=f"ek_anzahl_{endprodukt_id}",
        )
        if anzahl:
            endprodukt_auftraege.append((endprodukt_nach_id[endprodukt_id], Decimal(anzahl)))

with spalte_rezept:
    gewaehlte_rezepte = st.multiselect(
        "Rezepte (z. B. Vorrat an Zwischenprodukten)",
        list(rezept_nach_id),
        format_func=lambda i: rezept_nach_id[i].name,
        placeholder="Rezepte auswählen",
        key="ek_rezepte",
    )
    rezept_auftraege = []
    for rezept_id in gewaehlte_rezepte:
        rezept = rezept_nach_id[rezept_id]
        menge = st.number_input(
            f"Menge „{rezept.name}“ ({rezept.ausbeute_einheit})",
            min_value=0.0,
            value=float(rezept.ausbeute_menge),
            step=1.0,
            format="%.3f",
            key=f"ek_menge_{rezept_id}",
        )
        if menge:
            rezept_auftraege.append((rezept_id, dezimal(menge, 3) * in_basis(Decimal(1), rezept.ausbeute_einheit)))

if not endprodukt_auftraege and not rezept_auftraege:
    st.info("Wähle Endprodukte (mit Anzahl) oder Rezepte (mit Menge) aus, um die Einkaufsliste zu berechnen.")
    st.stop()

bedarf = kalkulator.bedarf(endprodukt_auftraege, rezept_auftraege)
einkauf = kalkulator.einkaufsliste(bedarf)

# --- Ergebnis --------------------------------------------------------------------

st.divider()
spalte1, spalte2 = st.columns(2)
spalte1.metric(
    "Einkauf (ganze Gebinde)",
    euro(sum((p.einkaufskosten for p in einkauf), Decimal(0))),
    help="Was an der Kasse bezahlt wird, wenn nur ganze Gebinde gekauft werden.",
)
spalte2.metric(
    "Materialverbrauch",
    euro(sum((p.verbrauchskosten for p in einkauf), Decimal(0))),
    help="Anteilige Kosten der tatsächlich verbrauchten Mengen.",
)

st.subheader("Einkaufen")
st.dataframe(
    pd.DataFrame([
        {
            "Artikel": p.artikel.name,
            "Kategorie": KATEGORIE_TEXT[p.artikel.kategorie],
            "Bedarf": menge_text(p.menge_basis, p.artikel.gebinde_einheit),
            "Gebinde": f"{zahl(p.artikel.gebinde_menge)} {p.artikel.gebinde_einheit}",
            "Anzahl Gebinde": p.gebinde_anzahl,
            "Einkauf": euro(p.einkaufskosten),
            "Verbrauch": euro(p.verbrauchskosten),
            "Lieferant": p.artikel.lieferant,
        }
        for p in einkauf
    ]),
    hide_index=True,
    width="stretch",
)

st.subheader("Herstellen")
herstellen = []
for rezept_id, menge in bedarf.rezepte.items():
    rezept = rezept_nach_id[rezept_id]
    chargen = menge / in_basis(rezept.ausbeute_menge, rezept.ausbeute_einheit)
    herstellen.append({
        "Rezept": rezept.name,
        "Menge": menge_text(menge, rezept.ausbeute_einheit),
        "Chargen": zahl(chargen.quantize(Decimal("0.01"))),
        "Ausbeute je Charge": f"{zahl(rezept.ausbeute_menge)} {rezept.ausbeute_einheit}",
    })
st.dataframe(pd.DataFrame(herstellen), hide_index=True, width="stretch")
