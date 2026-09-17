"""
FastAPI-Rewrite des Streamlit "Tool Nutzung"-Dashboards.

Ersetzt Streamlit 1:1 durch reines HTTP Request/Response (kein WebSocket,
kein SSE) - funktioniert daher auch hinter Proxies, die nur normale
HTTP-Requests durchreichen.

Start:
    python3 -m uvicorn main:app --host :: --port 8092

(identisch zu deinem bisherigen subprocess.run(["-m", "streamlit", "run", ...])
Aufruf - nur der Modulname ändert sich.)
"""

from __future__ import annotations

import json
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.express as px
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from Datenanalyse.build_revolver_report import compute_comparison_table

REPORT_DIR = Path("Datenanalyse/reports")
FRONTEND_DIR = Path("viz/frontend")

MACHINE_CAPACITY = {
    "C40": 121,
    "C400": 37,
    "RS2_1": 121,
    "RS2_2": 121,
    "Chiron": 48,
    "C42": 258,
    "Brother": 32,
}

DEFAULT_MACHINE = "C40"
DEFAULT_START = "2023-01-01"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATA LOADING  (ersetzt @st.cache_data)
# ============================================================

@lru_cache(maxsize=None)
def load(name: str, date_col: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(REPORT_DIR / f"{name}.csv")
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
    return df


def filter_time(df: pd.DataFrame, start_col: str, start_date, end_date) -> pd.DataFrame:
    return df[(df[start_col] >= start_date) & (df[start_col] < end_date)]


def filter_machine(df: pd.DataFrame, selection: str) -> pd.DataFrame:
    return df[df["Maschine_Final"] == selection]


def get_machine_filter_options(df: pd.DataFrame) -> list[str]:
    return sorted(df["Maschine_Final"].dropna().unique())


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


# ============================================================
# SERIALISIERUNGS-HELFER
# ============================================================

def fig_to_json(fig) -> dict:
    """Plotly Figure -> JSON-sicheres dict (Frontend macht Plotly.newPlot(el, d.data, d.layout))."""
    return json.loads(fig.to_json())


def df_to_records(df: pd.DataFrame) -> list[dict]:
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict(orient="records")


def parse_dates(start: Optional[str], end: Optional[str]):
    maschine_tools = load("MaschineTools", date_col="Start")
    min_date, max_date = maschine_tools["Start"].min(), maschine_tools["Start"].max()
    start_date = pd.to_datetime(start) if start else pd.to_datetime(DEFAULT_START)
    end_date = pd.to_datetime(end) if end else max_date
    return start_date, end_date, min_date, max_date


# ============================================================
# CHART-BUILDER  (1:1 aus dem Streamlit-Code übernommen,
#  nur st.plotly_chart(fig, ...) -> return fig)
# ============================================================

def build_top_tools_all(df: pd.DataFrame):
    tool_usage_all = (
        df.drop_duplicates(["AsID", "ToolName"])
        .groupby("ToolName")
        .size()
        .reset_index(name="usage_count")
        .sort_values("usage_count", ascending=False)
        .head(20)
    )
    fig = px.bar(
        tool_usage_all,
        x="usage_count",
        y="ToolName",
        orientation="h",
        title="Meist genutzte Tools (alle Maschinen)"
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def build_top10_machine(df: pd.DataFrame):
    top10 = (
        df.drop_duplicates(["AsID", "ToolName"])
        .groupby("ToolName")
        .size()
        .reset_index(name="usage_count")
        .sort_values("usage_count", ascending=False)
        .head(10)
    )
    fig = px.bar(
        top10,
        x="usage_count",
        y="ToolName",
        orientation="h",
        title="Top 10 Tools"
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def build_top_combos(df: pd.DataFrame, top_n_combos: int):
    job_tools = df[["AsID", "ToolName"]].drop_duplicates()
    combo_counts = compute_combo_counts(job_tools).head(top_n_combos)
    fig = px.bar(
        combo_counts,
        x="together_count",
        y=combo_counts["ToolName_x"] + " + " + combo_counts["ToolName_y"],
        orientation="h",
    )
    fig.update_yaxes(title_text="Toolkombination", autorange="reversed")
    return fig


def build_revolver_simulation(revolver_machine: pd.DataFrame, machine: str):
    fig = px.line(
        revolver_machine,
        x="Start",
        y="slots_used",
        labels={"Start": "Zeit", "slots_used": "Belegte Slots"},
    )
    cap = MACHINE_CAPACITY.get(machine)
    if cap is not None:
        fig.add_hline(
            y=cap,
            line_dash="dash",
            annotation_text=f"Kapazität ({cap})",
            annotation_position="top left",
            line_color="red",
        )
    return fig


def build_ruestzeit_vs_toolwechsel_all(revolver_df: pd.DataFrame):
    fig = px.scatter(
        revolver_df[revolver_df["Ruestzeit"].notna() & (revolver_df["Ruestzeit"] > 0)],
        x="n_tool_changes",
        y="Ruestzeit",
        hover_data=["Maschine_Final", "AsID", "n_tools_removed", "n_tools_added"],
        trendline="ols",
        labels={"n_tool_changes": "Anzahl Toolwechsel", "Ruestzeit": "Rüstzeit"},
        title="Rüstzeit vs. Anzahl Werkzeugwechsel (alle Maschinen)",
    )
    return fig


def build_ruestzeit_vs_toolwechsel(analyse_df: pd.DataFrame):
    fig = px.scatter(
        analyse_df,
        x="n_tool_changes",
        y="Ruestzeit",
        hover_data=["AsID", "n_tools_removed", "n_tools_added"],
        trendline="ols",
        labels={"n_tool_changes": "Anzahl Werkzeugwechsel", "Ruestzeit": "Rüstzeit"},
        title="Zusammenhang zwischen Werkzeugwechseln und Rüstzeit",
    )
    return fig


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/api/meta")
def api_meta():
    maschine_tools = load("MaschineTools", date_col="Start")
    machine_options = get_machine_filter_options(maschine_tools)
    min_date, max_date = maschine_tools["Start"].min(), maschine_tools["Start"].max()
    return {
        "machines": machine_options,
        "default_machine": DEFAULT_MACHINE if DEFAULT_MACHINE in machine_options else machine_options[0],
        "min_date": min_date.strftime("%Y-%m-%d"),
        "max_date": max_date.strftime("%Y-%m-%d"),
        "default_start": DEFAULT_START,
        "default_end": max_date.strftime("%Y-%m-%d"),
    }


@app.get("/api/uebersicht")
def api_uebersicht(start: Optional[str] = None, end: Optional[str] = None):
    start_date, end_date, _, _ = parse_dates(start, end)

    maschine_tools = filter_time(load("MaschineTools", date_col="Start"), "Start", start_date, end_date)
    revolver_df = filter_time(load("ToolRevolver", date_col="Start"), "Start", start_date, end_date)
    revolver_warnings = load("ToolRevolverWarnings")
    comparison_df = load("SzenarienVergleich")
    kategorisierung_df = load("ZeitenTableKategorisierung")

    row = kategorisierung_df.iloc[0]
    machine_nicht_zuordenbar = row["machine_leer"] + row["nur_pool"]
    kategorisierung_lines = [
        f"{row['gesamt']:>10,}  Arbeitsschritte",
        f"{'- ' + format(row['typ_ausschluss'], ',') :>12}  Typ ≠ Arbeitsschritt",
        f"{'- ' + format(row['keine_zeit'], ',') :>12}  Keine Zeit zugeordnet",
        f"{'- ' + format(machine_nicht_zuordenbar, ',') :>12}  Machine nicht zuordenbar",
        f"{'─' * 20}",
        f"{'= ' + format(row['final_in_zeiten_table'], ',') :>12}  In zeiten_table",
    ]

    return JSONResponse({
        "top_tools_all_chart": fig_to_json(build_top_tools_all(maschine_tools)),
        "warnings": {
            "count": len(revolver_warnings),
            "table": df_to_records(revolver_warnings.sort_values("AsID")) if not revolver_warnings.empty else [],
        },
        "ruestzeit_vs_toolwechsel_all_chart": fig_to_json(build_ruestzeit_vs_toolwechsel_all(revolver_df)),
        "kategorisierung_lines": kategorisierung_lines,
        "vergleich_all_table": df_to_records(comparison_df),
    })


@app.get("/api/revolver")
def api_revolver(
        start: Optional[str] = None,
        end: Optional[str] = None,
        machine: str = DEFAULT_MACHINE,
        top_n_combos: int = Query(10, ge=5, le=20),
):
    start_date, end_date, _, _ = parse_dates(start, end)

    maschine_tools = filter_time(load("MaschineTools", date_col="Start"), "Start", start_date, end_date)
    machine_tools_selected = filter_machine(maschine_tools, machine)

    revolver_df = filter_time(load("ToolRevolver", date_col="Start"), "Start", start_date, end_date)
    revolver_machine = revolver_df[revolver_df["Maschine_Final"] == machine]

    werkzeugverlauf = filter_time(load("ToolRevolverVerlauf", date_col="Start"), "Start", start_date, end_date)
    werkzeugverlauf_machine = werkzeugverlauf[werkzeugverlauf["Maschine_Final"] == machine]

    werkzeugverlauf_cols = [
        "Start", "AsID", "Ruestzeit", "n_tools_removed", "tools_removed",
        "n_tools_added", "tools_added", "slots_used", "tools_in_revolver",
    ]

    return JSONResponse({
        "werkzeugverlauf_table": df_to_records(werkzeugverlauf_machine[werkzeugverlauf_cols]),
        "top10_machine_chart": fig_to_json(build_top10_machine(machine_tools_selected)),
        "top_combos_chart": fig_to_json(build_top_combos(machine_tools_selected, top_n_combos)),
        "revolver_simulation_chart": fig_to_json(build_revolver_simulation(revolver_machine, machine)),
    })


@app.get("/api/ruestzeit")
def api_ruestzeit(
        start: Optional[str] = None,
        end: Optional[str] = None,
        machine: str = DEFAULT_MACHINE,
        exclude_zero_ruestzeit: bool = True,
        exclude_zero_changes: bool = True,
):
    start_date, end_date, _, _ = parse_dates(start, end)

    revolver_df = filter_time(load("ToolRevolver", date_col="Start"), "Start", start_date, end_date)
    revolver_machine = revolver_df[revolver_df["Maschine_Final"] == machine]

    mask = revolver_machine["Ruestzeit"].notna()
    if exclude_zero_ruestzeit:
        mask &= revolver_machine["Ruestzeit"] > 0
    else:
        mask &= revolver_machine["Ruestzeit"] >= 0
    if exclude_zero_changes:
        mask &= revolver_machine["n_tool_changes"] > 0

    analyse_df = revolver_machine[mask].copy()

    if analyse_df.empty:
        return JSONResponse({"empty": True})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        warnings.filterwarnings("ignore", message="An input array is constant")
        pearson = analyse_df["n_tool_changes"].corr(analyse_df["Ruestzeit"], method="pearson")
        spearman = analyse_df["n_tool_changes"].corr(analyse_df["Ruestzeit"], method="spearman")

    setup_summary = (
        analyse_df.groupby("n_tool_changes")
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

    return JSONResponse({
        "empty": False,
        "metrics": {
            "count": len(analyse_df),
            "pearson": None if pd.isna(pearson) else round(float(pearson), 3),
            "spearman": None if pd.isna(spearman) else round(float(spearman), 3),
        },
        "setup_summary_table": df_to_records(setup_summary),
        "scatter_chart": fig_to_json(build_ruestzeit_vs_toolwechsel(analyse_df)),
    })


@app.get("/api/vergleich")
def api_vergleich(start: Optional[str] = None, end: Optional[str] = None, machine: str = DEFAULT_MACHINE):
    start_date, end_date, _, _ = parse_dates(start, end)

    def load_filtered(name):
        df = filter_time(load(name, date_col="Start"), "Start", start_date, end_date)
        return df[df["Maschine_Final"] == machine]

    revolver_baseline = load_filtered("ToolRevolver")
    revolver_freq = load_filtered("ToolRevolver_Szenario1_Frequency")
    revolver_combo = load_filtered("ToolRevolver_Szenario2_Combo")

    comparison_df = compute_comparison_table(
        revolver_baseline,
        {
            "Szenario 1: Meistgenutzte Tools": revolver_freq,
            "Szenario 2: Toolkombinationen": revolver_combo,
        },
    )
    return JSONResponse({"table": df_to_records(comparison_df)})


# ============================================================
# STATIC FRONTEND  (gleiche Rolle wie Streamlits eigenes index.html)
# ============================================================

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


# @app.get("/app.js")
# def app_js():
#     return (FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")
#
# @app.get("/styles.js"))
# def app_js():
#     return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8092)