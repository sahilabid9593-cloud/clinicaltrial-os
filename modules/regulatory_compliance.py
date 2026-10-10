"""
ClinicalTrial OS - Registry Quality Check (v2)
Checks how completely and transparently a trial is registered on
ClinicalTrials.gov, using real registry fields. This is a transparency
check, NOT a legal or GCP compliance audit.
"""
import sqlite3
import json
from datetime import datetime
import pandas as pd

DB_PATH = "database/trials.db"
STOPPED = ("TERMINATED", "WITHDRAWN", "SUSPENDED")
ONGOING = ("RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING")


def _date(s):
    """Parse 'YYYY-MM-DD' or 'YYYY-MM' into a datetime (or None)."""
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(str(s), fmt)
        except (ValueError, TypeError):
            pass
    return None


def _filled(v):
    return v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() not in ("", "NA", "N/A")


def _known(v):
    return v is not None and not (isinstance(v, float) and pd.isna(v))


def run_checks(t, today=None):
    """Return a list of checks: (category, check, result) where result is
    True (pass), False (fail) or None (not applicable to this trial)."""
    today = today or datetime.now()
    interventional = t.get("study_type") == "INTERVENTIONAL"
    status = t.get("status", "")
    elig = str(t.get("eligibility") or "").lower()
    prim = json.loads(t.get("primary_outcomes") or "[]")
    pcd = _date(t.get("primary_completion_date"))
    updated = _date(t.get("last_updated"))
    posted = _date(t.get("first_posted")) or datetime(1900, 1, 1)

    return [
        ("Identification", "Official scientific title provided", _filled(t.get("official_title"))),
        ("Identification", "Brief summary is informative (100+ characters)",
         len(str(t.get("brief_summary") or "")) >= 100),
        ("Identification", "Lead sponsor named", _filled(t.get("sponsor"))),

        # "NA" is the correct registry value for single-group trials, so it counts as reported
        ("Design", "Allocation reported (randomized / non-randomized)",
         bool(str(t.get("allocation") or "").strip()) if interventional else None),
        ("Design", "Masking (blinding) reported", _filled(t.get("masking")) if interventional else None),
        ("Design", "Primary purpose reported", _filled(t.get("primary_purpose")) if interventional else None),
        ("Design", "Intervention(s) described", _filled(t.get("interventions")) if interventional else None),
        ("Design", "Enrollment number reported",
         int(t.get("enrollment") or 0) > 0 if status != "WITHDRAWN" else None),

        ("Outcomes", "At least one primary outcome", len(prim) > 0),
        ("Outcomes", "Primary outcome(s) have a time frame",
         all(_filled(o.get("timeFrame")) for o in prim) if prim else False),
        ("Outcomes", "Secondary outcome(s) reported", int(t.get("num_secondary_outcomes") or 0) > 0),

        ("Eligibility", "Inclusion criteria listed", "inclusion" in elig),
        ("Eligibility", "Exclusion criteria listed", "exclusion" in elig),
        ("Eligibility", "Age limits stated", _filled(t.get("min_age")) or _filled(t.get("max_age"))),
        ("Eligibility", "Sex eligibility stated", _filled(t.get("sex"))),

        ("Oversight", "Data Monitoring Committee status reported",
         _known(t.get("has_dmc")) if interventional else None),
        # This field became mandatory with the FDAAA Final Rule (Jan 2017)
        ("Oversight", "FDA-regulated product status reported",
         _known(t.get("fda_regulated_drug")) if posted >= datetime(2017, 1, 18) else None),

        ("Timeline", "Start date reported", _filled(t.get("start_date"))),
        ("Timeline", "Primary completion date reported", _filled(t.get("primary_completion_date"))),
        ("Timeline", "Record updated in the last 12 months (ongoing trials)",
         (updated is not None and (today - updated).days <= 365) if status in ONGOING else None),
        ("Timeline", "Reason given for stopping early",
         _filled(t.get("why_stopped")) if status in STOPPED else None),
        ("Sites", "At least one site location listed",
         int(t.get("num_sites") or 0) > 0 if status != "WITHDRAWN" else None),

        # FDAAA 801 generally expects results ~1 year after primary completion for applicable trials
        ("Results", "Results posted (FDA-regulated, completed > 1 year ago)",
         bool(t.get("has_results")) if (status == "COMPLETED" and interventional
                                         and t.get("fda_regulated_drug") == 1
                                         and pcd and (today - pcd).days > 365) else None),
    ]


def score_trial(t):
    checks = run_checks(t)
    applicable = [c for c in checks if c[2] is not None]
    passed = sum(1 for c in applicable if c[2])
    score = round(100 * passed / len(applicable), 1) if applicable else 0
    if score >= 90:
        grade = "Excellent"
    elif score >= 75:
        grade = "Good"
    elif score >= 50:
        grade = "Needs improvement"
    else:
        grade = "Poor"
    return score, grade, checks


