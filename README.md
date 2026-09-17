# Tool Nutzung Dashboard

Analyse der Werkzeugnutzung, Revolver-Belegung und Rüstzeiten auf Basis der
Maschinendaten aus `Datenexport_Praktikum_anonymised.json`.

## Setup

Dependencies installieren:

```bash
pip install -r requirements.txt
```

Die JSON-Datei muss im Projektroot liegen:

```text
Datenexport_Praktikum_anonymised.json
```

## Dashboard starten

```bash
python3 app.py
```

Startet standardmäßig das **FastAPI-Dashboard** unter:

```text
http://localhost:8092
bzw. 
https://lehre.bpm.in.tum.de/ports/8092/
```

Beim ersten Start baut das Skript `data.db` im Projektroot auf (falls sie noch
nicht existiert) und erzeugt anschließend die Reports unter
`Datenanalyse/reports/`, falls diese fehlen.

### Streamlit-Version starten

Die ursprüngliche Streamlit-Variante ist weiterhin vorhanden und kann
alternativ gestartet werden:

```bash
python3 app.py streamlit
```

### Datenbank / Reports neu aufbauen

Alle Optionen anzeigen:

```bash
python3 app.py --help
```

| Flag                 | Wirkung                                                                                   |
|----------------------|--------------------------------------------------------------------------------------------|
| `--rebuild-db`       | `data.db` löschen und aus der JSON-Datei neu aufbauen; erzeugt danach automatisch auch die Reports neu |
| `--rebuild-reports`  | Nur die Reports in `Datenanalyse/reports/` neu erzeugen (DB bleibt unverändert)            |

Beispiele:

```bash
# Datenbank komplett neu aufbauen (z. B. nach Änderungen an der JSON-Datei)
python3 app.py --rebuild-db

# Nur die Reports neu erzeugen (z. B. nach Änderungen an build_revolver_report.py)
python3 app.py --rebuild-reports

# Flags lassen sich mit der App-Auswahl kombinieren
python3 app.py streamlit --rebuild-db
```

Ohne Flags werden Datenbank bzw. Reports nur dann (neu) aufgebaut, wenn sie
noch nicht existieren.

## Projektstruktur

```text
.
├── app.py                          # Einstiegspunkt: baut DB/Reports, startet Dashboard
├── data.db                         # SQLite-Datenbank (generiert)
├── Datenanalyse/
│   ├── build_revolver_report.py    # Erzeugt die CSV-Reports aus der DB
│   ├── profile_json.py
│   └── reports/                    # Generierte CSVs (Basis für das Dashboard)
├── db/
│   ├── database.py
│   ├── db_helper.py
│   ├── extract_data.py             # Parsen der JSON-Rohdaten
│   ├── init_db.py                  # Schema anlegen + Daten importieren
│   └── schema.sql
├── viz/
│   ├── web_app.py                  # FastAPI-Dashboard (Standard)
│   ├── streamlit_app.py            # Streamlit-Dashboard (Alternative)
│   └── frontend/                   # Frontend für web_app.py (Vanilla JS + Plotly)
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── Datenexport_Praktikum_anonymised.json  # Rohdaten (nicht im Repo enthalten)
├── Datenbeschreibung.json
└── requirements.txt
```

## Datenbank in PyCharm ansehen

In PyCharm Professional:

```text
View → Tool Windows → Database
```

Dann:

```text
+ → Data Source → SQLite → data.db auswählen
```

Danach ggf. Rechtsklick auf die Verbindung:

```text
Synchronize / Refresh
```

Die Tabellen liegen unter:

```text
main → tables
```