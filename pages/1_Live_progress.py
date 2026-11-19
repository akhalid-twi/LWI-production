"""Live progress: every active storm on every platform (Stampede3 users, AWS).

Data: assets/<scenario>_simulation_progress.csv, written by update_dash on each platform
(lwicheck --csv) and merged on Stampede3, pushed to this repo about once an hour.
"""
import pandas as pd
import streamlit as st

ROOT_DIR = r"https://raw.githubusercontent.com/akhalid-twi/LWI-production/refs/heads/main/assets"
SCENARIOS = {"nontc_synthetic_base": "Synthetic Non-TC - BASE - NO SLR"}
ACTIVE = ["RUNNING", "PRE-PROC", "POST-PROC", "STOPPED", "FAILED"]

st.set_page_config(page_title="LWI Live Progress", layout="wide")
st.title("Live progress")
st.markdown("⬅️ [Back to the production summary](./)")


@st.cache_data(ttl=60)  # re-read from GitHub at most every 60 s
def load(scenario_key: str) -> pd.DataFrame:
    return pd.read_csv(f"{ROOT_DIR}/{scenario_key}_simulation_progress.csv")


key = st.selectbox("Scenario", list(SCENARIOS), format_func=SCENARIOS.get)
try:
    prog = load(key)
except Exception:
    st.info("No live table yet: it appears after the next update_dash on Stampede3 / AWS.")
    st.stop()

upd = prog["Updated"].dropna().max() if "Updated" in prog else "?"
st.caption(f"Last update from the clusters: {upd}  ·  refreshed about every hour  ·  "
           f"press R or use the menu to reload")

# --- headline numbers ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Running", int((prog.Status == "RUNNING").sum()))
c2.metric("Pre / post-processing", int(prog.Status.isin(["PRE-PROC", "POST-PROC"]).sum()))
c3.metric("Stopped / failed", int(prog.Status.isin(["STOPPED", "FAILED"]).sum()))
eta = prog.loc[prog.Status.isin(["RUNNING", "POST-PROC"]), "Done in (h)"].max()
c4.metric("Last running storm done in", f"~{eta:.1f} h" if pd.notna(eta) else "-")

# --- per platform ---
by_plat = (prog[prog.Status.isin(ACTIVE)].groupby(["Platform", "Status"]).size()
           .unstack(fill_value=0).reindex(columns=ACTIVE, fill_value=0))
if len(by_plat):
    st.subheader("By platform")
    st.dataframe(by_plat, use_container_width=True)

# --- every active storm ---
st.subheader("Storms")
f1, f2 = st.columns(2)
status_pick = f1.multiselect("Status", ACTIVE, default=ACTIVE)
plats = sorted(prog.Platform.dropna().unique())
plat_pick = f2.multiselect("Platform", plats, default=plats)
view = prog[prog.Status.isin(status_pick) & prog.Platform.isin(plat_pick)].copy()
view["Progress"] = view["Progress"] * 100                                  # 0-1 -> percent
view["Storm"] = (view["Directory"].str.replace("syn_event_", "", regex=False)
                 .str.replace("_SM3_BF1_Base", "", regex=False))
order = {"RUNNING": 0, "POST-PROC": 1, "PRE-PROC": 2, "STOPPED": 3, "FAILED": 4}
view = view.assign(_o=view.Status.map(order)).sort_values(["_o", "Done in (h)"], na_position="last").drop(columns="_o")

def _stage(status, note):
    """Readable stage of a storm: 1 setup -> 2 HEC-RAS -> 3 post-processing."""
    note = str(note) if pd.notna(note) else ""
    if status == "PRE-PROC":
        return "1 Setup: " + note.split(" (HEC-RAS")[0]          # e.g. "Applying CRS & Sorting Forcing Files"
    if status == "RUNNING":
        return "2 HEC-RAS: " + (note.replace("at ", "simulated to ") if note.startswith("at ") else note)
    if status == "POST-PROC":
        return "3 Post-processing: extraction, QA/QC, compression"
    if status == "STOPPED":
        return "Stopped: " + note
    if status == "FAILED":
        return "Failed: " + note
    return note


view["Stage"] = [_stage(st_, n) for st_, n in zip(view["Status"], view["Note"])]
cols = ["Platform", "Row", "Storm", "Status", "Progress", "Run (h)", "Done in (h)", "Stage"]
try:
    st.dataframe(
        view[cols], hide_index=True, use_container_width=True, height=600,
        column_config={
            "Progress": st.column_config.ProgressColumn("HEC-RAS progress", min_value=0, max_value=100, format="%.0f%%"),
            "Done in (h)": st.column_config.NumberColumn("Done in (h)", format="%.1f"),
            "Run (h)": st.column_config.NumberColumn("HEC-RAS time (h)", format="%.1f",
                                                     help="running: HEC-RAS hours so far; finished: total"),
            "Row": st.column_config.NumberColumn("CSV row", format="%d"),
        })
except Exception:                                   # older Streamlit: plain table, progress as text
    plain = view[cols].copy()
    plain["Progress"] = plain["Progress"].map(lambda v: f"{v:.0f}%" if pd.notna(v) else "")
    plain["Run (h)"] = plain["Run (h)"].map(lambda v: f"{v:.1f}" if pd.notna(v) else "")
    plain["Done in (h)"] = plain["Done in (h)"].map(lambda v: f"{v:.1f}" if pd.notna(v) else "")
    st.dataframe(plain, use_container_width=True, height=600)
st.caption(f"{len(view)} storms shown. STOPPED = log idle > 2 h (killed / interrupted, needs a rerun); "
           f"FAILED = finished with missing outputs.")
