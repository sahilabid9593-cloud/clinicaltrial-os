"""
ClinicalTrial OS - Site Selection (v2)
Ranks REAL trial sites (hospitals, research centres) using the locations
table built by modules/database.py (ClinicalTrials.gov data).
"""
import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "database/trials.db"
FINISHED = ("COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED")


def get_diseases():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT disease FROM trials").fetchall()
    conn.close()
    names = set()
    for (d,) in rows:
        for part in (d or "").split(";"):
            if part.strip():
                names.add(part.strip())
    return sorted(names)


def load_sites(disease):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT l.facility, l.city, l.country, l.lat, l.lon,
               t.nct_id, t.status, t.phase, t.enrollment, t.start_date
        FROM locations l
        JOIN trials t ON t.nct_id = l.nct_id
        WHERE t.disease LIKE ? AND l.facility != ''
    """, conn, params=[f"%{disease}%"])
    conn.close()
    return df


def rank_sites(disease="diabetes", country="All", min_trials=2, top_n=25):
    df = load_sites(disease)
    if df.empty:
        return pd.DataFrame(), {}
    if country != "All":
        df = df[df["country"] == country]
        if df.empty:
            return pd.DataFrame(), {}

    df["finished"] = df["status"].isin(FINISHED)
    df["completed"] = df["status"] == "COMPLETED"
    df["recruiting"] = df["status"] == "RECRUITING"
    df["late_phase"] = df["phase"].isin(["PHASE3", "PHASE4"])

    g = df.groupby(["facility", "city", "country"]).agg(
        trials=("nct_id", "nunique"),
        completed=("completed", "sum"),
        finished=("finished", "sum"),
        recruiting_now=("recruiting", "sum"),
        phase3_4_trials=("late_phase", "sum"),
        lat=("lat", "mean"),
        lon=("lon", "mean"),
        latest_start=("start_date", "max"),
    ).reset_index()

    g = g[g["trials"] >= min_trials]
    if g.empty:
        return pd.DataFrame(), {}

    # Completion rate with smoothing, so a site with 1/1 trials does not get 100%
    global_rate = df.loc[df["finished"], "completed"].mean() if df["finished"].any() else 0.8
    k = 3
    g["completion_rate"] = ((g["completed"] + k * global_rate) / (g["finished"] + k) * 100).round(1)

    # Score (0-100): experience 50%, reliability 35%, currently active 15%
    exp = np.log1p(g["trials"]) / np.log1p(g["trials"].max())
    rel = g["completion_rate"] / 100
    act = (g["recruiting_now"] > 0).astype(float)
    g["site_score"] = ((0.50 * exp + 0.35 * rel + 0.15 * act) * 100).round(1)

    g = g.sort_values(["site_score", "trials"], ascending=False).head(top_n)
    g.insert(0, "rank", range(1, len(g) + 1))

    summary = {
        "sites_found": int(df["facility"].nunique()),
        "countries": int(df["country"].nunique()),
        "trials": int(df["nct_id"].nunique()),
        "global_completion_rate": round(global_rate * 100, 1),
    }
    return g, summary


def country_summary(disease):
    df = load_sites(disease)
    return (df.groupby("country")
              .agg(sites=("facility", "nunique"), trials=("nct_id", "nunique"))
              .sort_values("trials", ascending=False)
              .reset_index())


def render_site_selection_page():
    """Full Streamlit page. Called from app/main.py."""
    import streamlit as st
    import plotly.express as px

    st.title("📍 Site Selection")
    st.markdown("Find experienced trial sites (hospitals and research centres) "
                "based on real ClinicalTrials.gov site data.")
    st.markdown("---")

    diseases = get_diseases()
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        disease = st.selectbox("Disease area", diseases,
                               index=diseases.index("diabetes") if "diabetes" in diseases else 0)
    countries = ["All"] + country_summary(disease)["country"].tolist()
    with c2:
        country = st.selectbox("Country", countries)
    with c3:
        min_trials = st.number_input("Min. trials at site", 1, 20, 2)

    sites, summary = rank_sites(disease, country, min_trials)

    if sites.empty:
        st.warning("No sites match these filters. Try 'Min. trials' = 1 or another country.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sites found", f"{summary['sites_found']:,}")
    m2.metric("Countries", summary["countries"])
    m3.metric("Trials analysed", f"{summary['trials']:,}")
    m4.metric("Avg completion rate", f"{summary['global_completion_rate']}%")

    st.markdown(f"### Top {len(sites)} sites for {disease}")
    map_df = sites.dropna(subset=["lat", "lon"])
    if not map_df.empty:
        fig = px.scatter_geo(map_df, lat="lat", lon="lon", size="trials",
                             color="site_score", hover_name="facility",
                             hover_data={"city": True, "country": True, "trials": True,
                                         "completion_rate": True, "lat": False, "lon": False},
                             color_continuous_scale="Teal", projection="natural earth")
        fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, width="stretch")

    st.dataframe(
        sites[["rank", "facility", "city", "country", "site_score", "trials",
               "completed", "completion_rate", "recruiting_now", "phase3_4_trials"]],
        width="stretch", hide_index=True,
        column_config={
            "site_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
            "completion_rate": st.column_config.NumberColumn("Completion %", format="%.1f%%"),
            "recruiting_now": "Recruiting now",
            "phase3_4_trials": "Phase 3/4 trials",
        })

    if country == "All":
        st.markdown("### Countries with most trial activity")
        cs = country_summary(disease).head(15)
        fig2 = px.bar(cs, x="trials", y="country", orientation="h",
                      color="sites", color_continuous_scale="Teal")
        fig2.update_layout(yaxis={"categoryorder": "total ascending"}, height=450)
        st.plotly_chart(fig2, width="stretch")

    with st.expander("ℹ️ How the score is calculated"):
        st.markdown("""
- **Experience (50%)**: number of trials the site has run in this disease area (log-scaled).
- **Reliability (35%)**: share of the site's finished trials that *completed* rather than
  terminated or withdrawn. Smoothed toward the average so sites with very few trials
  don't get extreme scores.
- **Active now (15%)**: whether the site is currently recruiting for a trial.

**Limitations:** based on registry data only (no site-level enrollment or quality data),
and limited to trials in this database. Use as a starting point for feasibility, not a final decision.
""")