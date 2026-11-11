"""Hilfen für Oberflächentests mit Streamlit AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJEKT = Path(__file__).resolve().parent.parent
SEITEN = PROJEKT / "pages"


def starte_seite(datei: str, **session_state) -> AppTest:
    return _starte(SEITEN / datei, session_state)


def starte_app(**session_state) -> AppTest:
    """Startet app.py inkl. Navigation (öffnet die Standardseite)."""
    return _starte(PROJEKT / "app.py", session_state)


def _starte(pfad: Path, session_state: dict) -> AppTest:
    at = AppTest.from_file(str(pfad), default_timeout=30)
    for schluessel, wert in session_state.items():
        at.session_state[schluessel] = wert
    return at.run()


def klicke(at: AppTest, beschriftung: str) -> AppTest:
    return next(b for b in at.button if b.label == beschriftung).click().run()
