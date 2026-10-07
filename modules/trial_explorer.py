"""
ClinicalTrial OS - Trial Explorer
Search trials and view full details (design, eligibility, outcomes, sites).
"""
import sqlite3
import json
import pandas as pd

DB_PATH = "database/trials.db"


def _query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


def get_options():
    df = _query("SELECT disease, status, phase FROM trials")
    diseases = sorted({p.strip() for d in df["disease"] for p in str(d).split(";") if p.strip()})
    return diseases, sorted(df["status"].dropna().unique()), sorted(df["phase"].dropna().unique())


def search_trials(text="", disease="All", status="All", phase="All", limit=500):
    sql = """SELECT nct_id, title, status, phase, sponsor, enrollment,
                    num_sites, num_countries, start_date
             FROM trials WHERE 1=1"""
    params = []
    if text.strip():
        like = f"%{text.strip()}%"
        sql += """ AND (nct_id LIKE ? OR title LIKE ? OR conditions LIKE ?
                   OR interventions LIKE ? OR sponsor LIKE ? OR keywords LIKE ?)"""
        params += [like] * 6
    if disease != "All":
        sql += " AND disease LIKE ?"
        params.append(f"%{disease}%")
    if status != "All":
        sql += " AND status = ?"
        params.append(status)
    if phase != "All":
        sql += " AND phase = ?"
        params.append(phase)
    total = int(_query(f"SELECT COUNT(*) AS n FROM ({sql})", params)["n"][0])
    sql += """ ORDER BY CASE status WHEN 'RECRUITING' THEN 0
                                    WHEN 'ACTIVE_NOT_RECRUITING' THEN 1
                                    WHEN 'COMPLETED' THEN 2 ELSE 3 END,
                       start_date DESC LIMIT ?"""
    params.append(limit)
    return _query(sql, params), total


def get_trial(nct_id):
    df = _query("SELECT * FROM trials WHERE nct_id = ?", (nct_id,))
    return None if df.empty else df.iloc[0].to_dict()


def get_sites(nct_id):
    return _query("""SELECT facility, city, state, country, site_status, lat, lon
                     FROM locations WHERE nct_id = ?""", (nct_id,))


def _nice(value, default="Not reported"):
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() in ("", "NA", "N/A"):
        return default
    return str(value).replace("_", " ").title() if str(value).isupper() else str(value)


