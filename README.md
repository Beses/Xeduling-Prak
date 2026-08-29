## Setup

Dependencies installieren:

```bash
pip install -r requirements.txt
```

## Datenbank erstellen & Dashboard starten

Die JSON-Datei muss im Projektroot liegen:

```text
Datenexport_Praktikum_anonymised.json
```

Starten:

```bash
python3 app.py
```

Das Skript baut beim ersten Start `data.db` im Projektroot auf (falls sie noch nicht existiert),
erzeugt die Reports und startet danach automatisch das Dashboard unter:

```text
http://localhost:8501
```

Um die Datenbank neu aufzubauen, `data.db` vorher löschen und `app.py` erneut ausführen.


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
