import warnings
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from Datenanalyse.build_revolver_report import compute_comparison_table

st.set_page_config(
    page_title="Tool Nutzung",
    layout="wide"
)

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


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
def load(name, date_col: str | None = None):
    df = pd.read_csv(f"{REPORT_DIR}/{name}.csv")
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
    return df

@st.cache_data
def get_date_bounds(df: pd.DataFrame, col: str) -> tuple:
    return df[col].min(), df[col].max()


def filter_time(df: pd.DataFrame, start_col: str, start_date, end_date) -> pd.DataFrame:
    """Filtert df anhand einer bereits geparsten Start-Spalte auf den globalen Zeitraum."""
    return df[(df[start_col] >= start_date) & (df[start_col] < end_date)]

@st.cache_data
def get_machine_filter_options(df: pd.DataFrame) -> list[str]:
    """Liefert die Auswahlliste für den globalen Maschinenfilter - jetzt
    einfach alle vorkommenden Maschine_Final-Werte, kein Pooling mehr."""
    return sorted(df["Maschine_Final"].dropna().unique())


def filter_machine(df: pd.DataFrame, selection: str) -> pd.DataFrame:
    """Filtert df auf die ausgewählte Maschine."""
    return df[df["Maschine_Final"] == selection]


# ============================================================
# CHART / SECTION FUNKTIONEN
# ============================================================

def show_top_tools_all(df: pd.DataFrame):
    """1. Meist genutzte Tools insgesamt (alle Maschinen, nur Zeitfilter)."""
    st.header("Meist genutzte Tools (alle Maschinen)")

    tool_usage_all = (
        df
        .drop_duplicates(["AsID", "ToolName"])
        .groupby("ToolName")
        .size()
        .reset_index(name="usage_count")
        .sort_values("usage_count", ascending=False)
        .head(20)
    )

    fig = px.bar(tool_usage_all, x="usage_count", y="ToolName", orientation="h")
    fig.update_yaxes(autorange="reversed")

    st.plotly_chart(fig, width="stretch", key="chart_top_tools_all")


def show_top10_machine(df: pd.DataFrame, machine: str):
    """2. Top 10 Tools auf ausgewählter Maschine (bereits auf Maschine+Zeit gefiltert)."""
    st.header(f"Top 10 Tools auf {machine}")

    top10_machine = (
        df
        .drop_duplicates(["AsID", "ToolName"])
        .groupby("ToolName")
        .size()
        .reset_index(name="usage_count")
        .sort_values("usage_count", ascending=False)
        .head(10)
    )

    fig = px.bar(top10_machine, x="usage_count", y="ToolName", orientation="h")
    fig.update_yaxes(autorange="reversed")

    st.plotly_chart(fig, width="stretch", key="chart_top10_machine")


@st.cache_data
def compute_combo_counts(job_tools: pd.DataFrame) -> pd.DataFrame:
    pairs = job_tools.merge(job_tools, on="AsID")
    pairs = pairs[pairs["ToolName_x"] < pairs["ToolName_y"]]
    return (
        pairs
        .groupby(["ToolName_x", "ToolName_y"])
        .size()
        .reset_index(name="together_count")
        .sort_values("together_count", ascending=False)
    )


def show_top_combos(df: pd.DataFrame, machine: str):
    st.header(f"Top Toolkombinationen auf {machine}")

    top_n_combos = st.slider("Anzahl Toolkombinationen", 5, 20, 10, key="slider_top_combos")

    job_tools = df[["AsID", "ToolName"]].drop_duplicates()
    combo_counts = compute_combo_counts(job_tools).head(top_n_combos)

    fig = px.bar(
        combo_counts,
        x="together_count",
        y=combo_counts["ToolName_x"] + " + " + combo_counts["ToolName_y"],
        orientation="h"
    )
    fig.update_yaxes(title_text="Toolkombination", autorange="reversed")

    st.plotly_chart(fig, width="stretch", key="chart_top_combos")


def show_tool_changes(df: pd.DataFrame, machine: str):
    st.header(f"Tool-Belegungsänderungen auf {machine}")

    job_toolsets = (
        df
        .dropna(subset=["ToolName"])
        .groupby(["AsID", "Start"])["ToolName"]
        .apply(lambda s: frozenset(s))
        .reset_index(name="tool_set")
        .sort_values("Start")
    )

    changed_mask = job_toolsets["tool_set"] != job_toolsets["tool_set"].shift()
    changes_table = job_toolsets.loc[changed_mask, ["Start", "AsID", "tool_set"]].copy()
    changes_table["AktuelleTools"] = changes_table["tool_set"].apply(lambda s: ", ".join(sorted(s)))
    changes_table = changes_table.drop(columns="tool_set")

    st.dataframe(changes_table, width="stretch", hide_index=True, key="table_tool_changes")


