import os
import sqlite3
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.document_generator import render_report_page
from modules.knowledge_graph import build_graph, find_sponsor_trials, get_graph_stats
from modules.pharmacovigilance import render_pharmacovigilance_page
from modules.protocol_intelligence import render_protocol_page
from modules.recruitment_prediction import render_recruitment_page
from modules.regulatory_compliance import render_compliance_page
from modules.risk_prediction import render_risk_page
from modules.site_selection import render_site_selection_page
from modules.trial_explorer import render_trial_explorer_page

DB = "database/trials.db"
GITHUB = "https://github.com/sahilabid9593-cloud/clinicaltrial-os"

st.set_page_config(page_title="ClinicalTrial OS", page_icon="🧬", layout="wide")


@st.cache_data
def query(sql):
    conn = sqlite3.connect(DB)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df


@st.cache_resource(show_spinner="Building knowledge graph...")
def cached_graph():
    return build_graph()


# ── SIDEBAR ──
st.sidebar.title("🧬 ClinicalTrial OS")
st.sidebar.markdown("*Open-source intelligence for clinical research*")
st.sidebar.markdown("---")

PAGES = [
    "🏠 Home",
    "🔍 Search Trials",
    "🧠 Protocol Intelligence",
    "🕸️ Knowledge Graph",
    "📄 Generate Report",
    "📈 Recruitment Prediction",
    "📍 Site Selection",
    "📊 Analytics",
    "⚠️ Risk Prediction",
    "✅ Compliance Check",
    "💊 Pharmacovigilance",
]
page = st.sidebar.radio("Navigate", PAGES)

st.sidebar.markdown("---")
st.sidebar.caption(f"⭐ [Star on GitHub]({GITHUB}) · MIT licensed")
st.sidebar.caption("Data: ClinicalTrials.gov, FDA FAERS. For research and education only, "
                   "not medical, regulatory or legal advice.")

# ── HOME ──
if page == "🏠 Home":
    st.title("🧬 ClinicalTrial OS")
    st.subheader("Open-source intelligence platform for clinical trial planning")
    st.markdown("Search trials, benchmark timelines, find experienced sites and check registry quality, "
                "all from real public data.")
    st.markdown("---")

    m = query("SELECT key, value FROM metadata").set_index("key")["value"]
    stats = query("""SELECT COUNT(DISTINCT sponsor) AS sponsors,
                            SUM(status = 'RECRUITING') AS recruiting FROM trials""").iloc[0]
    countries = query("SELECT COUNT(DISTINCT country) AS n FROM locations WHERE country != ''")["n"][0]

    c = st.columns(5)
    c[0].metric("Trials", f"{int(m['total_trials']):,}")
    c[1].metric("Trial sites", f"{int(m['total_sites']):,}")
    c[2].metric("Countries", f"{countries}")
    c[3].metric("Sponsors", f"{int(stats['sponsors']):,}")
    c[4].metric("Recruiting now", f"{int(stats['recruiting']):,}")
    st.caption(f"Source: {m['source']} · 10 disease areas · last refreshed {m['built_at'][:10]}")

    st.markdown("### What you can do")
    a, b = st.columns(2)
    with a:
        st.markdown("""
- 🔍 **Search Trials**: search by drug, sponsor, condition or NCT ID; open full trial details
- 🧠 **Protocol Intelligence**: break down eligibility and compare its complexity with peers
- 🕸️ **Knowledge Graph**: explore sponsor → trial → disease connections
- 📄 **Generate Report**: downloadable PDF trial report
- 📈 **Recruitment Prediction**: timeline benchmarks from similar completed trials
""")
    with b:
        st.markdown("""
- 📍 **Site Selection**: rank 20,000+ real sites on a world map
- 📊 **Analytics**: trends across the trial landscape
- ⚠️ **Risk Prediction**: early-stop risk model with honest accuracy
- ✅ **Compliance Check**: 23-point registry quality check
- 💊 **Pharmacovigilance**: FDA FAERS adverse event reports
""")
    st.info("ClinicalTrial OS is for research and educational use. It is not medical, regulatory "
            "or legal advice. Always verify against the official registry record.")

# ── SEARCH TRIALS ──
elif page == "🔍 Search Trials":
    render_trial_explorer_page()

# ── PROTOCOL INTELLIGENCE ──
elif page == "🧠 Protocol Intelligence":
    render_protocol_page()

