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
import requests
from collections import defaultdict


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
    "erdc_baseline_reruns": {
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
        "completion_date_projected": datetime(2026, 6, 15),
        "completion_date_actual": datetime(2026, 6, 25),        
        "total_simulations": 10000,
    },
    "synthetic_nontc_base": {
        "title": "Synthetic Non-TC - BASE - NO SLR",
        "category": "Non-Tropical Cyclones",
        "start_date": datetime(2026, 6, 15),
        "completion_date_projected": datetime(2026, 6, 30),
        "completion_date_actual": datetime(2026, 6, 30),
        "total_simulations": 10000,
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
DEFAULT_SCENARIO_KEY = "synthetic_nontc_slr4"

# Data root
ROOT_DIR = r"https://raw.githubusercontent.com/akhalid-twi/LWI-production/refs/heads/main/assets"



st.set_page_config(page_title="LWI Production Dashboard", layout="centered")

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

st.title("LWI Production Dashboard")
st.markdown("---")

# 1. Initialize global states cleanly
if "scenario_current" not in st.session_state:
    st.session_state.scenario_current = DEFAULT_SCENARIO_KEY
if "scenario_changed" not in st.session_state:
    st.session_state.scenario_changed = True

# Get the category of whatever the current scenario is
current_default_category = SCENARIOS[st.session_state.scenario_current].get("category", list(GROUPED_SCENARIOS.keys())[0])

# 2. Dynamic Category Selection
st.subheader("Scenario Configuration")

categories = list(GROUPED_SCENARIOS.keys())
selected_category = st.selectbox(
    "Select Scenario Category",
    options=categories,
    index=categories.index(current_default_category)
)

# 3. Pull scenarios strictly for the active category
scenarios_dict = GROUPED_SCENARIOS[selected_category]

# Map friendly titles to technical configuration keys
scenario_names = {key: cfg.get("title", key) for key, cfg in scenarios_dict.items()}
display_to_key = {v: k for k, v in scenario_names.items()}
display_list = list(display_to_key.keys())

# Determine the default index for the radio button
if st.session_state.scenario_current in scenarios_dict:
    current_display = scenario_names[st.session_state.scenario_current]
    default_idx = display_list.index(current_display)
else:
    default_idx = 0

# 4. A single, safe Radio widget that never conflicts with other tabs
selected_display = st.radio(
    f"Available {selected_category} Scenarios",
    options=display_list,
    index=default_idx,
    key="single_scenario_radio"
)

# 5. Process state updates cleanly downstream instead of via complex callbacks
new_selection = display_to_key[selected_display]

if st.session_state.scenario_current != new_selection:
    st.session_state.scenario_current = new_selection
    st.session_state.scenario_changed = True
    try:
        _load_df_cached.clear()
    except Exception:
        pass

# Finalize active configuration details
scenario_key = st.session_state.scenario_current
scenario_cfg = SCENARIOS[scenario_key]

st.markdown("---")
st.caption(f"Selected Scenario: **{scenario_cfg['title']}** ({scenario_cfg['category']})")

# ---------------------------------------------------------------------
# Helpers: Last updated + cached loader
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _load_df_cached(_scenario_key: str):
    # Your heavy loader (I/O, compute, merges, etc.)
    return load_merged_dataframe(_scenario_key)

def _get_last_updated_safe(_scenario_key: str):
    try:
        return get_last_updated_dt(_scenario_key)
    except Exception as e:
        st.info(f"Could not determine last updated time for '{_scenario_key}': {e}")
        return None

# ---------------------------------------------------------------------
# Main block: one spinner that covers load + processing + plot
# ---------------------------------------------------------------------
# We show spinner when:
#   - first paint (scenario_changed initialized True), or
#   - user actually changed scenario (handled by callback)
# Otherwise we render from cache quickly without spinner
force_spinner = st.session_state.scenario_changed

spinner_msg = f"Loading '{scenario_cfg.get('title', scenario_key)}' — fetching data and rendering…"
context_manager = st.spinner(spinner_msg) if force_spinner else st.empty()

with context_manager:
    # --- Last Updated ---
    modified_datetime = _get_last_updated_safe(scenario_key)
    if modified_datetime:
        st.caption(f"Last updated: {modified_datetime.strftime('%Y-%m-%d %H:%M UTC')}")
    else:
        st.caption("Last updated: Unknown (GitHub API limit or network issue)")

    # --- Data Loading (cached, no inner spinner to avoid double spinner) ---
    try:
        #df = _load_df_cached(scenario_key)
        df = load_merged_dataframe(scenario_key)
    except Exception as e:
        st.error(f"Failed to load data for scenario '{scenario_key}': {e}")
        st.stop()

    # --- Derived metrics (your processing) ---

    df_not_running = df[df.Status!='Running']
    running_on_psc = int(len(df[df.Status=='Running']))

    total_simulations = int(scenario_cfg.get("total_simulations", 10_000))

    completed_simulations = int(len(df_not_running) if df_not_running is not None else 0)
    progress_percent = min(int((completed_simulations / total_simulations) * 100), 100)

    # --- Plotting (keep your plotting inside spinner so it covers render time) ---
    # Example placeholders below; swap with your actual visualization code.

    st.markdown("---")
    st.subheader("Simulation Count")
    col1, col2, col3  = st.columns(3, gap="medium")
    with col1:
        st.metric("Completed", f"{completed_simulations:,}")
    with col2:
        st.metric("Running", f"{running_on_psc:,}")
    with col3:
        st.metric("Total", f"{total_simulations:,}")

    progress_text = f"Processing simulations... {progress_percent}% complete"
    st.progress(progress_percent, text=progress_text)

    # Example: If you have more heavy charts, render them here so spinner stays active.
    # chart = make_big_chart(df)  # your function
    # st.altair_chart(chart, use_container_width=True)

    
    # Status message
    if progress_percent < 25:
        st.info("🚧 Just getting started...")
    elif progress_percent < 75:
        st.warning("🔄 In progress...")
    elif progress_percent < 99.5:
        st.warning("🔄 Almost there...")
    else:
        st.success("✅ Completed!")
    
    # Timeline (scenario-specific)
    start_date = scenario_cfg["start_date"]
    completion_date_prj = scenario_cfg["completion_date_projected"]
    completion_date_act = scenario_cfg["completion_date_actual"]
    now = datetime.now()
    
    st.subheader("Timeline")
    st.write(f"Production Started: {start_date.strftime('%d %b %Y')}")
    st.write(f"Production Completion (projected): {completion_date_prj.strftime('%d %b %Y')}")
    st.write(f"Production Completion (actual): {completion_date_act.strftime('%d %b %Y')}")   
    
    # Optional: remaining time
    remaining_time = completion_date_act - now
    
    
    # Countdown timer
    days = remaining_time.days
    hours, remainder = divmod(remaining_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Check if we are past the completion date
    
    # Check timeline status
    remaining_seconds = remaining_time.total_seconds()
    
    if remaining_seconds >= 0:
        # Countdown still active
        st.info(f"Time Remaining: {days} days, {hours} hrs, {minutes} min")
    
    elif remaining_seconds < 0 and progress_percent < 99.5:
        # Project overdue but not yet technically complete
        st.error(f"Project overdue: {days} days, {hours} hrs, {minutes} min")
    
    elif remaining_seconds < 0 and progress_percent >= 99.5:
        # Completed beyond target date
        st.info(f"Completed {abs(days)} days ago")



# For debugging/visibility
#st.subheader(f"Selected scenario key: **{scenario_key}**")


# =============================================================================
# Status Count
# =============================================================================

# Filter simulations by status
success_df = df[df["Status"] == "SUCCESS"].copy()
failed_df = df[df["Status"].str.contains("Failed", case=False, na=False)]
running_df = df[df["Status"] == "Running"].copy()


# Simulated counts
completed_count = len(success_df) + len(failed_df)
running_count = len(running_df)
failed_count = len(failed_df)
successful_count = len(success_df)


waiting_count = total_simulations - (completed_count + running_count)
waiting_count = max(0, waiting_count)


#------------------------------
# Horizontal stacked bar: Completed vs Running
#------------------------------
st.subheader("Completed vs Running Simulations (Stacked)")


completed_count = len(success_df) + len(failed_df)
running_count = len(running_df)
waiting_count = total_simulations - (completed_count + running_count)
waiting_count = max(waiting_count, 0)  # avoid negative

fig_completion = go.Figure()

fig_completion.add_trace(go.Bar(
    y=["Simulations"],
    x=[completed_count],
    name="Completed",
    orientation='h',
    marker=dict(color='lightgreen')
))

fig_completion.add_trace(go.Bar(
    y=["Simulations"],
    x=[running_count],
    name="Running",
    orientation='h',
    marker=dict(color='skyblue')
))

fig_completion.add_trace(go.Bar(
    y=["Simulations"],
    x=[waiting_count],
    name="Waiting",
    orientation='h',
    marker=dict(color='lightgray')
))

fig_completion.update_layout(
    barmode='stack',
    xaxis_title="Count",
    xaxis=dict(range=[0, total_simulations]),
    height=225
)

st.plotly_chart(fig_completion)


#------------------------------
# Vertical Bar chart of status categories
#------------------------------
st.subheader("Simulation Status Distribution")

# Get value counts
status_counts = df["Status"].value_counts().reset_index()
status_counts.columns = ["Status", "Count"]

# Define custom colors for each status
color_map = {
    "SUCCESS": "#90EE90",
    "Running": "skyblue",
    "UNSTABLE-FAILED": "#FF7F7F",
    "SLURM_TIMEOUT-FAILED": "#FFD700",
    "DISK-FAILED": "#FFD700",
    "HDF-FAILED": "#FFD700"
}

status_counts["Color"] = status_counts["Status"].map(color_map).fillna("orange")

# Create Plotly bar chart
fig_status = go.Figure()

for _, row in status_counts.iterrows():
    fig_status.add_trace(go.Bar(
        x=[row["Status"]],
        y=[row["Count"]],
        name=row["Status"],
        marker_color=row["Color"],
        text=row["Count"],
        textposition="outside"
    ))

fig_status.update_layout(
    title="Status Type Counts",
    xaxis_title="Status",
    yaxis_title="Count",
    showlegend=False,
    height=500,
    yaxis=dict(range=[0, 10000])  # Set y-axis range
)

st.plotly_chart(fig_status)

#------------------------------
# Pie chart of success vs failure
#------------------------------
status_counts = df["Status"].value_counts().reset_index()
status_counts.columns = ["Status", "Count"]

color_map = {
    "SUCCESS": "#90EE90",        # Light Green (Success)
    "Running": "skyblue",        # Light Blue (In Progress)
    "UNSTABLE-FAILED": "#FF7F7F",# Soft Red (Unstable Failure)
    "SLURM_TIMEOUT-FAILED": "#FFA500", # Orange (Timeout)
    "DISK-FAILED": "#FFD700",    # Gold (Disk Issue)
    "HDF-FAILED": "#FFD700",     # Gold (HDF Issue)
    "FAILED": "#FF6347"          #
}

fig_pie = px.pie(
    status_counts,
    names="Status",
    values="Count",
    title="Failure vs Success Distribution",
    color="Status",
    color_discrete_map=color_map
)
#st.subheader("Simulation Status Distribution")
st.plotly_chart(fig_pie)


# =============================================================================
#  SU usage
# =============================================================================

# Convert SUs to numeric
success_df["SUs"] = pd.to_numeric(success_df["SUs"], errors='coerce')
total_sus = success_df["SUs"].sum()

# Create numeric storm numbering
success_df = success_df.reset_index(drop=True)
success_df["Storm Number"] = success_df.index + 1

# SU usage plot
st.subheader("Service Units (SUs) Used per Successful Simulation")
st.markdown(f"**Total SUs Used:** {total_sus:,}")

fig_su = px.bar(
    success_df,
    x="Storm Number",
    y="SUs",
    color="SUs",
    title="SUs per Successful Run",
    hover_data={
        "Directory": True,
        "Storm Number": False
    }
)

fig_su.update_traces(
    hovertemplate=
    "<b>Storm:</b> %{customdata[0]}<br>" +
    "<b>SUs:</b> %{y:,.0f}<extra></extra>"
)

fig_su.update_layout(
    xaxis_title="Storm Number"
)

st.plotly_chart(fig_su, config={"responsive": True})

# =============================================================================
# Error plots for key metrics
# =============================================================================

st.subheader("Error plots for key metrics")

# Convert columns to numeric
df["Vol Error (AF)"] = pd.to_numeric(df["Vol Error (AF)"], errors='coerce')
df["Vol Error (%)"] = pd.to_numeric(df["Vol Error (%)"], errors='coerce')
df["Max WSEL Err"] = pd.to_numeric(df["Max WSEL Err"], errors='coerce')


def categorize_by_status(status):
    status = str(status).strip().lower()

    if status == "success":
        return "Success"         # green
    elif status == "running":
        return "Running"         # cyan
    elif "failed" in status:
        return "Failed"          # red
    else:
        return "Other"           # orange

# Apply to each metric
df["Color Category WSEL"]  = df["Status"].apply(categorize_by_status)
df["Color Category VolAF"] = df["Status"].apply(categorize_by_status)
df["Color Category VolPct"] = df["Status"].apply(categorize_by_status)

# Color map (simple)
color_map = {
    "Success": "green",
    "Running": "cyan",
    "Failed": "red",
    "Other": "orange"
}


df_sorted = df.sort_values(by='Directory')

# Create numeric index for x-axis labels
df_sorted = df_sorted.reset_index(drop=True)
df_sorted["Storm Number"] = df_sorted.index + 1



#------------------------------
# Plot for Max WSEL Err
#------------------------------

fig_max_wsel_er = px.bar(
    df_sorted,
    x="Storm Number", #    x="Directory",
    y="Max WSEL Err",
    title="Max WSEL Error",
    color="Color Category WSEL",
    color_discrete_map=color_map,
    hover_data={
        "Directory": True,          # show full storm/scenario name on hover
        "Storm Number": False        # don't repeat index in hover
    }
)
fig_max_wsel_er.update_yaxes(range=[0, 20])

st.plotly_chart(fig_max_wsel_er, config={"responsive": True})


#------------------------------
# Plot for Vol Error (AF)
#------------------------------

fig_vol_af = px.bar(
    df_sorted,
    x="Storm Number", #    x="Directory",
    y="Vol Error (AF)",
    title="Volume Error (AF)",
    color="Color Category VolAF",
    color_discrete_map=color_map,
    hover_data={
        "Directory": True,          # show full storm/scenario name on hover
        "Storm Number": False        # don't repeat index in hover
    }

)
fig_vol_af.update_yaxes(range=[0, 100000])
st.plotly_chart(fig_vol_af, config={"responsive": True})


#------------------------------
# Plot for Vol Error (%)
#------------------------------

fig_vol_pct = px.bar(
    df_sorted,
    x="Storm Number", #    x="Directory",
    y="Vol Error (%)",
    title="Volume Error (%)",
    color="Color Category VolPct",
    color_discrete_map=color_map,
    hover_data={
        "Directory": True,          # show full storm/scenario name on hover
        "Storm Number": False        # don't repeat index in hover
    }

)
fig_vol_pct.update_yaxes(range=[0, 2])
st.plotly_chart(fig_vol_pct, config={"responsive": True})



# =============================================================================
# Status Table
# =============================================================================
for cols in ['Color Category WSEL', 'Color Category VolAF','Color Category VolPct', 'Max Cum PRCP (inc)']:
    if cols in df.columns:
        del df[cols]

df = df.rename(columns={
    'Duration': 'CPU Runtime (hrs)',
    'Max WSEL Err': 'WSEL Error Max (ft)',
    'Start Time': 'CPU Start Time',
    'End Time': 'CPU End Time'
})


# Status table
styled_df = df.style.apply(highlight_status, axis=1)

st.subheader("Status Table")
st.dataframe(styled_df)


#------------------------------
# Hydrodynamic and forcing plots
#------------------------------
st.subheader("Hydrodynamic Model Outputs and Forcings")

# Convert relevant columns to numeric
for col in df.columns:
    if col not in ['Directory','Status','Failure Reason','Start Time','End Time']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# Plot each metric with units in y-axis label
metrics_with_units = {
#    "Max WSE (ft)": "Maximum Water Surface Elevation (ft)",
    "Max Depth (ft)": "Maximum Flood Depth (ft)",
#    "Max Velocity": "Maximum Velocity (ft/s)",
    "Max Volume (ft^3)": "Maximum Volume (ft³)",
    "Max Flow Balance (ft^3/s)": "Maximum Flow Balance (ft³/s)",
    "Max Stage BC (ft)": "Maximum Downstream Boundary Condition (ft)",
    "Max Inflow BC (cfs)": "Maximum Inflow Boundary Condition (cfs)",
    "Max Cum PRCP (in)": "Maximum Cumulative PRCP Depth (inc)",

}


# Create numeric index for plotting
df = df.reset_index(drop=True)
df["Storm Number"] = df.index + 1

for col, title in metrics_with_units.items():

    if col in df.columns:

        mean_val = round(df[col].quantile(0.95), 2)

        colors = [
            'purple' if val > mean_val else 'steelblue'
            for val in df[col]
        ]

        fig = go.Figure()

        # Main bars
        fig.add_trace(go.Bar(
            x=df["Storm Number"],
            y=df[col],
            marker_color=colors,
            name=col,
            customdata=df[["Directory"]],
            hovertemplate=
                "<b>Storm:</b> %{customdata[0]}<br>" +
                f"<b>{title}:</b> %{{y}}<extra></extra>"
        ))

        # 95% threshold line
        fig.add_trace(go.Scatter(
            x=df["Storm Number"],
            y=[mean_val] * len(df),
            mode='lines',
            line=dict(color='black', dash='dash'),
            name='95%'
        ))

        # Dummy traces for legend
        fig.add_trace(go.Bar(
            x=[None],
            y=[None],
            marker_color='purple',
            name='Above 95%'
        ))

        fig.add_trace(go.Bar(
            x=[None],
            y=[None],
            marker_color='steelblue',
            name='Below 95%'
        ))

        fig.update_layout(
            title=title,
            xaxis_title="Storm Number",
            yaxis_title=title,
            showlegend=True
        )

        ymax = mean_val * 1.5
        fig.update_yaxes(range=[0, ymax])

        if col == 'Max Cum PRCP (in)':
            fig.update_yaxes(range=[0, 100])

        elif col == 'Max Stage BC (ft)':
            fig.update_yaxes(range=[0, 15])

        st.plotly_chart(fig, config={"responsive": True})


#--------------------------
# correlation metrics
#--------------------------

success_df = df[df["Status"] == "SUCCESS"].copy()

success_df_clean = success_df.copy()
for cols in ['SUs','Max WSE (ft)','Failure Info','Failure Reason']:
    if cols in success_df_clean.columns:
        del success_df_clean[cols]

st.subheader("Correlation Metrics")
#print(success_df_clean.columns)


# rearrange columns
success_df_clean = success_df_clean[['Vol Error (%)','Vol Error (AF)','Max Depth (ft)',
                                     'Max Volume (ft^3)',
                                     'Max Flow Balance (ft^3/s)', 'Max Stage BC (ft)',
                                     'Max Inflow BC (cfs)', 'Max Cum PRCP (in)']]


corr_matrix = success_df_clean.select_dtypes(include='number').corr()
fig_corr = go.Figure(data=go.Heatmap(
     z=corr_matrix.values,
     x=corr_matrix.columns,
     y=corr_matrix.columns,
     colorscale='Viridis'
 ))
st.plotly_chart(fig_corr)

# We reached here without exception; clear the change flag so spinner doesnot reappear
st.session_state.scenario_changed = False