def show_warnings(warnings_df: pd.DataFrame):
    """5. Revolver-Simulation (pro Maschine, mit Kapazitätslogik).
    `revolver_machine` kommt bereits nach Zeit UND Maschine gefiltert von
    main(), damit dieselben gefilterten Daten auch im Rüstzeit-Tab
    wiederverwendet werden können."""
    st.header("Werkzeug-Revolver Simulation")

    st.write(
        "Simuliert die tatsächliche Werkzeugbelegung im Revolver pro Maschine, "
        "inklusive Kapazitätsgrenze und FIFO-Ersetzung. "
        "Wird per `build_revolver_report.py` offline erzeugt."
    )

    if not warnings_df.empty:
        st.warning(
            f"{len(warnings_df)} Arbeitsschritte benötigen mehr Tools "
            f"als die Revolver-Kapazität der jeweiligen Maschine zulässt."
        )
        st.dataframe(warnings_df.sort_values("AsID"), width="stretch", hide_index=True, key="table_revolver_warnings")


def show_revolver_simulation(revolver_machine: pd.DataFrame, machine: str):
    fig = px.line(
        revolver_machine,
        x="Start",
        y="slots_used",
        labels={"Start": "Zeit", "slots_used": "Belegte Slots"}
    )

    cap = MACHINE_CAPACITY.get(machine)
    if cap is not None:
        fig.add_hline(
            y=cap,
            line_dash="dash",
            annotation_text=f"Kapazität ({cap})",
            annotation_position="top left",
            line_color="red"
        )

    st.plotly_chart(fig, width="stretch", key="chart_revolver_simulation")


def show_werkzeugverlauf(werkzeugverlauf_df: pd.DataFrame, machine: str):
    """6. Werkzeugverlauf (verdichtete Änderungstabelle mit Kapazitätslogik)."""
    st.header(f"Werkzeugverlauf auf {machine}")

    werkzeugverlauf_machine = werkzeugverlauf_df[werkzeugverlauf_df["Maschine_Final"] == machine]

    st.dataframe(
        werkzeugverlauf_machine[
            [
                "Start",
                "AsID",
                "Ruestzeit",
                "n_tools_removed",
                "tools_removed",
                "n_tools_added",
                "tools_added",
                "slots_used",
                "tools_in_revolver",
            ]
        ],
        width="stretch",
        hide_index=True,
        key="table_werkzeugverlauf"
    )