# ── KNOWLEDGE GRAPH ──
elif page == "🕸️ Knowledge Graph":
    st.title("🕸️ Knowledge Graph")
    st.markdown("Connections between sponsors, trials, diseases and phases.")
    st.markdown("---")

    G = cached_graph()
    stats = get_graph_stats(G)
    c = st.columns(4)
    c[0].metric("Trials", f"{stats['trials']:,}")
    c[1].metric("Sponsors", f"{stats['sponsors']:,}")
    c[2].metric("Disease areas", stats["diseases"])
    c[3].metric("Connections", f"{G.number_of_edges():,}")

    st.markdown("### Most active sponsors")
    top = query("""SELECT sponsor, sponsor_class, COUNT(*) AS trials,
                          SUM(status = 'RECRUITING') AS recruiting
                   FROM trials GROUP BY sponsor ORDER BY trials DESC LIMIT 15""")
    st.plotly_chart(px.bar(top, x="trials", y="sponsor", orientation="h", color="sponsor_class",
                           labels={"trials": "Trials", "sponsor": "", "sponsor_class": "Sponsor type"})
                    .update_layout(yaxis={"categoryorder": "total ascending"}, height=480),
                    width="stretch")

    st.markdown("### Find a sponsor's trials")
    sponsor = st.text_input("Sponsor name contains", "novo")
    results = find_sponsor_trials(sponsor, G) if sponsor.strip() else []
    if results:
        st.success(f"{len(results)} trials found")
        st.dataframe(pd.DataFrame(results), width="stretch", hide_index=True)
    else:
        st.warning("No trials found for this sponsor.")

# ── GENERATE REPORT ──
elif page == "📄 Generate Report":
    render_report_page()

# ── RECRUITMENT PREDICTION ──
elif page == "📈 Recruitment Prediction":
    render_recruitment_page()

# ── SITE SELECTION ──
elif page == "📍 Site Selection":
    render_site_selection_page()

# ── ANALYTICS ──
elif page == "📊 Analytics":
    st.title("📊 Trial Analytics")
    st.markdown("Visual insights across all trials in the database.")
    st.markdown("---")

    df = query("SELECT disease, status, phase, sponsor_class, start_date, study_type, has_results FROM trials")
    df["disease1"] = df["disease"].str.split(";").str[0]
    df["start_year"] = pd.to_numeric(df["start_date"].str[:4], errors="coerce")

    a, b = st.columns(2)
    with a:
        d = df.groupby(["disease1", "status"]).size().reset_index(name="trials")
        st.plotly_chart(px.bar(d, x="trials", y="disease1", color="status", orientation="h",
                               title="Trials by disease and status",
                               labels={"disease1": "", "trials": "Trials"}).update_layout(height=450),
                        width="stretch")
    with b:
        p = df["phase"].replace({"N/A": "Not applicable"}).value_counts().reset_index()
        p.columns = ["Phase", "Trials"]
        st.plotly_chart(px.pie(p, names="Phase", values="Trials", hole=0.45,
                               title="Trials by phase").update_layout(height=450), width="stretch")

    y = df[(df["start_year"] >= 2000) & (df["start_year"] <= 2026)]
    y = y.groupby(["start_year", "study_type"]).size().reset_index(name="trials")
    st.plotly_chart(px.line(y, x="start_year", y="trials", color="study_type", markers=True,
                            title="Trials started per year",
                            labels={"start_year": "Start year", "trials": "Trials", "study_type": "Type"}),
                    width="stretch")

    a, b = st.columns(2)
    with a:
        countries = query("""SELECT country, COUNT(DISTINCT nct_id) AS trials FROM locations
                             WHERE country != '' GROUP BY country ORDER BY trials DESC LIMIT 15""")
        st.plotly_chart(px.bar(countries, x="trials", y="country", orientation="h",
                               title="Top countries by number of trials",
                               labels={"country": "", "trials": "Trials"})
                        .update_layout(yaxis={"categoryorder": "total ascending"}, height=480),
                        width="stretch")
    with b:
        fin = df[df["status"].isin(["COMPLETED", "TERMINATED", "WITHDRAWN"])]
        rate = (fin.assign(stopped=fin["status"] != "COMPLETED")
                   .groupby("sponsor_class")["stopped"].agg(["mean", "count"]).reset_index())
        rate = rate[rate["count"] >= 20]
        rate["mean"] = (rate["mean"] * 100).round(1)
        st.plotly_chart(px.bar(rate.sort_values("mean"), x="mean", y="sponsor_class", orientation="h",
                               title="Early-stop rate by sponsor type (finished trials)",
                               labels={"mean": "% terminated or withdrawn", "sponsor_class": ""},
                               hover_data=["count"]).update_layout(height=480),
                        width="stretch")

# ── RISK PREDICTION ──
elif page == "⚠️ Risk Prediction":
    render_risk_page()

# ── COMPLIANCE CHECK ──
elif page == "✅ Compliance Check":
    render_compliance_page()

# ── PHARMACOVIGILANCE ──
elif page == "💊 Pharmacovigilance":
    render_pharmacovigilance_page()
