"""Read the dashboard CSVs and merge every HPC's copy at page load.

Each HPC pushes its own CSVs: AWS clusters to assets/<site>/, Stampede3 to assets/ (its merge of the
sites as they were at that moment). Merging here, on every load, means the page never depends on
which HPC pushed last:
  1. within one platform, the freshest source wins (site folders are newer than Stampede3's copy);
  2. across platforms, the furthest-along status wins (a real result beats another HPC's placeholder).
"""
import re

import pandas as pd
import streamlit as st

ROOT_DIR = r"https://raw.githubusercontent.com/akhalid-twi/LWI-production/refs/heads/main/assets"
# later = fresher: the archive holds frozen rows, the live site folders override it
SITES = ["aws2_archive", "aws", "aws2", "stampede3"]
# a site folder is trusted only for its own platform's storms (plus not-started placeholders), so a stale
# copy of another HPC's rows in it can never override that HPC's fresher data
SITE_PLATFORM = {"aws2_archive": "AWS2", "aws": "AWS", "aws2": "AWS2", "stampede3": "Stampede3"}

PROGRESS_RANK = {"COMPLETE": 6, "POST-PROC": 5, "RUNNING": 4, "PRE-PROC": 3, "FAILED": 2, "STOPPED": 2,
                 "QUEUED": 1}


def basic_rank(status):
    s = str(status).strip().upper()
    if s == "SUCCESS":
        return 6
    if s == "RUNNING":
        return 4
    if "FAIL" in s:
        return 2
    if s == "NOT STARTED":
        return 0
    return 1


@st.cache_data(ttl=60, show_spinner=False)   # re-read from GitHub at most every 60 s
def _read(url):
    try:
        return pd.read_csv(url)
    except Exception:            # a site that has not pushed this file yet
        return None


def _system(platform):
    """Platform label -> platform key: one key per AWS cluster, one per Stampede3 account."""
    p = str(platform)
    if p in ("", "-", "nan", "None"):
        return "-"
    if p.startswith("AWS2"):
        return "AWS2"
    if p.startswith("AWS"):
        return "AWS"
    m = re.match(r"Stampede3 \((.+)\)", p)
    return f"Stampede3:{m.group(1)}" if m else p


def sources(name):
    """[(order, frame)] for the main copy and every site copy of one CSV."""
    out = []
    for i, site in enumerate([None] + SITES):
        d = _read(f"{ROOT_DIR}/{site + '/' if site else ''}{name}")
        if d is None or not len(d):
            continue
        if site and "Platform" in d.columns:
            sys_ = d["Platform"].map(_system)
            plat = SITE_PLATFORM[site]           # exact: "AWS" must not also match "AWS2"
            d = d[(sys_ == "-") | (sys_ == plat) | sys_.str.startswith(plat + ":")]
        out.append((i, d))
    return out


def merged(name, key, rank):
    """One row per storm (`key`), merged from every source by the two rules in the module doc."""
    frames = [d.assign(_src=i) for i, d in sources(name)]
    if not frames:
        raise FileNotFoundError(name)
    df = pd.concat(frames, ignore_index=True)
    df["_sys"] = df["Platform"].map(_system) if "Platform" in df.columns else "-"
    df = df.sort_values("_src", kind="stable").drop_duplicates([key, "_sys"], keep="last")
    df["_rank"] = df["Status"].map(rank).fillna(0) if isinstance(rank, dict) else df["Status"].map(rank)
    df = df.sort_values(["_rank", "_src"], kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns=["_src", "_sys", "_rank"]).sort_values(key).reset_index(drop=True)


def progress(scenario):
    return merged(f"{scenario}_simulation_progress.csv", "Directory", PROGRESS_RANK)


def basic(scenario):
    return merged(f"{scenario}_simulation_basic_summary.csv", "Directory", basic_rank)


def hdf(scenario):
    """HDF summary: values do not change once a storm is done, so the freshest copy per storm wins."""
    frames = [d.assign(_src=i) for i, d in sources(f"{scenario}_simulation_HDF_summary.csv")]
    if not frames:
        raise FileNotFoundError(scenario)
    df = pd.concat(frames, ignore_index=True)
    return (df.sort_values("_src", kind="stable").drop_duplicates("folder", keep="last")
            .drop(columns="_src").set_index("folder"))


@st.cache_data(ttl=300, show_spinner=False)
def push_times():
    """Last dashboard push per HPC, from the repo's recent commits (one GitHub API call, cached 5 min).
    Commit messages end in '(aws)' / '(aws2)' for the AWS clusters; Stampede3's have no suffix."""
    import requests
    from datetime import datetime
    out = {}
    try:
        r = requests.get("https://api.github.com/repos/akhalid-twi/LWI-production/commits",
                         params={"path": "assets", "per_page": 60}, timeout=10)
        commits = r.json() if r.status_code == 200 else []
    except Exception:
        commits = []
    for c in commits:
        msg = c["commit"]["message"].splitlines()[0]
        if not msg.startswith("updated production log"):
            continue
        m = re.search(r"\((\w+)\)\s*$", msg)
        who = {"aws": "AWS", "aws2": "AWS2"}.get(m.group(1), m.group(1)) if m else "Stampede3"
        when = datetime.fromisoformat(c["commit"]["committer"]["date"].replace("Z", "+00:00"))
        out[who] = max(out.get(who, when), when)
    return out
