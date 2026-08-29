import sqlite3
import urllib.parse

import pandas as pd
from pandas import DataFrame


def _connect(db_path: str):
    """Open the SQLite database in read-only immutable mode and tune read performance."""
    uri = f"file:{urllib.parse.quote(db_path)}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA cache_size=-32768;")
    conn.execute("PRAGMA mmap_size=268435456;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn


class Database:
    """Read-only helper for loading machine, step, and production-time data from SQLite."""

    def __init__(self, db_path: str):
        """Create the database connection and cache available table/column metadata."""
        self._conn = _connect(db_path)

    def _query(self, sql: str, params=None) -> DataFrame:
        return pd.read_sql_query(
            sql,
            self._conn,
            params=params or {}
        )

    def _build_temp_tables_tools(self) -> None:
        """Temp-Tabellen auf der shared connection aufbauen."""
        stmts = [
            "CREATE TEMP TABLE ass_table AS SELECT Maschine, PSP_ARBEITSSCHRITT_NUMMER, PBRef, id, Typ FROM arbeitsschritte",
            "CREATE INDEX idx_ass_psp_pb ON ass_table (PSP_ARBEITSSCHRITT_NUMMER, PBRef)",

            "CREATE TEMP TABLE zt_table AS SELECT Maschine, Start, Stop, ZeitRuestungGesamt, PspPositionNummer, PBRef FROM zeiten WHERE Maschine IS NOT NULL",
            "CREATE INDEX idx_zt_psp_pb ON zt_table (PspPositionNummer, PBRef)",
            "CREATE INDEX idx_zt_machine_start ON zt_table (Maschine, Start)",

            "CREATE TEMP TABLE pb_table AS SELECT ArtikelNummer, id FROM pb",
            "CREATE INDEX idx_pb_id ON pb_table (id)",

            "CREATE TEMP TABLE tool_table AS SELECT DISTINCT AsID, ToolName FROM tools",
            "CREATE INDEX idx_tool_asid ON tool_table (AsID)",

            # Häufigste Maschine je PBRef/PspPositionNummer aus zeiten,
            # bei Gleichstand die alphabetisch kleinste (MIN)
            """CREATE TEMP TABLE zeiten_machine_lookup AS
               SELECT PBRef, PspPositionNummer, Maschine AS any_machine
               FROM (
                   SELECT
                       PBRef,
                       PspPositionNummer,
                       Maschine,
                       COUNT(*) AS anzahl,
                       ROW_NUMBER() OVER (
                           PARTITION BY PBRef, PspPositionNummer
                           ORDER BY COUNT(*) DESC, Maschine ASC
                       ) AS rn
                   FROM zeiten
                   WHERE NULLIF(Maschine, '') IS NOT NULL
                   GROUP BY PBRef, PspPositionNummer, Maschine
               ) x
               WHERE rn = 1""",
            "CREATE INDEX idx_zml_pbref_psp ON zeiten_machine_lookup (PBRef, PspPositionNummer)",

            # Eine Zeile pro PBRef/PSP, bevorzugt die mit gesetzter Maschine
            """CREATE TEMP TABLE arbeitsschritte_dedup AS
               SELECT id, PBRef, PSP_ARBEITSSCHRITT_NUMMER, Maschine, MaschinenPool, Typ
               FROM (
                   SELECT
                       a.id, a.PBRef, a.PSP_ARBEITSSCHRITT_NUMMER, a.Maschine, a.MaschinenPool, a.Typ,
                       ROW_NUMBER() OVER (
                           PARTITION BY a.PBRef, a.PSP_ARBEITSSCHRITT_NUMMER
                           ORDER BY CASE WHEN NULLIF(a.Maschine, '') IS NOT NULL THEN 0 ELSE 1 END
                       ) AS rn
                   FROM arbeitsschritte a
               ) x
               WHERE rn = 1""",
            "CREATE INDEX idx_asd_pbref_psp ON arbeitsschritte_dedup (PBRef, PSP_ARBEITSSCHRITT_NUMMER)",

            """CREATE TEMP TABLE zeiten_table AS
               SELECT
                   z.PBRef,
                   z.PspPositionNummer,
                   COALESCE(
                       NULLIF(z.Maschine, ''),
                       NULLIF(a.Maschine, ''),
                       zml.any_machine
                   ) AS Maschine_Final,
                   z.Start,
                   z.Stop,
                   a.id,
                   z.ZeitRuestungGesamt,
                   a.Typ
               FROM zeiten z
               JOIN arbeitsschritte_dedup a
                   ON a.PBRef = z.PBRef
                  AND a.PSP_ARBEITSSCHRITT_NUMMER = z.PspPositionNummer
               LEFT JOIN zeiten_machine_lookup zml
                   ON zml.PBRef = z.PBRef
                  AND zml.PspPositionNummer = z.PspPositionNummer
               WHERE
                   (
                       NULLIF(z.Maschine, '') IS NOT NULL
                       OR NULLIF(a.Maschine, '') IS NOT NULL
                       OR NULLIF(a.MaschinenPool, '') IS NOT NULL
                       OR zml.any_machine IS NOT NULL
                   )
                   AND COALESCE(
                       NULLIF(z.Maschine, ''),
                       NULLIF(a.Maschine, ''),
                       zml.any_machine
                   ) IS NOT NULL
                   AND a.Typ = 'Arbeitsschritt'""",

            "CREATE INDEX idx_zeiten_table_id ON zeiten_table (id)",
            "CREATE INDEX idx_zeiten_table_typ_start_machine ON zeiten_table (Typ, Start, Maschine_Final)",
            "CREATE INDEX idx_zeiten_table_pbref_psp ON zeiten_table (PBRef, PspPositionNummer)",
        ]

        for stmt in stmts:
            self._conn.execute(stmt)

    def _ensure_temp_tables_tools(self) -> None:
        """baut Temp-Tabellen nur wenn noch nicht vorhanden."""
        cur = self._conn.execute(
            "SELECT name FROM sqlite_temp_master WHERE type='table' AND name='zeiten_table'"
        )
        if cur.fetchone() is None:
            self._build_temp_tables_tools()

    def MaschineTools(self) -> DataFrame:
        self._ensure_temp_tables_tools()
        return self._query("""
            select t.AsID, t.ToolName, zt.Start, zt.Maschine_Final
            from tools t 
            join zeiten_table zt on zt.id = t.AsID
        """)

    def arbeitsschritt_tools(self) -> DataFrame:
        """Eine Zeile pro Arbeitsschritt (zeiten_table.id) mit Maschine_Final, Start
        und der kommagetrennten Liste der benutzten Tools - Grundlage fuer die
        Werkzeug-Revolver-Simulation (Reihenfolge/FIFO laesst sich nicht sinnvoll
        in SQL abbilden, daher die rohe Job-Liste hier und die Simulation in Python)."""
        self._ensure_temp_tables_tools()
        return self._query("""
            SELECT
                z.id AS AsID,
                z.PBRef,
                z.PspPositionNummer,
                z.Maschine_Final,
                z.Start,
                GROUP_CONCAT(DISTINCT t.ToolName) AS Tools,
                z.ZeitRuestungGesamt AS Ruestzeit
            FROM zeiten_table z
            LEFT JOIN tool_table t
                ON t.AsID = z.id
            WHERE z.Typ = 'Arbeitsschritt'
              AND z.Start IS NOT NULL
              AND z.Maschine_Final IS NOT NULL
            GROUP BY z.id
            ORDER BY z.Start;
        """)

    def zeiten_table_kategorisierung(self) -> DataFrame:
        """Erklärt, warum Arbeitsschritte nicht in zeiten_table landen:
        Aufschlüsselung nach Typ-Ausschluss, fehlender Zeit und Machine-Filter.
        Nutzt bewusst dieselbe Dedup-Logik (arbeitsschritte_dedup) wie
        zeiten_table selbst, damit final_in_zeiten_table exakt mit der Anzahl
        distinkter Arbeitsschritte in zeiten_table übereinstimmt."""
        self._ensure_temp_tables_tools()
        return self._query("""
            WITH
              zeiten_hat_machine AS (
                SELECT
                  PBRef,
                  PspPositionNummer,
                  COUNT(*) AS zeilen_anzahl,
                  MAX(CASE WHEN NULLIF(Maschine, '') IS NOT NULL THEN 1 ELSE 0 END) AS hat_maschine
                FROM zeiten
                GROUP BY PBRef, PspPositionNummer
              ),
              kategorisiert AS (
                SELECT
                  a.PBRef,
                  a.PSP_ARBEITSSCHRITT_NUMMER,
                  CASE
                    WHEN a.Typ != 'Arbeitsschritt' THEN 'Typ ungleich Arbeitsschritt'
                    WHEN zh.zeilen_anzahl IS NULL THEN 'Keine Zeit zugeordnet'
                    WHEN zh.hat_maschine = 1
                         OR NULLIF(a.Maschine, '') IS NOT NULL THEN 'In zeiten_table'
                    WHEN NULLIF(a.MaschinenPool, '') IS NOT NULL THEN 'Nur MaschinenPool gefüllt (zählt nicht)'
                    ELSE 'Machine komplett leer'
                  END AS Kategorie
                FROM arbeitsschritte_dedup a
                LEFT JOIN zeiten_hat_machine zh
                    ON zh.PBRef = a.PBRef
                   AND zh.PspPositionNummer = a.PSP_ARBEITSSCHRITT_NUMMER
              )
            SELECT
              (SELECT COUNT(*) FROM arbeitsschritte) AS gesamt,
              SUM(CASE WHEN Kategorie = 'Typ ungleich Arbeitsschritt' THEN 1 ELSE 0 END) AS typ_ausschluss,
              SUM(CASE WHEN Kategorie = 'Keine Zeit zugeordnet' THEN 1 ELSE 0 END) AS keine_zeit,
              SUM(CASE WHEN Kategorie = 'Machine komplett leer' THEN 1 ELSE 0 END) AS machine_leer,
              SUM(CASE WHEN Kategorie = 'Nur MaschinenPool gefüllt (zählt nicht)' THEN 1 ELSE 0 END) AS nur_pool,
              SUM(CASE WHEN Kategorie = 'In zeiten_table' THEN 1 ELSE 0 END) AS final_in_zeiten_table
            FROM kategorisiert;
        """)