def check_compliance(nct_id):
    """Kept for backward compatibility with older code."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trials WHERE nct_id = ?", conn, params=[nct_id])
    conn.close()
    if df.empty:
        return None
    score, grade, checks = score_trial(df.iloc[0].to_dict())
    return {"compliance_score": score, "status": grade,
            "passed": [c[1] for c in checks if c[2] is True],
            "failed": [c[1] for c in checks if c[2] is False]}


def portfolio_scores():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trials", conn)
    conn.close()
    rows, gaps = [], {}
    for t in df.to_dict("records"):
        score, grade, checks = score_trial(t)
        rows.append({"nct_id": t["nct_id"], "title": t["title"], "status": t["status"],
                     "sponsor": t["sponsor"], "sponsor_class": t["sponsor_class"],
                     "disease": t["disease"], "score": score, "grade": grade})
        for cat, name, res in checks:
            if res is not None:
                g = gaps.setdefault(name, [0, 0])
                g[1] += 1
                if res is False:
                    g[0] += 1
    gaps_df = pd.DataFrame([{"check": k, "failing_trials": v[0],
                             "failing_pct": round(100 * v[0] / v[1], 1)}
                            for k, v in gaps.items()]).sort_values("failing_pct", ascending=False)
    return pd.DataFrame(rows), gaps_df


def render_compliance_page():
    import streamlit as st
    import plotly.express as px

    @st.cache_data(show_spinner="Scoring all trials...")
    def _portfolio():
        return portfolio_scores()

    st.title("✅ Registry Quality Check")
    st.markdown("How completely and transparently is a trial registered? "
                "Checks 23 items across design, outcomes, eligibility, oversight, timeline and results.")
    st.info("This is a **registry transparency check** based on public ClinicalTrials.gov data. "
            "It is not a legal, regulatory or ICH-GCP compliance audit.")

    tab1, tab2 = st.tabs(["Check a trial", "Database overview"])

    with tab1:
        nct_id = st.text_input("Enter NCT ID", "NCT06589765").strip().upper()
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM trials WHERE nct_id = ?", conn, params=[nct_id])
        conn.close()
        if df.empty:
            st.warning("Trial not found in the database. Use Search Trials to find NCT IDs.")
        else:
            t = df.iloc[0].to_dict()
            score, grade, checks = score_trial(t)
            st.markdown(f"#### {t['title']}")
            st.markdown(f"[View on ClinicalTrials.gov ↗](https://clinicaltrials.gov/study/{nct_id})")
            applicable = [c for c in checks if c[2] is not None]
            c1, c2, c3 = st.columns(3)
            c1.metric("Quality score", f"{score:.0f}%")
            c2.metric("Rating", grade)
            c3.metric("Checks passed", f"{sum(1 for c in applicable if c[2])} / {len(applicable)}")

            res = pd.DataFrame(checks, columns=["Category", "Check", "Result"])
            res["Result"] = res["Result"].map({True: "✅ Pass", False: "❌ Missing", None: "➖ Not applicable"})
            st.dataframe(res, width="stretch", hide_index=True, height=600)

    with tab2:
        scores, gaps = _portfolio()
        c1, c2, c3 = st.columns(3)
        c1.metric("Trials scored", f"{len(scores):,}")
        c2.metric("Average score", f"{scores['score'].mean():.1f}%")
        c3.metric("Rated Excellent", f"{(scores['grade'] == 'Excellent').mean() * 100:.0f}%")

        order = ["Excellent", "Good", "Needs improvement", "Poor"]
        dist = scores["grade"].value_counts().reindex(order, fill_value=0).reset_index()
        dist.columns = ["Rating", "Trials"]
        st.plotly_chart(px.bar(dist, x="Rating", y="Trials", color="Rating",
                               title="Rating distribution"), width="stretch")

        st.markdown("#### Most common gaps")
        st.plotly_chart(px.bar(gaps.head(10), x="failing_pct", y="check", orientation="h",
                               labels={"failing_pct": "% of applicable trials missing this", "check": ""})
                        .update_layout(yaxis={"categoryorder": "total ascending"}), width="stretch")

        st.markdown("#### Average score by sponsor type")
        by_class = scores.groupby("sponsor_class")["score"].agg(["mean", "count"]).round(1)
        by_class = by_class[by_class["count"] >= 10].sort_values("mean", ascending=False).reset_index()
        by_class.columns = ["Sponsor type", "Average score", "Trials"]
        st.dataframe(by_class, width="stretch", hide_index=True)

    with st.expander("ℹ️ Method and limitations"):
        st.markdown("""
Each trial is checked against registry fields that ClinicalTrials.gov and the WHO Trial
Registration Data Set expect sponsors to report. Checks that don't apply (e.g. blinding for
observational studies, "reason for stopping" for ongoing trials, FDA-regulation fields for trials
registered before the 2017 FDAAA Final Rule) are excluded from the score.

The **results** check flags completed, FDA-regulated interventional trials whose primary completion
was over a year ago but have no results posted. Under FDAAA 801, many such trials must post results
within about one year, but not every trial is legally required to, so treat it as a flag, not a violation.
""")