def _yes_no(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Not reported"
    return "Yes" if int(value) == 1 else "No"


def render_trial_detail(t):
    import streamlit as st
    import plotly.express as px

    st.markdown(f"## {t['title']}")
    if t.get("official_title") and t["official_title"] != t["title"]:
        st.caption(t["official_title"])
    st.markdown(f"**{t['nct_id']}** · [View on ClinicalTrials.gov ↗]"
                f"(https://clinicaltrials.gov/study/{t['nct_id']})")

    c = st.columns(5)
    c[0].metric("Status", _nice(t["status"]))
    c[1].metric("Phase", _nice(t["all_phases"]))
    c[2].metric("Enrollment", f"{int(t['enrollment'] or 0):,}",
                help=f"Type: {_nice(t['enrollment_type'])}")
    c[3].metric("Sites", int(t["num_sites"] or 0))
    c[4].metric("Countries", int(t["num_countries"] or 0))

    if t.get("why_stopped"):
        st.error(f"**Why stopped:** {t['why_stopped']}")

    tabs = st.tabs(["Overview", "Design", "Eligibility", "Outcomes", "Sites", "Timeline"])

    with tabs[0]:
        st.markdown("**Brief summary**")
        st.write(t["brief_summary"] or "Not reported")
        a, b = st.columns(2)
        with a:
            st.markdown(f"**Conditions:** {_nice(t['conditions'])}")
            st.markdown(f"**Keywords:** {_nice(t['keywords'])}")
            st.markdown(f"**Interventions:** {_nice(t['interventions'])}")
            st.markdown(f"**Intervention types:** {_nice(t['intervention_types'])}")
        with b:
            st.markdown(f"**Lead sponsor:** {_nice(t['sponsor'])} ({_nice(t['sponsor_class'])})")
            st.markdown(f"**Collaborators:** {_nice(t['collaborators'], 'None listed')}")
            st.markdown(f"**Results posted:** {_yes_no(t['has_results'])}")

    with tabs[1]:
        a, b = st.columns(2)
        a.markdown(f"**Study type:** {_nice(t['study_type'])}")
        a.markdown(f"**Allocation:** {_nice(t['allocation'])}")
        a.markdown(f"**Intervention model:** {_nice(t['intervention_model'])}")
        a.markdown(f"**Masking (blinding):** {_nice(t['masking'])}")
        b.markdown(f"**Primary purpose:** {_nice(t['primary_purpose'])}")
        b.markdown(f"**Data Monitoring Committee:** {_yes_no(t['has_dmc'])}")
        b.markdown(f"**FDA-regulated drug:** {_yes_no(t['fda_regulated_drug'])}")
        b.markdown(f"**FDA-regulated device:** {_yes_no(t['fda_regulated_device'])}")

    with tabs[2]:
        a, b, c2 = st.columns(3)
        a.metric("Age range", f"{_nice(t['min_age'], 'Any')} – {_nice(t['max_age'], 'Any')}")
        b.metric("Sex", _nice(t["sex"]))
        c2.metric("Healthy volunteers", _yes_no(t["healthy_volunteers"]))
        st.caption(f"Age groups: {_nice(t['age_groups'])}")
        st.markdown("**Eligibility criteria (as registered)**")
        st.text(t["eligibility"] or "Not reported")

    with tabs[3]:
        for label, col in [("Primary outcomes", "primary_outcomes"),
                           ("Secondary outcomes", "secondary_outcomes")]:
            items = json.loads(t[col] or "[]")
            st.markdown(f"**{label} ({len(items)})**")
            if items:
                st.dataframe(pd.DataFrame(items).rename(
                    columns={"measure": "Measure", "timeFrame": "Time frame"}),
                    width="stretch", hide_index=True)
            else:
                st.caption("None reported")

    with tabs[4]:
        sites = get_sites(t["nct_id"])
        if sites.empty:
            st.info("No site locations reported for this trial.")
        else:
            geo = sites.dropna(subset=["lat", "lon"])
            if not geo.empty:
                fig = px.scatter_geo(geo, lat="lat", lon="lon", hover_name="facility",
                                     hover_data={"city": True, "country": True,
                                                 "lat": False, "lon": False},
                                     projection="natural earth")
                fig.update_traces(marker=dict(size=8, color="#0e7c86"))
                fig.update_layout(height=380, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, width="stretch")
            st.dataframe(sites.drop(columns=["lat", "lon"]), width="stretch", hide_index=True)

    with tabs[5]:
        timeline = pd.DataFrame([
            ("First posted", t["first_posted"]),
            ("Study start", t["start_date"]),
            ("Primary completion", t["primary_completion_date"]),
            ("Study completion", t["completion_date"]),
            ("Last updated", t["last_updated"]),
        ], columns=["Milestone", "Date"])
        timeline["Date"] = timeline["Date"].replace("", "Not reported")
        st.dataframe(timeline, width="stretch", hide_index=True)
        st.caption("Dates may be estimated or anticipated for ongoing trials.")


def render_trial_explorer_page():
    """Full Streamlit page. Called from app/main.py."""
    import streamlit as st

    st.title("🔍 Trial Explorer")
    st.markdown("Search trials by keyword, drug, sponsor or NCT ID, then open any trial for full details.")
    st.markdown("---")

    diseases, statuses, phases = get_options()
    text = st.text_input("Search", placeholder="e.g. semaglutide, Pfizer, NCT04846686, insulin pump")
    a, b, c = st.columns(3)
    disease = a.selectbox("Disease area", ["All"] + diseases)
    status = b.selectbox("Status", ["All"] + list(statuses))
    phase = c.selectbox("Phase", ["All"] + list(phases))

    results, total = search_trials(text, disease, status, phase)
    st.success(f"Found {total:,} trials" + (f" (showing first {len(results)})" if total > len(results) else ""))

    if results.empty:
        st.info("No trials match. Try a broader search.")
        return

    event = st.dataframe(results, width="stretch", hide_index=True,
                         on_select="rerun", selection_mode="single-row", height=320)
    rows = event.selection.rows if event and hasattr(event, "selection") else []

    st.caption("👆 Click a row to see full trial details, or pick one below.")
    default_id = results.iloc[rows[0]]["nct_id"] if rows else results.iloc[0]["nct_id"]
    ids = results["nct_id"].tolist()
    nct_id = st.selectbox("Trial", ids, index=ids.index(default_id),
                          format_func=lambda i: f"{i} — {results.set_index('nct_id').loc[i, 'title'][:90]}")

    trial = get_trial(nct_id)
    if trial:
        st.markdown("---")
        render_trial_detail(trial)