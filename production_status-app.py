# -*- coding: utf-8 -*-
"""
Created on Wed Feb 26 15:01:15 2026

@author: akhalid
"""

import os
import pandas as pd
import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone
from time import sleep
from stqdm import stqdm
import re
import requests
from collections import defaultdict

import ui


# =============================================================================
# Helper functions
# =============================================================================




def get_last_modified(owner: str, repo: str, path: str):
    """
    Get last commit timestamp for a given path in a GitHub repo.
    Returns an aware datetime in UTC or None if unavailable.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "page": 1, "per_page": 1}

    try:
        r = requests.get(url, params=params, timeout=10)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    data = r.json()
    if not data:
        return None

    timestamp = data[0]["commit"]["committer"]["date"]  # e.g. "2026-02-20T19:22:37Z"
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return dt


def highlight_status(row):
    """
    Row-wise styling for a Pandas DataFrame (if used in st.dataframe(pdStyler)).
    """
    color = ""
    status = str(row.get("Status", "")).lower()
    if status == "success":
        color = "background-color: lightgreen"
    elif "failed" in status:
        color = "background-color: lightcoral"
    elif status == "running":
        color = "background-color: lightblue"
    return [color] * len(row)


# =============================================================================
# Scenario configuration
# =============================================================================

# Centralized scenario registry
SCENARIOS = {
    "cpra_base": {
         "title": "CPRA BASELINE",
         "category": "Base",
         "start_date": datetime(2026, 5, 28),
         "completion_date_projected": datetime(2026, 5, 31),
         "completion_date_actual": datetime(2026, 5, 31),       
         "total_simulations": 645,
     },
    "optimal_sample_base": {
        "title": "Optimal Sample - BASE - NO SLR",
        "category": "Tropical Cyclones",
        "start_date": datetime(2026, 6, 1),
        "completion_date_projected": datetime(2026, 6, 21),
        "completion_date_actual": datetime(2026, 6, 24),        
        "total_simulations": 10000,
    },
    "nontc_synthetic_base": {
        "title": "Synthetic Non-TC - BASE - NO SLR",
        "category": "Non-Tropical Cyclones",
        "start_date": datetime(2026, 11, 15),
        "completion_date_projected": datetime(2026, 12, 5),
        "completion_date_actual": datetime(2026, 12, 5),
        "total_simulations": 10000,  # all non-TC regions; per-region targets in REGION_TOTALS
    },

}

def group_scenarios(scenarios):
    grouped = defaultdict(dict)
    for key, cfg in scenarios.items():
        category = cfg.get("category", "Other")
        grouped[category][key] = cfg
    return grouped
GROUPED_SCENARIOS = group_scenarios(SCENARIOS)



# Default scenario key (as requested)
DEFAULT_SCENARIO_KEY = "optimal_sample_base"
DEFAULT_SCENARIO_KEY = "nontc_synthetic_base"

# Data root
ROOT_DIR = r"https://raw.githubusercontent.com/akhalid-twi/LWI-production/refs/heads/main/assets"



st.set_page_config(page_title="LWI Production", page_icon="🌊", layout="wide")

# =============================================================================
# Data loading helpers (cached)
# =============================================================================

@st.cache_data(ttl=60)  # refresh every 60 seconds
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(ttl=60)  # refresh every 60 seconds
def load_csv_with_index(path: str, index_col: str) -> pd.DataFrame:
    return pd.read_csv(path, index_col=index_col)


def build_paths(scenario_key: str):
    csv_basic = f"{scenario_key}_simulation_basic_summary.csv"
    csv_hdf = f"{scenario_key}_simulation_HDF_summary.csv"
    url_basic = f"{ROOT_DIR}/{csv_basic}"
    url_hdf = f"{ROOT_DIR}/{csv_hdf}"
    return csv_basic, csv_hdf, url_basic, url_hdf


def load_merged_dataframe(scenario_key: str) -> pd.DataFrame:
    """
    Loads the two CSVs for a scenario, merges/aligns them and returns a single DataFrame.
    """
    csv_basic, csv_hdf, url_basic, url_hdf = build_paths(scenario_key)

    # Load basic summary
    df_basic = load_csv(url_basic)
    # Standardize index
    df_basic["_index"] = df_basic["Directory"]
    df_basic = df_basic.set_index("_index")

    # Load HDF summary (uses 'folder' as index)
    df_hdf = load_csv_with_index(url_hdf, index_col="folder")

    # Merge HDF-derived metrics into df_basic
    # We assign by aligned index; ensure the indices match logically
    # If directories differ from folder keys, consider a join/merge with a key mapping
    if "max_wse" in df_hdf.columns:
        df_basic["Max WSE (ft)"] = df_hdf["max_wse"]
    if "max_depth" in df_hdf.columns:
        df_basic["Max Depth (ft)"] = df_hdf["max_depth"]
    if "max_volume" in df_hdf.columns:
        df_basic["Max Volume (ft^3)"] = df_hdf["max_volume"]
    if "max_flow_balance" in df_hdf.columns:
        df_basic["Max Flow Balance (ft^3/s)"] = df_hdf["max_flow_balance"]

    # Stage BC (two potential column names)
    if "max_bc_stage" in df_hdf.columns:
        df_basic["Max Stage BC (ft)"] = df_hdf["max_bc_stage"]
    elif "max_bc_stage_EventCond" in df_hdf.columns:
        df_basic["Max Stage BC (ft)"] = df_hdf["max_bc_stage_EventCond"]

    # Flow BC (two potential column names)
    if "max_bc_flow" in df_hdf.columns:
        df_basic["Max Inflow BC (cfs)"] = df_hdf["max_bc_flow"]
    elif "max_bc_flow_EventCond" in df_hdf.columns:
        df_basic["Max Inflow BC (cfs)"] = df_hdf["max_bc_flow_EventCond"]

    # Cum PRCP
    if "max_prcp_EventCond" in df_hdf.columns:
        df_basic["Max Cum PRCP (in)"] = df_hdf["max_prcp_EventCond"]
    
        

    # Sorting & reset for display
    if "Directory" in df_basic.columns:
        df_basic = df_basic.sort_values(by="Directory")
    df_basic = df_basic.reset_index(drop=True)
    return df_basic


def get_last_updated_dt(scenario_key: str):
    """
    Detects last modified time for the basic summary CSV.
    Works for GitHub raw URLs via the GitHub API.
    """
    csv_basic, _, _, _ = build_paths(scenario_key)

    if "githubusercontent" not in ROOT_DIR:
        try:
            modified_timestamp = os.path.getmtime(f"{ROOT_DIR}/{csv_basic}")
            modified_datetime = datetime.fromtimestamp(modified_timestamp, tz=timezone.utc)
        except Exception:
            modified_datetime = None
    else:
        # Path within repo
        modified_datetime = get_last_modified(
            owner="akhalid-twi",
            repo="LWI-production",
            path=f"assets/{csv_basic}",
        )
    return modified_datetime



# =============================================================================
# App UI
# =============================================================================
ui.inject()

# --- sidebar: which scenario (category, then scenario) ---
if "scenario_current" not in st.session_state:
    st.session_state.scenario_current = DEFAULT_SCENARIO_KEY

with st.sidebar:
    st.markdown("### Scenario")
    categories = list(GROUPED_SCENARIOS.keys())
    current_category = SCENARIOS[st.session_state.scenario_current].get("category", categories[0])
    selected_category = st.selectbox("Category", categories, index=categories.index(current_category))
    scenarios_dict = GROUPED_SCENARIOS[selected_category]
    keys = list(scenarios_dict)
    default_idx = keys.index(st.session_state.scenario_current) if st.session_state.scenario_current in keys else 0
    st.session_state.scenario_current = st.radio(
        "Scenario", keys, index=default_idx, format_func=lambda k: SCENARIOS[k]["title"],
        key="single_scenario_radio")
    st.markdown("&nbsp;")
    st.page_link("pages/1_Live_progress.py", label="Live progress: every storm", icon="📡")

scenario_key = st.session_state.scenario_current
scenario_cfg = SCENARIOS[scenario_key]


def _get_last_updated_safe(_scenario_key: str):
    try:
        return get_last_updated_dt(_scenario_key)
    except Exception:
        return None


def _ago(dt):
    if not dt:
        return "Update time unknown"
    mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if mins < 1:
        return "Updated just now"
    if mins < 60:
        return f"Updated {mins} min ago"
    if mins < 48 * 60:
        return f"Updated {mins // 60} h {mins % 60:02d} min ago"
    return f"Updated {dt:%d %b %Y}"


with st.spinner(f"Loading {scenario_cfg['title']}…"):
    modified_datetime = _get_last_updated_safe(scenario_key)
    try:
        df = load_merged_dataframe(scenario_key)
    except Exception as e:
        st.error(f"Failed to load data for scenario '{scenario_key}': {e}")
        st.stop()

    # counts from the live storm table (lwicheck on every platform), so this page, the Live
    # progress page and lwicheck agree; the older run summary (df) stays the source for the charts
    try:
        _p = load_csv(f"{ROOT_DIR}/{scenario_key}_simulation_progress.csv")
        _status = {"COMPLETE": "SUCCESS", "RUNNING": "Running", "PRE-PROC": "Running", "POST-PROC": "Running",
                   "FAILED": "Failed", "STOPPED": "Stopped", "QUEUED": "Queued"}
        dfc = _p.assign(Status=_p.Status.map(_status))
    except Exception:
        dfc = df

completed_simulations = int((dfc.Status == "SUCCESS").sum())
running_now = int((dfc.Status == "Running").sum())
queued_now = int((dfc.Status == "Queued").sum())
total_simulations = int(scenario_cfg.get("total_simulations", 10_000))
remaining = max(total_simulations - completed_simulations, 0)
progress_percent = min(completed_simulations / total_simulations * 100, 100) if total_simulations else 0

# storms per region in the non-TC production (dropped storms excluded)
REGION_TOTALS = {"West": 2077, "Northeast": 2014, "Central": 3000, "Southeast": 3000}   # Central, Southeast: approximate until generated
REGION_RE = r"syn_event_([A-Za-z]+)_"
non_tc = scenario_cfg.get("category") == "Non-Tropical Cyclones" and "Directory" in dfc.columns
region_of = (dfc["Directory"].astype(str).str.extract(REGION_RE, expand=False).fillna("Other")
             if "Directory" in dfc.columns else None)

C = ui.COLORS

# --- header ---
fresh = ui.dot(C["complete"] if modified_datetime and
               (datetime.now(timezone.utc) - modified_datetime).total_seconds() < 3 * 3600 else C["stopped"])
ui.header("LWI Production", scenario_cfg["title"], scenario_cfg["category"],
          pill=f"{fresh}{ui.esc(_ago(modified_datetime))}")

# --- hero: overall ring + headline numbers + timeline ---
now = datetime.now()
target = scenario_cfg["completion_date_actual"]
left = target - now
if progress_percent >= 99.5:
    timing, timing_color = "Complete", C["complete"]
elif left.total_seconds() >= 0:
    timing, timing_color = f"{left.days} days {left.seconds // 3600} h left", C["running"]
else:
    timing, timing_color = f"Overdue by {abs(left.days)} days", C["failed"]

ring = ui.ring([(completed_simulations, C["complete"]), (running_now, C["running"]), (queued_now, C["queued"])],
               total_simulations,
               size=176, width=18, center=f"{progress_percent:.0f}%", sub="complete")
kpis = "".join([
    ui.kpi("Completed", f"{completed_simulations:,}", f"of {total_simulations:,} storms", C["complete"]),
    ui.kpi("Running", f"{running_now:,}", "on all platforms", C["running"]),
    ui.kpi("Queued", f"{queued_now:,}", "waiting for nodes", C["queued"]),
    ui.kpi("Remaining", f"{remaining:,}", "not yet complete"),
])
ui.raw(f'<div class="lwi-card"><div class="lwi-hero">{ring}<div class="lwi-kpis">{kpis}</div></div>'
       f'<div class="lwi-chips" style="margin-top:18px">'
       f'{ui.chip("Started " + scenario_cfg["start_date"].strftime("%d %b"))}'
       f'{ui.chip("Target " + target.strftime("%d %b %Y"))}'
       f'{ui.chip(timing, timing_color)}</div></div>')

# --- regions: one ring per region ---
if non_tc:
    ui.section("Regions")
    by_reg = dfc.assign(Region=region_of).groupby(["Region", "Status"]).size().unstack(fill_value=0)
    cards = []
    for region, total in REGION_TOTALS.items():
        r = by_reg.loc[region] if region in by_reg.index else {}
        done, run, que = int(r.get("SUCCESS", 0)), int(r.get("Running", 0)), int(r.get("Queued", 0))
        bad = int(r.get("Failed", 0)) + int(r.get("Stopped", 0))
        started = done + run + que > 0
        pct = 100 * done / total if total else 0
        chips = ("".join([ui.chip(f"{run:,} running", C["running"]) if run else "",
                          ui.chip(f"{que:,} queued", C["queued"]) if que else "",
                          ui.chip(f"{bad:,} to rerun", C["failed"]) if bad else ""])
                 if started else ui.chip("Not started"))
        cards.append(
            f'<div class="lwi-card lwi-region">'
            f'{ui.ring([(done, C["complete"]), (run, C["running"]), (que, C["queued"])], total, size=92, width=11, center=f"{pct:.0f}%")}'
            f'<div><div class="lwi-region-name">{ui.esc(region)}</div>'
            f'<div class="lwi-region-num">{done:,} of {total:,} storms</div>'
            f'<div class="lwi-chips">{chips}</div></div></div>')
    ui.raw(f'<div class="lwi-grid">{"".join(cards)}</div>')

# --- where the storms run: grouped by system (AWS clusters, then Stampede3 accounts) ---
if "Platform" in dfc.columns:
    def _place(pl):
        """Platform label -> (system, row name). 'AWS' = cluster 1, 'AWS2 (...)' = cluster 2,
        'Stampede3 (<user>)' = one row per TACC account."""
        pl = str(pl)
        if pl.startswith("AWS2"):
            return "AWS", "AWS2 · cluster 2, us-east-2c"
        if pl.startswith("AWS"):
            return "AWS", "AWS1 · cluster 1, us-east-2a"
        m = re.match(r"Stampede3 \((.+)\)", pl)
        return ("TACC Stampede3", m.group(1)) if m else ("Other", pl)

    act = dfc[dfc.Status.isin(["SUCCESS", "Running", "Queued"]) & (dfc.Platform.fillna("-") != "-")].copy()
    if len(act):
        ui.section("Where storms run")
        act[["System", "Row"]] = [list(_place(p)) for p in act.Platform]
        act["Region"] = region_of[act.index] if region_of is not None else "-"
        lists = []
        for system in ["AWS", "TACC Stampede3", "Other"]:
            g = act[act.System == system]
            if not len(g):
                continue
            rows = []
            for name, gr in g.groupby("Row", sort=True):
                regs = []
                for reg, rr in gr.groupby("Region"):
                    run, que = int((rr.Status == "Running").sum()), int((rr.Status == "Queued").sum())
                    regs.append(reg + (f" · {run:,} running" if run else "") + (f" · {que:,} queued" if que else "")
                                if (run or que) else f"{reg} · done")
                rows.append((name, "   |   ".join(regs),
                             (f'{int((gr.Status == "Running").sum()):,}', "running"),
                             (f'{int((gr.Status == "SUCCESS").sum()):,}', "completed")))
            lists.append(ui.grouped_list(system, rows))
        ui.raw(f'<div class="lwi-grid" style="grid-template-columns:repeat(auto-fit,minmax(420px,1fr))">'
               f'{"".join(lists)}</div>')

# =============================================================================
# Details: one region filter, then tabs instead of one long scroll
# =============================================================================
ui.section("Details", "charts and the full table")

region_df = df["Directory"].astype(str).str.extract(REGION_RE, expand=False).fillna("Other")
detail_total = total_simulations
if non_tc:
    regions = [r for r in REGION_TOTALS if (region_df == r).any()]
    pick = st.segmented_control("Region", ["All regions"] + regions, default="All regions",
                                label_visibility="collapsed") or "All regions"
    if pick != "All regions":
        df = df[(region_df == pick).to_numpy()].copy()
        detail_total = REGION_TOTALS[pick] or len(df)


def _family(status):
    s = str(status).strip().lower()
    if s == "success":
        return "Complete"
    if s == "running":
        return "Running"
    if "fail" in s:
        return "Failed"
    if s == "not started":
        return "Not started"
    return "Other"


FAMILY_COLORS = {"Complete": C["complete"], "Running": C["running"], "Failed": C["failed"], "Other": C["stopped"],
                 "Not started": C["queued"]}
df = df.reset_index(drop=True)
df["Storm Number"] = df.index + 1
df["Result"] = df["Status"].map(_family)
for col in ["Vol Error (AF)", "Vol Error (%)", "Max WSEL Err", "SUs"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def dots(data, y, title, yrange=None, ytitle=None, color_by="Result", colors=FAMILY_COLORS, extra=None):
    """One dot per storm (readable at thousands of storms, unlike thousands of bars)."""
    if y not in data.columns or not data[y].notna().any():
        st.info(f"No {ytitle or y} values for this selection yet.")
        return
    fig = go.Figure()
    for name, g in data.groupby(color_by, sort=False):
        fig.add_trace(go.Scattergl(
            x=g["Storm Number"], y=g[y], mode="markers", name=str(name),
            marker=dict(size=6, color=colors.get(name, ui.INK_3), line=dict(width=0)),
            customdata=g[["Directory"]],
            hovertemplate="<b>%{customdata[0]}</b><br>" + f"{ytitle or y}: " + "%{y:,.3g}<extra></extra>"))
    if extra:
        extra(fig)
    if yrange:
        fig.update_yaxes(range=yrange)
    ui.style_fig(fig, 320, title, ytitle or y, "Storm (sorted by name)")
    st.plotly_chart(fig, config=ui.PLOT_CONFIG, use_container_width=True)


tab_status, tab_quality, tab_outputs, tab_compute, tab_corr, tab_table = st.tabs(
    ["Status", "Quality", "Model outputs", "Compute", "Correlation", "Table"])

with tab_status:
    ok = int((df.Result == "Complete").sum())
    run = int((df.Result == "Running").sum())
    fail = int((df.Result == "Failed").sum())
    other = int((df.Result == "Other").sum())
    waiting = max(detail_total - ok - run - fail - other, 0)
    ui.raw(f'<div class="lwi-card"><div class="lwi-kpi-label" style="margin-bottom:10px">'
           f'Run summary · {len(df):,} storms with a run folder, {detail_total:,} planned</div>'
           + ui.stacked_bar([(ok, C["complete"], "Complete"), (run, C["running"], "Running"),
                             (fail, C["failed"], "Failed"), (other, C["stopped"], "Other"),
                             (waiting, C["remaining"], "Not started")], detail_total)
           + "</div>")
    counts = df["Status"].value_counts().sort_values()
    fig = go.Figure(go.Bar(
        x=counts.values, y=counts.index, orientation="h",
        marker=dict(color=[FAMILY_COLORS[_family(s)] for s in counts.index], cornerradius=4),
        text=[f"{v:,}" for v in counts.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:,}<extra></extra>"))
    ui.style_fig(fig, max(200, 46 * len(counts) + 60), "Storms by status")
    fig.update_xaxes(showticklabels=False, showline=False)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, config=ui.PLOT_CONFIG, use_container_width=True)

with tab_quality:
    ok_df = df[df.Result == "Complete"]
    q1, q2, q3 = st.columns(3)
    for col_, label, name, unit in [(q1, "Max WSEL Err", "Median max WSE error", "ft"),
                                    (q2, "Vol Error (%)", "Median volume error", "%"),
                                    (q3, "Vol Error (AF)", "Median volume error", "AF")]:
        if label in ok_df.columns and ok_df[label].notna().any():
            col_.metric(name,
                        f"{ok_df[label].median():,.3g} {unit}",
                        help=f"95th percentile {ok_df[label].quantile(.95):,.3g} {unit}, completed storms only")
    dots(df, "Max WSEL Err", "Max water-surface error per storm", [0, 20], "Max WSE error (ft)")
    dots(df, "Vol Error (%)", "Volume error per storm", [0, 2], "Volume error (%)")
    dots(df, "Vol Error (AF)", "Volume error per storm, acre-feet", [0, 100000], "Volume error (AF)")

with tab_outputs:
    metrics_with_units = {
        "Max Depth (ft)": "Maximum flood depth (ft)",
        "Max Volume (ft^3)": "Maximum volume (ft³)",
        "Max Flow Balance (ft^3/s)": "Maximum flow balance (ft³/s)",
        "Max Stage BC (ft)": "Maximum downstream boundary stage (ft)",
        "Max Inflow BC (cfs)": "Maximum inflow boundary (cfs)",
        "Max Cum PRCP (in)": "Maximum cumulative precipitation (in)",
    }
    available = [c for c in metrics_with_units if c in df.columns]
    if available:
        metric = st.selectbox("Output", available, format_func=metrics_with_units.get)
        vals = pd.to_numeric(df[metric], errors="coerce")
        p95 = vals.quantile(0.95)
        band = df.assign(**{metric: vals, "Band": ["Above 95th percentile" if v > p95 else "Within"
                                                   for v in vals]})
        ylim = {"Max Cum PRCP (in)": [0, 100], "Max Stage BC (ft)": [0, 15]}.get(
            metric, [0, p95 * 1.5] if pd.notna(p95) and p95 > 0 else None)

        def _p95_line(fig):
            fig.add_hline(y=p95, line=dict(color=ui.INK_3, width=1.5, dash="dot"),
                          annotation_text=f"95th percentile {p95:,.3g}", annotation_position="top left",
                          annotation_font=dict(size=12, color=ui.INK_2))

        dots(band, metric, metrics_with_units[metric], ylim, metrics_with_units[metric], color_by="Band",
             colors={"Within": ui.SERIES[0], "Above 95th percentile": ui.SERIES[1]}, extra=_p95_line)
    else:
        st.info("No model-output summary for this selection yet.")

with tab_compute:
    su = df[(df.Result == "Complete") & df["SUs"].notna()] if "SUs" in df.columns else df.iloc[0:0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total SUs used", f"{su['SUs'].sum():,.0f}" if len(su) else "0")
    c2.metric("Median SUs per storm", f"{su['SUs'].median():,.1f}" if len(su) else "-")
    c3.metric("Storms counted", f"{len(su):,}", help="AWS runs report 0 SUs (billed in dollars, not SUs)")
    if len(su):
        dots(su.assign(Result="Complete"), "SUs", "Service units per completed storm", None, "SUs")

with tab_corr:
    cols = [c for c in ["Vol Error (%)", "Vol Error (AF)", "Max Depth (ft)", "Max Volume (ft^3)",
                        "Max Flow Balance (ft^3/s)", "Max Stage BC (ft)", "Max Inflow BC (cfs)",
                        "Max Cum PRCP (in)"] if c in df.columns]
    ok_df = df[df.Result == "Complete"][cols].apply(pd.to_numeric, errors="coerce")
    if len(ok_df) > 2 and len(cols) > 1:
        corr = ok_df.corr()
        fig = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.columns, zmin=-1, zmax=1, zmid=0,
            colorscale=[[0, "#2a78d6"], [0.5, "#f0efec"], [1, "#e34948"]],
            text=[[f"{v:.2f}" for v in row] for row in corr.values], texttemplate="%{text}",
            textfont=dict(size=12), xgap=2, ygap=2,
            hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
            colorbar=dict(thickness=10, outlinewidth=0, tickvals=[-1, 0, 1])))
        ui.style_fig(fig, 520, "Correlation between outputs, completed storms")
        fig.update_xaxes(tickangle=-35, showline=False)
        fig.update_yaxes(showgrid=False, autorange="reversed")
        st.plotly_chart(fig, config=ui.PLOT_CONFIG, use_container_width=True)
    else:
        st.info("Not enough completed storms for a correlation yet.")

with tab_table:
    table = df.drop(columns=[c for c in ["Max Cum PRCP (inc)", "Result", "Storm Number"] if c in df.columns]).rename(
        columns={"Duration": "CPU Runtime (hrs)", "Max WSEL Err": "WSEL Error Max (ft)",
                 "Start Time": "CPU Start Time", "End Time": "CPU End Time"})
    q = st.text_input("Search storms", placeholder="e.g. Northeast_L-H-H_c0097")
    if q:
        table = table[table["Directory"].astype(str).str.contains(q, case=False, regex=False)]
    st.dataframe(table, hide_index=True, use_container_width=True, height=560)
    st.caption(f"{len(table):,} storms")