def show_ruestzeit_vs_toolwechsel(revolver_machine: pd.DataFrame, machine: str):
    """7. Rüstzeit vs. Werkzeugwechsel, nur für die ausgewählte Maschine."""
    st.header(f"Rüstzeit vs. Anzahl Werkzeugwechsel auf {machine}")

    col_ex1, col_ex2 = st.columns(2)
    exclude_zero_ruestzeit = col_ex1.checkbox(
        "Rüstzeit = 0 ausschließen",
        value=True,
        key="checkbox_exclude_zero_ruestzeit"
    )
    exclude_zero_changes = col_ex2.checkbox(
        "Werkzeugwechsel = 0 ausschließen",
        value=True,
        key="checkbox_exclude_zero_changes"
    )

    mask = revolver_machine["Ruestzeit"].notna()
    if exclude_zero_ruestzeit:
        mask &= revolver_machine["Ruestzeit"] > 0
    else:
        mask &= revolver_machine["Ruestzeit"] >= 0

    if exclude_zero_changes:
        mask &= revolver_machine["n_tool_changes"] > 0

    analyse_df = revolver_machine[mask].copy()

    if analyse_df.empty:
        st.info("Für den ausgewählten Zeitraum liegen keine gültigen Rüstzeitdaten vor.")
        return

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        warnings.filterwarnings("ignore", message="An input array is constant")
        pearson = analyse_df["n_tool_changes"].corr(analyse_df["Ruestzeit"], method="pearson")
        spearman = analyse_df["n_tool_changes"].corr(analyse_df["Ruestzeit"], method="spearman")

    col1, col2, col3 = st.columns(3)
    col1.metric("Arbeitsschritte", len(analyse_df))
    col2.metric("Pearson-Korrelation", f"{pearson:.3f}" if pd.notna(pearson) else "-")
    col3.metric("Spearman-Korrelation", f"{spearman:.3f}" if pd.notna(spearman) else "-")

    setup_summary = (
        analyse_df
        .groupby("n_tool_changes")
        .agg(
            Arbeitsschritte=("Ruestzeit", "count"),
            Durchschnitt_Ruestzeit=("Ruestzeit", "mean"),
            Median_Ruestzeit=("Ruestzeit", "median"),
            Min_Ruestzeit=("Ruestzeit", "min"),
            Max_Ruestzeit=("Ruestzeit", "max"),
        )
        .reset_index()
        .sort_values("n_tool_changes")
    )

    round_cols = ["Durchschnitt_Ruestzeit", "Median_Ruestzeit", "Min_Ruestzeit", "Max_Ruestzeit"]
    setup_summary[round_cols] = setup_summary[round_cols].round(2)

    st.subheader("Durchschnittliche Rüstzeit je Werkzeugwechsel")
    st.dataframe(setup_summary, width="stretch", hide_index=True, key="table_setup_summary")

    fig_setup = px.scatter(
        analyse_df,
        x="n_tool_changes",
        y="Ruestzeit",
        hover_data=["AsID", "n_tools_removed", "n_tools_added"],
        trendline="ols",
        labels={"n_tool_changes": "Anzahl Werkzeugwechsel", "Ruestzeit": "Rüstzeit"},
        title="Zusammenhang zwischen Werkzeugwechseln und Rüstzeit",
    )

    st.plotly_chart(fig_setup, width="stretch", key="chart_ruestzeit_toolwechsel")


def show_ruestzeit_vs_toolwechsel_all(revolver_df: pd.DataFrame):
    fig = px.scatter(
        revolver_df[revolver_df["Ruestzeit"].notna() & (revolver_df["Ruestzeit"] > 0)],
        x="n_tool_changes",
        y="Ruestzeit",
        hover_data=["Maschine_Final", "AsID", "n_tools_removed", "n_tools_added"],
        trendline="ols",
        labels={"n_tool_changes": "Anzahl Toolwechsel", "Ruestzeit": "Rüstzeit"},
        title="Rüstzeit vs. Anzahl Werkzeugwechsel (alle Maschinen)"
    )

    st.plotly_chart(fig, width="stretch", key="chart_werkzeugverlauf_scatter")


def show_vergleich(
        revolver_baseline: pd.DataFrame,
        revolver_freq: pd.DataFrame,
        revolver_combo: pd.DataFrame,
        machine: str
):
    st.header(f"Vergleich auf {machine}")

    comparison_df = compute_comparison_table(
        revolver_baseline,
        {
            "Szenario 1: Meistgenutzte Tools": revolver_freq,
            "Szenario 2: Toolkombinationen": revolver_combo,
        },
    )

    st.dataframe(
        comparison_df,
        width="stretch",
        hide_index=True,
        key="table_vergleich",
        column_config={
            "Reduktion (%)": st.column_config.NumberColumn(format="%.1f"),
        },
    )


