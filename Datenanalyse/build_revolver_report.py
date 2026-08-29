import itertools

import pandas as pd

from db.database import Database

DB_PATH = "data.db"
REPORT_DIR = "Datenanalyse/reports"

# ============================================================
# KAPAZITÄT PRO MASCHINE
# (keine Pools mehr - jede Maschine hat ihren eigenen Revolver)
# ============================================================

MACHINE_CAPACITY = {
    "C40": 121,
    "C400": 37,
    "RS2_1": 121,
    "RS2_2": 121,
    "Chiron": 48,
    "C42": 258,
    "Brother": 32,
}


def parse_tools(val):
    """Wandelt den kommagetrennten Tools-String (oder NaN) in ein Set von Toolnamen um."""
    if pd.isna(val) or val == "":
        return set()
    return set(t.strip() for t in str(val).split(",") if t.strip())


def precompute_usage_and_combo(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    Brechnet wie oft Tool X auf Maschine Y verwendet wurde und wie häufig zwei bestimmte Tools gemeinsam auf einer Maschine verwendet wurden

    usage_counts: {(machine, tool): Anzahl Arbeitsschritte,
            in denen das Tool auf dieser Maschine benutzt wurde}
    combo_counts: {(machine, frozenset({tool_a, tool_b})): Anzahl Arbeitsschritte,
            in denen beide Tools gemeinsam auf dieser Maschine benutzt wurden}
    """
    usage_counts: dict = {}
    combo_counts: dict = {}

    for row in df.itertuples(index=False):
        machine = row.Maschine_Final
        tools = parse_tools(row.Tools)

        for t in tools:
            key = (machine, t)
            usage_counts[key] = usage_counts.get(key, 0) + 1

        for t1, t2 in itertools.combinations(sorted(tools), 2):
            key = (machine, frozenset((t1, t2)))
            combo_counts[key] = combo_counts.get(key, 0) + 1

    return usage_counts, combo_counts


def combo_affinity(tool: str, needed: set, machine: str, combo_counts: dict) -> int:
    """
    Benötigt für Szenario 1: Toolkombinationen.
    Wie oft trat `tool` historisch gemeinsam mit den aktuell benötigten
    Tools auf dieser Maschine auf? Hohe Zahl = starke Kombination = sollte
    eher NICHT entfernt werden.
    """
    total = 0
    for t in needed:
        key = (machine, frozenset((tool, t)))
        total += combo_counts.get(key, 0)
    return total


def compute_tool_revolver(
        df: pd.DataFrame,
        strategy: str,
        usage_counts: dict | None = None,
        combo_counts: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simuliert die Werkzeugbelegung im Revolver, pro Maschine einzeln
    (kein Pooling mehr).

    strategy:
      - "fifo" (Baseline):
            Entfernt zuerst Tools, die auch der nächste Arbeitsschritt
            nicht braucht; bei mehreren Kandidaten FIFO.
      - "frequency" (Szenario 1):
            Entfernt zuerst die am seltensten benutzten Tools (maschinenweite
            Nutzungshäufigkeit); die meistgenutzten Tools bleiben so lange
            wie möglich drin.
      - "combo" (Szenario 2):
            Entfernt zuerst Tools mit der geringsten historischen
            Kombinationshäufigkeit zu den aktuell benötigten Tools.

    Erwartet eine Zeile pro Arbeitsschritt mit den Spalten
    AsID, Start, Maschine_Final, Tools, Ruestzeit.
    """
    if strategy == "frequency" and usage_counts is None:
        raise ValueError("strategy='frequency' benötigt usage_counts")
    if strategy == "combo" and combo_counts is None:
        raise ValueError("strategy='combo' benötigt combo_counts")

    df = df.copy()
    df = df.sort_values(["Maschine_Final", "Start"])

    results = []
    warnings = []

    for machine, group_df in df.groupby("Maschine_Final"):
        cap = MACHINE_CAPACITY.get(machine, None)
        loaded = []  # Liste statt Set -> Einfüge-Reihenfolge = FIFO-Reihenfolge

        rows = list(group_df.itertuples())

        for i, row in enumerate(rows):
            idx = row.Index
            needed = parse_tools(row.Tools)

            if cap is not None and len(needed) > cap:
                warnings.append({
                    "Maschine_Final": machine,
                    "AsID": row.AsID,
                    "needed": len(needed),
                    "capacity": cap
                })

            if i + 1 < len(rows):
                next_needed = parse_tools(rows[i + 1].Tools)
            else:
                next_needed = set()

            loaded_set = set(loaded)
            missing = needed - loaded_set

            tools_removed = []

            # Wenn die Maschine eine Kapazität hat und diese erreicht wurde und Werkzeuge hinzugefügt werden müssen
            if cap is not None and missing:
                free_slots = cap - len(loaded_set)
                slots_to_free = len(missing) - free_slots

                if slots_to_free > 0:
                    # Welche Werkzeuge sind im revolver die nicht benötigt werden.
                    removable = [t for t in loaded if t not in needed]

                    if strategy == "fifo":
                        # Tools, die der nächste Arbeitsschritt nicht braucht.
                        not_needed_next = [t for t in removable if t not in next_needed]
                        # Tools, die der nächste Arbeitsschritt braucht.
                        needed_next = [t for t in removable if t in next_needed]
                        # Erst Werkzeuge entfernen, die weder jetzt noch im nächsten Schritt gebraucht werden
                        ordered_candidates = not_needed_next + needed_next
                        # reihenfolge innerhalb der sets bleibt in FIFo Reihenfolge erhalten

                    elif strategy == "frequency":
                        # Entferne zuerst die Tools, die historisch am seltensten verwendet wurden.
                        ordered_candidates = sorted(
                            removable,
                            key=lambda t: usage_counts.get((machine, t), 0)
                        )

                    elif strategy == "combo":
                        # Wie häufig wurde dieses Tool gemeinsam mit den momentan benötigten Tools verwendet?
                        ordered_candidates = sorted(
                            removable,
                            key=lambda t: combo_affinity(t, needed, machine, combo_counts)
                        )

                    else:
                        raise ValueError(f"Unbekannte Strategie: {strategy}")

                    to_remove = ordered_candidates[:slots_to_free]
                    tools_removed = to_remove.copy()
                    to_remove_set = set(to_remove)
                    # Entferne die Werkzeuge aus dem Revolver, damit genug Platz für die in diesem Arbeitsschritt
                    # benötigten Werkzeuge ist
                    loaded = [t for t in loaded if t not in to_remove_set]

            # Füge die in diesem Arbeitsschritt benötigten Werkzeuge dem Revolver zu
            loaded_set = set(loaded)
            tools_added = []
            for tool in sorted(needed):
                if tool not in loaded_set:
                    loaded.append(tool)
                    loaded_set.add(tool)
                    tools_added.append(tool)

            results.append({
                "index": idx,
                "tools_removed": ", ".join(sorted(tools_removed)),
                "tools_added": ", ".join(sorted(tools_added)),
                "n_tools_removed": len(tools_removed),
                "n_tools_added": len(tools_added),
                "n_tool_changes": len(tools_removed) + len(tools_added),
                "tools_in_revolver": ", ".join(sorted(loaded)),
                "slots_used": len(loaded),
                "capacity": cap,
            })

    result_df = pd.DataFrame(results).set_index("index")
    warnings_df = pd.DataFrame(warnings)

    return df.join(result_df), warnings_df


# TODO wofür
def revolver_change_log(revolver_df: pd.DataFrame) -> pd.DataFrame:
    """Verdichtet den Revolververlauf auf die Arbeitsschritte, bei denen
    sich die Bestückung tatsächlich verändert."""
    revolver_df = revolver_df.sort_values(["Maschine_Final", "Start"])

    change_rows = []
    prev = None
    for _, row in revolver_df.iterrows():
        current = row["tools_in_revolver"]
        if current != prev:
            change_rows.append({
                "Maschine_Final": row["Maschine_Final"],
                "Start": row["Start"],
                "AsID": row["AsID"],
                "Ruestzeit": row["Ruestzeit"],
                "tools_removed": row["tools_removed"],
                "tools_added": row["tools_added"],
                "n_tools_removed": row["n_tools_removed"],
                "n_tools_added": row["n_tools_added"],
                "n_tool_changes": row["n_tool_changes"],
                "tools_in_revolver": row["tools_in_revolver"],
                "slots_used": row["slots_used"],
            })
            prev = current

    return pd.DataFrame(change_rows)


def analyze_setup_time_vs_tool_changes(revolver_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Untersucht den Zusammenhang zwischen Anzahl der Toolwechsel und
    Rüstzeit. Liefert Aggregation nach Anzahl Toolwechsel + Korrelationen."""
    df = revolver_df.copy()
    df = df[df["Ruestzeit"].notna() & (df["Ruestzeit"] > 0)].copy()

    if df.empty:
        return pd.DataFrame(), {"pearson": None, "spearman": None, "n": 0}

    summary = (
        df.groupby("n_tool_changes")
        .agg(
            anzahl=("Ruestzeit", "count"),
            durchschnitt=("Ruestzeit", "mean"),
            median=("Ruestzeit", "median"),
            minimum=("Ruestzeit", "min"),
            maximum=("Ruestzeit", "max"),
        )
        .reset_index()
        .sort_values("n_tool_changes")
    )
    for col in ["durchschnitt", "median", "minimum", "maximum"]:
        summary[col] = summary[col].round(2)

    pearson = df["n_tool_changes"].corr(df["Ruestzeit"], method="pearson")
    spearman = df["n_tool_changes"].corr(df["Ruestzeit"], method="spearman")

    stats = {
        "pearson": round(pearson, 4) if pd.notna(pearson) else None,
        "spearman": round(spearman, 4) if pd.notna(spearman) else None,
        "n": len(df),
    }
    return summary, stats


# ============================================================
# VERGLEICHSTABELLE: BASELINE VS. SZENARIEN
# (wird sowohl hier fürs Konsolen-Log als auch von Streamlit
#  live auf gefilterten Daten wiederverwendet)
# ============================================================

def compute_comparison_table(
        baseline_df: pd.DataFrame,
        scenario_dfs: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Baut die 'Vergleich'-Tabelle: eine Zeile für die Baseline plus eine
    Zeile pro Szenario in `scenario_dfs` ({Anzeigename: DataFrame}).

    Spalten: Szenario, Arbeitsschritte, Toolwechsel, Vermiedene Toolwechsel,
    Reduktion (%), Geschätzte Einsparung (s), Geschätzte Einsparung (h).

    Die avg. Rüstzeit pro Toolwechsel wird ausschließlich aus der Baseline
    berechnet (einzige Variante mit real beobachteten Rüstzeiten) und auf
    alle Szenarien angewendet.
    """
    valid = baseline_df[
        baseline_df["Ruestzeit"].notna()
        & (baseline_df["Ruestzeit"] > 0)
        & (baseline_df["n_tool_changes"] > 0)
        ]
    rate = valid["Ruestzeit"].sum() / valid["n_tool_changes"].sum() if not valid.empty else 0.0

    baseline_changes = int(baseline_df["n_tool_changes"].sum())

    rows = [{
        "Szenario": "Baseline (FIFO)",
        "Arbeitsschritte": len(baseline_df),
        "Toolwechsel": baseline_changes,
        "Vermiedene Toolwechsel": None,
        "Reduktion (%)": None,
        "Geschätzte Einsparung (s)": None,
        "Geschätzte Einsparung (h)": None,
    }]

    for name, scen_df in scenario_dfs.items():
        scen_changes = int(scen_df["n_tool_changes"].sum())
        vermieden = baseline_changes - scen_changes
        reduktion = (100.0 * vermieden / baseline_changes) if baseline_changes else 0.0
        einsparung_s = vermieden * rate
        rows.append({
            "Szenario": name,
            "Arbeitsschritte": len(scen_df),
            "Toolwechsel": scen_changes,
            "Vermiedene Toolwechsel": vermieden,
            "Reduktion (%)": round(reduktion, 1),
            "Geschätzte Einsparung (s)": round(einsparung_s, 1),
            "Geschätzte Einsparung (h)": round(einsparung_s / 3600, 2),
        })

    return pd.DataFrame(rows)


def build_report():
    db = Database(DB_PATH)

    print("Lade MaschineTools aus SQLite ...")
    maschine_tools = db.MaschineTools()
    maschine_tools.to_csv(f"{REPORT_DIR}/MaschineTools.csv", index=False)

    print("Lade arbeitsschritt_tools aus SQLite ...")
    arbeitsschritt_tools = db.arbeitsschritt_tools()
    arbeitsschritt_tools["Start"] = pd.to_datetime(arbeitsschritt_tools["Start"])

    print(f"{len(arbeitsschritt_tools)} Arbeitsschritte geladen.")

    print("Berechne Nutzungs- und Kombinationshäufigkeiten ...")
    usage_counts, combo_counts = precompute_usage_and_combo(arbeitsschritt_tools)

    # Baseline (bisheriges Verhalten)
    print("Simuliere Baseline (fifo) ...")
    revolver_df, warnings_df = compute_tool_revolver(arbeitsschritt_tools, strategy="fifo")
    revolver_df.to_csv(f"{REPORT_DIR}/ToolRevolver.csv", index=False)

    # Szenario 1: meistgenutzte Tools bevorzugt behalten
    print("Simuliere Szenario 1 (frequency) ...")
    revolver_freq_df, _ = compute_tool_revolver(arbeitsschritt_tools, strategy="frequency", usage_counts=usage_counts)
    revolver_freq_df.to_csv(f"{REPORT_DIR}/ToolRevolver_Szenario1_Frequency.csv", index=False)

    # Szenario 2: häufigste Toolkombinationen bevorzugt behalten
    print("Simuliere Szenario 2 (combo) ...")
    revolver_combo_df, _ = compute_tool_revolver(arbeitsschritt_tools, strategy="combo", combo_counts=combo_counts)
    revolver_combo_df.to_csv(f"{REPORT_DIR}/ToolRevolver_Szenario2_Combo.csv", index=False)

    verlauf_df = revolver_change_log(revolver_df)
    setup_summary_df, correlation = analyze_setup_time_vs_tool_changes(revolver_df)

    verlauf_df.to_csv(f"{REPORT_DIR}/ToolRevolverVerlauf.csv", index=False)
    warnings_df.to_csv(f"{REPORT_DIR}/ToolRevolverWarnings.csv", index=False)
    setup_summary_df.to_csv(f"{REPORT_DIR}/ToolRevolverSetupAnalyse.csv", index=False)

    # --------------------------------------------------
    # Vergleichstabelle (Gesamtdatensatz, ungefiltert - Streamlit
    # berechnet dieselbe Tabelle live auf gefilterten Daten)
    # --------------------------------------------------
    comparison_df = compute_comparison_table(
        revolver_df,
        {
            "Szenario 1: Meistgenutzte Tools": revolver_freq_df,
            "Szenario 2: Toolkombinationen": revolver_combo_df,
        },
    )
    comparison_df.to_csv(f"{REPORT_DIR}/SzenarienVergleich.csv", index=False)

    kategorisierung_df = db.zeiten_table_kategorisierung()
    kategorisierung_df.to_csv(f"{REPORT_DIR}/ZeitenTableKategorisierung.csv", index=False)

    print(
        f"Fertig. Baseline: {len(revolver_df)} Zeilen, "
        f"Verlauf: {len(verlauf_df)} Zeilen, "
        f"Warnungen: {len(warnings_df)}"
    )
    print()
    print("=== Zusammenhang Toolwechsel / Rüstzeit (Baseline) ===")
    print(f"Datensätze: {correlation['n']}")
    print(f"Pearson:    {correlation['pearson']}")
    print(f"Spearman:   {correlation['spearman']}")
    print()
    print("=== Vergleich (Gesamtdatensatz) ===")
    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    build_report()
