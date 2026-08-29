import sqlite3

DB_PATH = "data.db"
SCHEMA_PATH = "db/schema.sql"


def init_db():
    conn = sqlite3.connect(DB_PATH)

    # WAL during writes for safety
    conn.execute("PRAGMA journal_mode=WAL;")  # write ahead log
    conn.execute("PRAGMA synchronous=NORMAL;")  # Session only PRAGMA
    conn.execute("PRAGMA cache_size=-65536;")
    conn.execute("PRAGMA temp_store=MEMORY;")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    conn.commit()

    conn.close()
    print("Database initialized")


def import_data(data):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA synchronous=NORMAL;")

    conn.executemany(
        """INSERT OR IGNORE INTO arbeitsschritte (
            id, PSP_ARBEITSSCHRITT_NUMMER, NCName, AmountOfParts, Maschine, MaschinenPool,
            MaxBearbeitungProTag, PBRef, PartZeitEinzel, ProduktionszeitGesamt, RuestzeitGesamt, StartDate, 
            Konflikt, Status, Typ, AllowNight, MaxMountedAtNight, Abstandstage 
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        data["arbeitsschritte"]
    )

    conn.executemany(
        """INSERT OR IGNORE INTO tools (
            id, AsID, ToolName, ToolNr
        ) VALUES (?, ?, ?, ?)""",
        data["tools"]
    )

    conn.executemany(
        """INSERT OR IGNORE INTO zeiten (
            id, PspPositionNummer, PBRef, Maschine, Start, Stop, ZeitGesamt, ZeitProduktionAk, ZeitProduktionGesamt,
            ZeitProduktionMs, ZeitRuestungGesamt, MengeIst, MengeAusschuss, KgBezeichnung, BemerkungAusschuss
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        data["zeiten"]
    )

    conn.executemany(
        """INSERT OR IGNORE INTO pb (
            id, ArtikelNummer, Name, ProduktionsStatus, Liefertermin, Prioritaet, PBBeschreibung, PBPosition
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        data["pbs"]
    )

    conn.executemany(
        """INSERT OR IGNORE INTO article (
            id, ArID, ArtikelNummer
        ) VALUES (?, ?, ?)""",
        data["articles"]
    )

    conn.commit()
    conn.close()
    print("Database has been filled")


def finalize_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("VACUUM;")  # rebuilds the database file, repacking it into a minimal amount of disk space
    conn.execute("PRAGMA optimize;")  # to achieve the best possible query performance
    # conn.execute("ANALYZE;") # gathers statistics about tables and indices

    conn.commit()
    conn.close()
    print("Database cleaned and ready for Search")