def show_vergleich_all(comparison_df: pd.DataFrame):
    st.header("Vergleich")

    st.dataframe(
        comparison_df,
        width="stretch",
        hide_index=True,
        key="table_vergleich_all",
        column_config={
            "Reduktion (%)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

def show_zeiten_table_kategorisierung(kategorisierung_df: pd.DataFrame):
    """Zeigt als Subtraktionskette, wie sich alle Arbeitsschritte auf die
    Gründe verteilen, warum sie (nicht) in zeiten_table landen."""
    st.header("Warum landen Arbeitsschritte nicht in zeiten_table?")

    row = kategorisierung_df.iloc[0]
    gesamt = row["gesamt"]
    machine_nicht_zuordenbar = row["machine_leer"] + row["nur_pool"]

    lines = [
        f"{gesamt:>10,}  Arbeitsschritte",
        f"{'- ' + format(row['typ_ausschluss'], ',') :>12}  Typ ≠ Arbeitsschritt",
        f"{'- ' + format(row['keine_zeit'], ',') :>12}  Keine Zeit zugeordnet",
        f"{'- ' + format(machine_nicht_zuordenbar, ',') :>12}  Machine nicht zuordenbar",
        f"{'─' * 20}",
        f"{'= ' + format(row['final_in_zeiten_table'], ',') :>12}  In zeiten_table",
    ]

    st.code("\n".join(lines), language=None)


@st.fragment
def render_uebersicht_tab(maschine_tools, revolver_warnings, revolver_df, comparison_df, kategorisierung_df):
    show_top_tools_all(maschine_tools)
    show_warnings(revolver_warnings)
    show_ruestzeit_vs_toolwechsel_all(revolver_df)
    show_zeiten_table_kategorisierung(kategorisierung_df)
    show_vergleich_all(comparison_df)


@st.fragment
def render_revolver_tab(werkzeugverlauf, machine_tools_selected, revolver_machine, selection):
    show_werkzeugverlauf(werkzeugverlauf, selection)
    show_top10_machine(machine_tools_selected, selection)
    show_top_combos(machine_tools_selected, selection)
    show_revolver_simulation(revolver_machine, selection)


@st.fragment
def render_ruestzeit_tab(revolver_machine, selection):
    show_ruestzeit_vs_toolwechsel(revolver_machine, selection)


@st.fragment
def render_vergleich_tab(revolver_machine, revolver_freq_machine, revolver_combo_machine, selection):
    show_vergleich(revolver_machine, revolver_freq_machine, revolver_combo_machine, selection)


def main():
    st.title("Tool Nutzung Dashboard")

    # --- Globale Daten + Filter ---
    maschine_tools = load("MaschineTools", date_col="Start")
    machine_options = get_machine_filter_options(maschine_tools)

    min_date, max_date = get_date_bounds(maschine_tools, "Start")

    default_machine = "C40"
    default_start_date = date(2023, 1, 1)
    default_end_date = max_date

    date_range = st.sidebar.date_input("Timeframe", value=(default_start_date, default_end_date), min_value=min_date,
                                       max_value=max_date, help="Hier die gewünschte Zeitspanne auswählen")
    selection = st.sidebar.selectbox("Maschine auswählen", machine_options,
                                     index=machine_options.index(default_machine), help="Die verfügbaren Maschinen für den ausgewählten Zeitraum")

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start_date, default_end_date

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    maschine_tools = filter_time(maschine_tools, "Start", start_date, end_date)
    machine_tools_selected = filter_machine(maschine_tools, selection)

    # --- Revolver-Daten (Baseline + beide Szenarien) einmal laden & filtern,
    #     werden in mehreren Tabs gebraucht ---
    revolver_df = load("ToolRevolver", date_col="Start")
    revolver_df = filter_time(revolver_df, "Start", start_date, end_date)
    revolver_machine = revolver_df[revolver_df["Maschine_Final"] == selection]

    revolver_freq_df = load("ToolRevolver_Szenario1_Frequency", date_col="Start")
    revolver_freq_df = filter_time(revolver_freq_df, "Start", start_date, end_date)
    revolver_freq_machine = revolver_freq_df[revolver_freq_df["Maschine_Final"] == selection]

    revolver_combo_df = load("ToolRevolver_Szenario2_Combo", date_col="Start")
    revolver_combo_df = filter_time(revolver_combo_df, "Start", start_date, end_date)
    revolver_combo_machine = revolver_combo_df[revolver_combo_df["Maschine_Final"] == selection]

    werkzeugverlauf = load("ToolRevolverVerlauf", date_col="Start")
    werkzeugverlauf = filter_time(werkzeugverlauf, "Start", start_date, end_date)

    revolver_warnings = load("ToolRevolverWarnings")

    comparison_df = load("SzenarienVergleich")
    kategorisierung_df = load("ZeitenTableKategorisierung")

    # --- Tabs ---
    tab_uebersicht, tab_revolver, tab_ruestzeit, tab_vergleich = st.tabs(
        ["Übersicht (alle Maschinen)", "Revolver Simulation", "Rüstzeit Analyse", "Vergleich"]
    )

    with tab_uebersicht:
        render_uebersicht_tab(maschine_tools, revolver_warnings, revolver_df, comparison_df, kategorisierung_df)

    with tab_revolver:
        render_revolver_tab(werkzeugverlauf, machine_tools_selected, revolver_machine, selection)

    with tab_ruestzeit:
        render_ruestzeit_tab(revolver_machine, selection)

    with tab_vergleich:
        render_vergleich_tab(revolver_machine, revolver_freq_machine, revolver_combo_machine, selection)


if __name__ == "__main__":
    main()
