import streamlit as st
import sqlite3
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.protocol_intelligence import analyze_protocol
from modules.knowledge_graph import build_graph, find_sponsor_trials, get_graph_stats
from modules.document_generator import generate_report

st.set_page_config(
    page_title="ClinicalTrial OS",
    page_icon="🧬",
    layout="wide"
)

st.sidebar.image("https://img.icons8.com/color/96/dna-helix.png", width=60)
st.sidebar.title("ClinicalTrial OS")
st.sidebar.markdown("*AI Platform for Clinical Research*")
st.sidebar.markdown("---")

page = st.sidebar.radio("Navigate", [
    "🏠 Home",
    "🔍 Search Trials",
    "🧠 Protocol Intelligence",
    "🕸️ Knowledge Graph",
    "📄 Generate Report"
])

# ─── HOME ───
if page == "🏠 Home":
    st.title("🧬 ClinicalTrial OS")
    st.subheader("AI Operating System for Clinical Trials")
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    conn = sqlite3.connect("database/trials.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trials")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT sponsor) FROM trials")
    sponsors = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM trials WHERE status='COMPLETED'")
    completed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT phase) FROM trials")
    phases = cursor.fetchone()[0]
    conn.close()

    col1.metric("Total Trials", total)
    col2.metric("Sponsors", sponsors)
    col3.metric("Completed", completed)
    col4.metric("Phases", phases)

    st.markdown("---")
    st.markdown("### What this platform does")
    st.markdown("""
    - 🔍 **Search Trials** — Search 200+ real clinical trials by disease
    - 🧠 **Protocol Intelligence** — AI analyzes trial eligibility criteria
    - 🕸️ **Knowledge Graph** — Find connections between sponsors and trials
    - 📄 **Generate Report** — Create professional PDF reports in seconds
    """)

# ─── SEARCH TRIALS ───
elif page == "🔍 Search Trials":
    st.title("🔍 Search Clinical Trials")
    st.markdown("---")

    col1, col2 = st.columns([3,1])
    with col1:
        search = st.text_input("Search by disease", "diabetes")
    with col2:
        status_filter = st.selectbox("Status", 
            ["ALL", "COMPLETED", "RECRUITING", "ACTIVE_NOT_RECRUITING"])

    if st.button("Search", type="primary"):
        conn = sqlite3.connect("database/trials.db")
        if status_filter == "ALL":
            df = pd.read_sql("""
                SELECT nct_id, title, status, phase, sponsor, enrollment
                FROM trials WHERE disease LIKE ?
            """, conn, params=[f"%{search}%"])
        else:
            df = pd.read_sql("""
                SELECT nct_id, title, status, phase, sponsor, enrollment
                FROM trials WHERE disease LIKE ? AND status=?
            """, conn, params=[f"%{search}%", status_filter])
        conn.close()

        st.success(f"Found {len(df)} trials")
        st.dataframe(df, use_container_width=True)

# ─── PROTOCOL INTELLIGENCE ───
elif page == "🧠 Protocol Intelligence":
    st.title("🧠 Protocol Intelligence")
    st.markdown("AI reads and analyzes clinical trial protocols")
    st.markdown("---")

    nct_id = st.text_input("Enter NCT ID", "NCT00035906")
    
    if st.button("Analyze Protocol", type="primary"):
        with st.spinner("AI is analyzing the protocol... please wait 30 seconds..."):
            result = analyze_protocol(nct_id)
        
        if result:
            col1, col2, col3 = st.columns(3)
            col1.metric("Recruitment Difficulty", 
                       result.get("recruitment_difficulty", "N/A"))
            col2.metric("Patient Pool", 
                       result.get("estimated_patient_pool", "N/A"))
            col3.metric("Key Risks", 
                       len(result.get("key_risks", [])))

            st.markdown("### Ideal Patient Profile")
            st.info(result.get("ideal_patient_profile", "N/A"))

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Inclusion Criteria")
                for item in result.get("inclusion_criteria", []):
                    st.markdown(f"✅ {item}")
            with col2:
                st.markdown("### Exclusion Criteria")
                for item in result.get("exclusion_criteria", []):
                    st.markdown(f"❌ {item}")

            st.markdown("### Key Risks")
            for risk in result.get("key_risks", []):
                st.warning(risk)

# ─── KNOWLEDGE GRAPH ───
elif page == "🕸️ Knowledge Graph":
    st.title("🕸️ Knowledge Graph")
    st.markdown("Connections between trials, sponsors and diseases")
    st.markdown("---")

    with st.spinner("Building knowledge graph..."):
        G = build_graph()
        stats = get_graph_stats(G)

    col1, col2, col3 = st.columns(3)
    col1.metric("Trials", stats["trials"])
    col2.metric("Sponsors", stats["sponsors"])
    col3.metric("Total Connections", stats["trials"] + stats["sponsors"])

    st.markdown("---")
    sponsor = st.text_input("Search sponsor", "novo")
    if st.button("Find Trials", type="primary"):
        results = find_sponsor_trials(sponsor, G)
        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No trials found for this sponsor")

# ─── GENERATE REPORT ───
elif page == "📄 Generate Report":
    st.title("📄 Generate Trial Report")
    st.markdown("Generate a professional PDF report for any trial")
    st.markdown("---")

    nct_id = st.text_input("Enter NCT ID", "NCT00035906")

    if st.button("Generate PDF Report", type="primary"):
        with st.spinner("AI writing report... please wait 30 seconds..."):
            generate_report(nct_id)
        st.success(f"Report saved to reports/{nct_id}_report.pdf")
        st.balloons()
        st.info("Open the reports/ folder in VS Code to see your PDF")