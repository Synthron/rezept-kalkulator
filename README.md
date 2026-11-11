# Herstellkosten-Kalkulator

Lokales Tool zur groben Berechnung der **Herstellkosten pro Gebinde** (z. B. Sirup, Likör).
Einkaufspreise von Zutaten und Verpackungen werden auf g / ml / Stk heruntergebrochen und über
Rezepte und Endprodukte bis zum Preis pro Flasche hochgerechnet.

Details zu Zielen, Rechenregeln und Meilensteinen: [PLANUNG.md](PLANUNG.md)

## Voraussetzungen

- Python **3.11 oder neuer**
- Linux (Debian/Ubuntu): zusätzlich das Paket `python3-venv`
  ```bash
  sudo apt install python3-venv
  ```

## Starten

```bash
python start.py
```

Unter Linux heißt der Befehl je nach Distribution `python3 start.py`.

Beim **ersten Start** legt `start.py` die virtuelle Umgebung `.venv` an und installiert die
Abhängigkeiten aus `requirements.txt`. Das dauert einmalig etwas. Danach öffnet sich das Tool
im Browser unter <http://localhost:8501>.

Beenden mit `Strg+C` im Terminal.

## Befehle für die Entwicklung

Alle Befehle im Projektordner ausführen. Sie nutzen das Python aus der `.venv`, die `start.py`
beim ersten Start anlegt.

| Zweck | Windows | Linux |
|---|---|---|
| Alle Tests | `.venv\Scripts\python.exe -m pytest -q` | `.venv/bin/python -m pytest -q` |
| Tests einer Datei | `.venv\Scripts\python.exe -m pytest tests\test_berechnung.py` | `.venv/bin/python -m pytest tests/test_berechnung.py` |
| Nur Fachlogik-Tests (schnell) | `.venv\Scripts\python.exe -m pytest -q --ignore-glob="tests/test_seite_*"` | `.venv/bin/python -m pytest -q --ignore-glob="tests/test_seite_*"` |
| Abhängigkeiten manuell installieren | `.venv\Scripts\python.exe -m pip install -r requirements.txt` | `.venv/bin/python -m pip install -r requirements.txt` |
| Streamlit ohne `start.py` | `.venv\Scripts\python.exe -m streamlit run app.py` | `.venv/bin/python -m streamlit run app.py` |

Hinweise:

- Ändert sich `requirements.txt`, installiert `start.py` beim nächsten Start automatisch neu.
- Für eine komplett frische Umgebung den Ordner `.venv` löschen und `python start.py` erneut ausführen.
- Nach Codeänderungen die App neu starten (`Strg+C`, dann `python start.py`). `start.py` schaltet das
  automatische Neuladen von Streamlit bewusst ab, weil halb neu geladene Module zu Fehlern führen.
- Neue Seiten in `pages/` müssen zusätzlich in `app.py` (`st.navigation`) eingetragen werden.

## Daten

- Alle Daten liegen in einer einzigen Datei: `daten/kalkulation.db` (SQLite).
- Sie wird beim ersten Zugriff automatisch angelegt.
- **Sichern:** Datei kopieren (während das Tool nicht läuft).
- **Zurücksetzen:** Datei löschen – beim nächsten Start wird eine leere Datenbank angelegt.
- Die Datei kann zwischen Windows und Linux ausgetauscht werden.
- **Rezepte weitergeben:** Seite „Import / Export“. Die JSON-Datei enthält die Rezepte samt
  Zwischenprodukten und benötigten Einkaufsartikeln. Beim Import werden vorhandene Namen
  (Groß-/Kleinschreibung egal) verwendet und nicht überschrieben; importiert wird ganz oder gar nicht.

## Projektstruktur

```
start.py            Startskript für Windows und Linux
app.py              Streamlit-Einstieg: Navigation (Seitenleiste)
oberflaeche.py      Gemeinsame Hilfen der Seiten (Datenbankzugriff, Meldungen, Tabellen)
pages/              Seiten, in app.py registriert
  0_Uebersicht.py   Startseite: Herstellkosten aller Endprodukte und Rezepte
  1_Einkaufsartikel.py
  2_Rezepte.py
  3_Endprodukte.py
  4_Einkaufsliste.py   Hochrechnung: Bedarf, Gebinde, Kosten, herzustellende Chargen
  5_Import_Export.py   Rezepte als JSON exportieren und importieren
kalkulation/        Fachlogik (unabhängig von der Oberfläche)
  einheiten.py      Einheiten, Gruppen, Umrechnung
  modelle.py        Datenklassen inkl. Eingabeprüfung
  berechnung.py     Kostenberechnung, Zirkelprüfung, Hochrechnung/Einkaufsliste
  datenbank.py      SQLite: Laden, Speichern, Löschen, Duplizieren, Import
  austausch.py      Exportformat (JSON) und Prüfung von Importdateien
  anzeige.py        Formatierung (Euro, Mengen, Preise je Einheit)
tests/              pytest-Tests (inkl. Oberflächentests mit Streamlit AppTest)
  conftest.py       Test-Datenbank und Beispieldaten für Oberflächentests
  seitenhilfe.py    Hilfen zum Starten und Bedienen der Seiten im Test
daten/              Datenbank (wird automatisch angelegt, nicht versioniert)
```

## Stand

| Meilenstein | Status |
|---|---|
| 1 Projektgerüst | erledigt |
| 2 Rechenkern | erledigt |
| 3 Datenbank | erledigt |
| 4 Seite Einkaufsartikel | erledigt |
| 5 Seite Rezepte | erledigt |
| 6 Seite Endprodukte | erledigt |
| 7 Übersicht | erledigt |
| 8 Echte Daten | offen |
| 9 Komfort: Rezepte duplizieren, Export/Import, Einkaufsliste mit Hochrechnung | erledigt |
