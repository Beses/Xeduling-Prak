#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

from Datenanalyse.build_revolver_report import build_report
from db.extract_data import extract
from db.init_db import *

APPS = {
    "web": [
        sys.executable, "-m", "uvicorn",
        "viz.web_app:app",
        "--host", "::",
        "--port", "8092",
    ],
    "streamlit": [
        sys.executable, "-m", "streamlit", "run",
        "viz/streamlit_app.py",
    ],
}

DB_PATH = Path("data.db")

REPORT_FILES = [
    "MaschineTools",
    "SzenarienVergleich",
    "ToolRevolver",
    "ToolRevolverSetupAnalyse",
    "ToolRevolverVerlauf",
    "ToolRevolverWarnings",
    "ToolRevolver_Szenario1_Frequency",
    "ToolRevolver_Szenario2_Combo",
    "ZeitenTableKategorisierung",
]
REPORT_DIR = Path("Datenanalyse/reports")


def reports_complete() -> bool:
    return all((REPORT_DIR / f"{name}.csv").exists() for name in REPORT_FILES)


def parse_args():
    parser = argparse.ArgumentParser(description="Tool-Nutzung Dashboard starten")
    parser.add_argument(
        "app",
        nargs="?",
        default="web",
        choices=sorted(APPS),
        help="Welches Frontend gestartet wird (default: web)",
    )
    parser.add_argument(
        "--rebuild-db",
        action="store_true",
        help="data.db löschen und aus der JSON-Datei neu aufbauen, bevor gestartet wird ",
    )
    parser.add_argument(
        "--rebuild-reports",
        action="store_true",
        help="Reports in Datenanalyse/reports/ neu erzeugen, bevor gestartet wird",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.rebuild_db and DB_PATH.exists():
        DB_PATH.unlink()

    if not DB_PATH.exists():
        init_db()
        import_data(extract())
        finalize_db()

    if args.rebuild_reports or not reports_complete():
        build_report()

    sys.exit(subprocess.run(APPS[args.app]).returncode)
