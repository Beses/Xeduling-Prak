CREATE TABLE IF NOT EXISTS arbeitsschritte
(
    id                        INTEGER PRIMARY KEY,
    PSP_ARBEITSSCHRITT_NUMMER TEXT NOT NULL,
    NCName                    TEXT,
    AmountOfParts             TEXT,
    Maschine                  TEXT,
    MaschinenPool             TEXT,
    MaxBearbeitungProTag      INTEGER,
    PBRef                     INTEGER,
    PartZeitEinzel            REAL,
    ProduktionszeitGesamt     INTEGER,
    RuestzeitGesamt           INTEGER,
    StartDate                 TEXT,
    Konflikt                  TEXT,
    Status                    TEXT,
    Typ                       TEXT,
    AllowNight                TEXT,
    MaxMountedAtNight         INTEGER,
    Abstandstage              INTEGER
);

CREATE TABLE IF NOT EXISTS tools
(
    id       INTEGER PRIMARY KEY,
    AsID     INTEGER,
    ToolName TEXT,
    ToolNr   INTEGER,

    FOREIGN KEY (AsID)
        REFERENCES arbeitsschritte (id)
);

CREATE TABLE IF NOT EXISTS zeiten
(
    id                   INTEGER PRIMARY KEY,
    PspPositionNummer    TEXT NOT NULL,
    PBRef                INTEGER,
    Maschine             TEXT,
    Start                TEXT,
    Stop                 TEXT,
    ZeitGesamt           REAL,
    ZeitProduktionAk     REAL,
    ZeitProduktionGesamt REAL,
    ZeitProduktionMs     REAL,
    ZeitRuestungGesamt   REAL,
    MengeIst             INTEGER,
    MengeAusschuss       INTEGER,
    KgBezeichnung        TEXT,
    BemerkungAusschuss   TEXT,
    FOREIGN KEY (PspPositionNummer, PBRef)
        REFERENCES arbeitsschritte (PSP_ARBEITSSCHRITT_NUMMER, PBRef)
);

CREATE TABLE IF NOT EXISTS pb
(
    id                INTEGER PRIMARY KEY,
    ArtikelNummer     TEXT,
    Name              TEXT,
    ProduktionsStatus TEXT,
    Liefertermin      TEXT,
    Prioritaet        TEXT,
    PBBeschreibung    TEXT,
    PBPosition        TEXT,
    FOREIGN KEY (ArtikelNummer)
        REFERENCES article (ArtikelNummer)
);

CREATE TABLE IF NOT EXISTS article
(
    id            INTEGER PRIMARY KEY,
    ArID          INTEGER,
    ArtikelNummer TEXT

);

-- Indexe einfügen für schnellere zugriffe
CREATE INDEX IF NOT EXISTS idx_zeiten_machine_time
    ON zeiten (Maschine, Start, Stop);

CREATE INDEX IF NOT EXISTS idx_tools_asid
    ON tools (AsID);

CREATE INDEX IF NOT EXISTS idx_tools_asid
    ON tools (AsID);

CREATE INDEX IF NOT EXISTS idx_tools_asid_toolnr
    ON tools (AsID, ToolNr);

CREATE INDEX IF NOT EXISTS idx_as_pbref
    ON arbeitsschritte (PBRef);

CREATE INDEX IF NOT EXISTS idx_as_psp_nummer
    ON arbeitsschritte (PSP_ARBEITSSCHRITT_NUMMER);

CREATE INDEX IF NOT EXISTS idx_as_pbref_psp
    ON arbeitsschritte (PBRef, PSP_ARBEITSSCHRITT_NUMMER);

CREATE INDEX IF NOT EXISTS idx_zeiten_psp_start
    ON zeiten (PspPositionNummer, Start);

CREATE INDEX IF NOT EXISTS idx_pb_artikelnummer
    ON pb (ArtikelNummer);

-- arbeitsschritte
CREATE INDEX IF NOT EXISTS idx_arbeitsschritte_psp
    ON arbeitsschritte (PSP_ARBEITSSCHRITT_NUMMER);

CREATE INDEX IF NOT EXISTS idx_arbeitsschritte_machine_pb
    ON arbeitsschritte (Maschine, PBRef);

CREATE INDEX IF NOT EXISTS idx_arbeitsschritte_pb
    ON arbeitsschritte (PBRef);

-- tools
CREATE INDEX IF NOT EXISTS idx_tools_asid_toolnr
    ON tools (AsID, ToolNr);

-- pb
CREATE INDEX IF NOT EXISTS idx_pb_id_artikel
    ON pb (id, ArtikelNummer);

-- zeiten -> arbeitsschritte join
create index IF NOT EXISTS idx_zeiten_psp_pbref on zeiten(PspPositionNummer, PBRef);
CREATE INDEX IF NOT EXISTS idx_zeiten_pbref_psp ON zeiten (PBRef, PspPositionNummer, Maschine);


-- arbeitsschritte -> zeiten join (mirror side)
create index IF NOT EXISTS idx_arbeitsschritte_psp_pbref on arbeitsschritte(PSP_ARBEITSSCHRITT_NUMMER, PBRef);

-- tools -> arbeitsschritte join
create index IF NOT EXISTS idx_tools_asid on tools(AsID);

-- Maschine filter + Start ordering, covers your setup_per_machine_over_time query
create index IF NOT EXISTS idx_zeiten_maschine_start on zeiten(Maschine, Start);

-- Typ filter on arbeitsschritte, very selective if most rows aren't 'Arbeitsschritt'
create index IF NOT EXISTS idx_arbeitsschritte_typ on arbeitsschritte(Typ);

create index IF NOT EXISTS idx_zeiten_ruestung on zeiten(Maschine, Start)
    where ZeitRuestungGesamt is not null and ZeitRuestungGesamt > 0;