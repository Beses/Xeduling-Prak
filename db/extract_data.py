import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from db.db_helper import *


def extract() -> Dict[str, List[tuple]]:
    with open('Datenexport_Praktikum_anonymised.json') as f:
        data = json.load(f)

    arbeitsschritte = []
    zeiten = []
    tools = []
    pbs = []
    articles = []

    for art in data['$values']:
        articles.append(
            Article(
                id=check_value(art, '$id', 'int'),
                ArID=check_value(art, 'ArID', 'int'),
                ArtikelNummer=check_value(art, 'ArtikelNummer', 'str')
            ).to_tuple()
        )
        for pb in art.get('PBModels', {}).get('$values', []):
            pbs.append(
                PB(
                    id=check_value(pb, "$id", "int"),
                    ArtikelNummer=check_value(pb, "ArtikelNummer", "str"),
                    Name=check_value(pb, "PB", "str"),
                    ProduktionsStatus=check_value(pb, "ProduktionsStatus", "str"),
                    Liefertermin=check_value(pb, "Liefertermin", "str"),
                    Prioritaet=check_value(pb, "Prioritaet", "str"),
                    PBBeschreibung=check_value(pb, "PBBeschreibung", "str"),
                    PBPosition=check_value(pb, "PBPosition", "str")
                ).to_tuple()
            )
            for a in pb.get('Arbeitsschritte', {}).get('$values', []):

                arbeitsschritte.append(
                    Arbeitsschritt(
                        id=check_value(a, '$id', "int"),
                        PSP_ARBEITSSCHRITT_NUMMER=check_value(a, 'PSP_ARBEITSSCHRITT_NUMMER', "str"),
                        NCName=check_value(a, 'NCName', "str"),
                        AmountOfParts=check_value(a, 'AmountOfParts', "str"),
                        Maschine=check_value(a, 'Maschine', "str"),
                        MaschinenPool=check_value(a, 'MaschinenPool', "str"),
                        MaxBearbeitungProTag=check_value(a, 'MaxBearbeitungProTag', "int"),
                        PBRef=check_value(a, 'PBRef', "int", nested='$ref'),
                        PartZeitEinzel=check_value(a, 'PartZeitEinzel', "float"),
                        ProduktionszeitGesamt=check_value(a, 'ProduktionszeitGesamt', "int"),
                        RuestzeitGesamt=check_value(a, 'RuestzeitGesamt', "int"),
                        StartDate=check_value(a, 'StartDate', "str"),
                        Konflikt=check_value(a, "Konflikt", "str"),
                        Status=check_value(a, "Status", "str"),
                        Typ=check_value(a, "Typ", "str"),
                        AllowNight=check_value(a, "AllowNight", "str"),
                        MaxMountedAtNight=check_value(a, "MaxMountedAtNight", "int"),
                        Abstandstage=check_value(a, "Abstandstage", "int"),
                    ).to_tuple()
                )
                for t in a.get('Tools', {}).get('$values', []):
                    tools.append(
                        Tool(
                            id=check_value(t, '$id', "int"),
                            AsID=check_value(a, '$id', "int"),
                            ToolName=check_value(t, "ToolName", "str"),
                            ToolNr=check_value(t, "ToolNr", "int"),
                        ).to_tuple()
                    )
            for z in pb.get('Zeiten', {}).get('$values', []):
                duration = z.get('ZeitGesamt')
                if duration < 0:
                    continue
                start, stop = combine_start_stop(
                    z.get('ZbDatumStart'),
                    z.get('ZbZeitStart'),
                    z.get('ZbZeitStop'),
                    to_float(duration)
                )

                zeiten.append(
                    Zeit(
                        id=check_value(z, '$id', "int"),
                        PspPositionNummer=check_value(z, 'PspPositionNummer', "str"),
                        PBRef=check_value(z, 'PbRef', "int", nested='$ref'),
                        Maschine=check_value(z, 'Machine', "str"),
                        Start=start,
                        Stop=stop,
                        ZeitGesamt=check_value(z, 'ZeitGesamt', "float"),
                        ZeitProduktionAk=check_value(z, 'ZeitProduktionAk', "float"),
                        ZeitProduktionGesamt=check_value(z, 'ZeitProduktionGesamt', "float"),
                        ZeitProduktionMs=check_value(z, 'ZeitProduktionMs', "float"),
                        ZeitRuestungGesamt=check_value(z, 'ZeitRuestungGesamt', "float"),
                        MengeIst=check_value(z, 'MengeIst', "int"),
                        MengeAusschuss=check_value(z, 'MengeAusschuss', "int"),
                        KgBezeichnung=check_value(z, 'KgBezeichnung', "str"),
                        BemerkungAusschuss=check_value(z, 'BemerkungAusschuss', "str")
                    ).to_tuple()
                )
    return {
        "arbeitsschritte": arbeitsschritte,
        "zeiten": zeiten,
        "tools": tools,
        "pbs": pbs,
        "articles": articles
    }


def check_value(obj, name, target_type, nested=None):
    val = obj.get(name)
    if nested is not None:
        val = (val or {}).get(nested)
    if val is None or val == "None" or val == "":
        return None
    if target_type == "float":
        return to_float(val)
    elif target_type == "int":
        return to_int(val)
    elif target_type == "str":
        return str(val)
    return None


def combine_start_stop(date, time_start, time_stop, duration) -> Tuple[Optional[str], Optional[str]]:
    if date is None or time_start is None or time_stop is None or duration is None:
        return None, None

    start = f"{date[:10]}T{time_start}"
    start_datetime = datetime.fromisoformat(start)
    stop_datetime = start_datetime + timedelta(minutes=duration)
    stop = f"{stop_datetime.strftime('%Y-%m-%d')}T{time_stop}"

    return start, stop


def to_int(val) -> Optional:
    return int(val) if val is not None else None


def to_float(val) -> Optional:
    return float(str(val).replace(',', '.')) if val is not None else None


if __name__ == '__main__':
    extract()
