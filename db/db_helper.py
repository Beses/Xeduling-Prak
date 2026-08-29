from dataclasses import dataclass


@dataclass
class Arbeitsschritt:
    id: str
    PSP_ARBEITSSCHRITT_NUMMER: str
    NCName: str
    AmountOfParts: str
    Maschine: str
    MaschinenPool: str
    MaxBearbeitungProTag: int
    PBRef: int
    PartZeitEinzel: int
    ProduktionszeitGesamt: int
    RuestzeitGesamt: int
    StartDate: str
    Konflikt: str
    Status: str
    Typ: str
    AllowNight: str
    MaxMountedAtNight: int
    Abstandstage: int

    def to_tuple(self) -> tuple:
        return (
            self.id,
            self.PSP_ARBEITSSCHRITT_NUMMER,
            self.NCName,
            self.AmountOfParts,
            self.Maschine,
            self.MaschinenPool,
            self.MaxBearbeitungProTag,
            self.PBRef,
            self.PartZeitEinzel,
            self.ProduktionszeitGesamt,
            self.RuestzeitGesamt,
            self.StartDate,
            self.Konflikt,
            self.Status,
            self.Typ,
            self.AllowNight,
            self.MaxMountedAtNight,
            self.Abstandstage,
        )


@dataclass
class Zeit:
    id: str
    PspPositionNummer: str
    PBRef: int
    Maschine: str
    Start: str
    Stop: str
    ZeitGesamt: float
    ZeitProduktionAk: float
    ZeitProduktionGesamt: float
    ZeitProduktionMs: float
    ZeitRuestungGesamt: float
    MengeIst: int
    MengeAusschuss: int
    KgBezeichnung: str
    BemerkungAusschuss: str

    def to_tuple(self) -> tuple:
        return ((
            self.id,
            self.PspPositionNummer,
            self.PBRef,
            self.Maschine,
            self.Start,
            self.Stop,
            self.ZeitGesamt,
            self.ZeitProduktionAk,
            self.ZeitProduktionGesamt,
            self.ZeitProduktionMs,
            self.ZeitRuestungGesamt,
            self.MengeIst,
            self.MengeAusschuss,
            self.KgBezeichnung,
            self.BemerkungAusschuss,
        )
        )


@dataclass
class Article:
    id: int
    ArID: int
    ArtikelNummer: str

    def to_tuple(self) -> tuple:
        return (
            self.id,
            self.ArID,
            self.ArtikelNummer,
        )


@dataclass
class Tool:
    id: int
    AsID: int
    ToolName: str
    ToolNr: int

    def to_tuple(self) -> tuple:
        return (
            self.id,
            self.AsID,
            self.ToolName,
            self.ToolNr,
        )


@dataclass
class PB:
    id: int
    ArtikelNummer: int
    Name: str
    ProduktionsStatus: str
    Liefertermin: str
    Prioritaet: str
    PBBeschreibung: str
    PBPosition: str

    def to_tuple(self) -> tuple:
        return (
            self.id,
            self.ArtikelNummer,
            self.Name,
            self.ProduktionsStatus,
            self.Liefertermin,
            self.Prioritaet,
            self.PBBeschreibung,
            self.PBPosition,
        )
