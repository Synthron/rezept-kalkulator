#!/usr/bin/env python3
"""Startet den Herstellkosten-Kalkulator unter Windows und Linux.

Aufruf: python start.py  (unter Linux ggf. python3 start.py)
Nutzt nur die Standardbibliothek, damit es vor der Installation der Abhängigkeiten läuft.
"""

import hashlib
import shutil
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

MIN_PYTHON = (3, 11)
HOST = "localhost"
PORT = 8501

PROJEKT = Path(__file__).resolve().parent
VENV = PROJEKT / ".venv"
REQUIREMENTS = PROJEKT / "requirements.txt"
HASH_DATEI = VENV / ".requirements.sha256"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def pruefe_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        benoetigt = ".".join(map(str, MIN_PYTHON))
        vorhanden = ".".join(map(str, sys.version_info[:3]))
        sys.exit(f"Fehler: Python {benoetigt} oder neuer wird benötigt (gefunden: {vorhanden}).")


def erstelle_venv() -> None:
    if venv_python().exists():
        return
    print("Lege virtuelle Umgebung .venv an ...")
    try:
        venv.create(VENV, with_pip=True)
    except (subprocess.CalledProcessError, OSError) as fehler:
        # Halb angelegte .venv entfernen, damit der nächste Start sauber neu beginnt.
        shutil.rmtree(VENV, ignore_errors=True)
        hinweis = ""
        if sys.platform != "win32":
            version = f"{sys.version_info.major}.{sys.version_info.minor}"
            hinweis = (
                "\nUnter Debian/Ubuntu fehlt evtl. das venv-Paket. Installieren mit:\n"
                f"  sudo apt install python3-venv  (oder python{version}-venv)"
            )
        sys.exit(f"Fehler: Virtuelle Umgebung konnte nicht angelegt werden ({fehler}).{hinweis}")


def installiere_abhaengigkeiten() -> None:
    soll = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if HASH_DATEI.exists() and HASH_DATEI.read_text(encoding="utf-8").strip() == soll:
        return
    print("Installiere Abhängigkeiten aus requirements.txt ...")
    try:
        subprocess.run(
            [str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
            check=True,
        )
    except subprocess.CalledProcessError:
        sys.exit("Fehler: Installation der Abhängigkeiten fehlgeschlagen (Ausgabe oben beachten).")
    HASH_DATEI.write_text(soll, encoding="utf-8")


def oeffne_browser_wenn_bereit(timeout: float = 60.0) -> None:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                webbrowser.open(f"http://{HOST}:{PORT}")
                return
        except OSError:
            time.sleep(0.5)


def starte_app() -> int:
    befehl = [
        str(venv_python()), "-m", "streamlit", "run", str(PROJEKT / "app.py"),
        # headless verhindert die interaktive E-Mail-Abfrage beim ersten Start; Browser öffnet start.py selbst.
        "--server.headless", "true",
        "--server.address", HOST,
        "--server.port", str(PORT),
        "--browser.gatherUsageStats", "false",
        # Kein Neuladen bei Codeänderungen: halb neu geladene Module führen sonst zu Fehlern (z. B. bei Enums).
        "--server.fileWatcherType", "none",
    ]
    print(f"Starte Kalkulator auf http://{HOST}:{PORT}  (Beenden mit Strg+C)")
    threading.Thread(target=oeffne_browser_wenn_bereit, daemon=True).start()
    try:
        return subprocess.run(befehl, cwd=PROJEKT).returncode
    except KeyboardInterrupt:
        return 0


def main() -> None:
    pruefe_python_version()
    erstelle_venv()
    installiere_abhaengigkeiten()
    sys.exit(starte_app())


if __name__ == "__main__":
    main()
