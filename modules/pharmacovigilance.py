"""
ClinicalTrial OS - Pharmacovigilance (v2)
Real post-marketing adverse event reports from the FDA FAERS database (openFDA).
"""
import requests

FAERS = "https://api.fda.gov/drug/event.json"
LABELS = "https://api.fda.gov/drug/label.json"


def _find_query(drug):
    """Try generic name, then brand name, then the free-text product name."""
    d = drug.strip().lower().replace('"', "")
    for field in ("patient.drug.openfda.generic_name", "patient.drug.openfda.brand_name",
                  "patient.drug.medicinalproduct"):
        q = f'{field}:"{d}"'
        data = requests.get(FAERS, params={"search": q, "limit": 1}, timeout=15).json()
        if "results" in data:
            return q, data["meta"]["results"]["total"]
    return None, 0


def get_adverse_events(drug_name, limit=15):
    try:
        q, n_reports = _find_query(drug_name)
        if not q:
            return None
        top = requests.get(FAERS, params={"search": q, "limit": limit,
                                          "count": "patient.reaction.reactionmeddrapt.exact"},
                           timeout=15).json().get("results", [])
        serious = requests.get(FAERS, params={"search": f"{q} AND serious:1", "limit": 1},
                               timeout=15).json()
        n_serious = serious.get("meta", {}).get("results", {}).get("total", 0)
        by_year = requests.get(FAERS, params={"search": q, "count": "receivedate"},
                               timeout=15).json().get("results", [])
    except Exception as e:
        print(f"openFDA error: {e}")
        return None

    years = {}
    for r in by_year:
        y = str(r["time"])[:4]
        years[y] = years.get(y, 0) + r["count"]

    return {
        "drug": drug_name,
        "total_reports": n_reports,
        "serious_reports": n_serious,
        "top_events": [{"event": r["term"].title(), "reports": r["count"],
                        "pct_of_reports": round(100 * r["count"] / n_reports, 1)} for r in top],
        "by_year": [{"year": int(y), "reports": c} for y, c in sorted(years.items())],
        "source": "FDA FAERS via openFDA",
    }


def get_drug_label(drug_name):
    d = drug_name.strip().lower().replace('"', "")
    try:
        data = {}
        for field in ("openfda.generic_name", "openfda.brand_name"):
            data = requests.get(LABELS, params={"search": f'{field}:"{d}"', "limit": 1},
                                timeout=15).json()
            if "results" in data:
                break
        if "results" not in data:
            return None
        lab = data["results"][0]
        first = lambda k: (lab.get(k) or [""])[0]
        return {"boxed_warning": first("boxed_warning"),
                "warnings": first("warnings") or first("warnings_and_cautions"),
                "brand": ", ".join(lab.get("openfda", {}).get("brand_name", [])[:3])}
    except Exception:
        return None


def render_pharmacovigilance_page():
    import streamlit as st
    import pandas as pd
    import plotly.express as px

    st.title("💊 Pharmacovigilance")
    st.markdown("Real-world adverse event reports from the **FDA FAERS** database.")
    st.warning("FAERS reports are voluntary and unverified. A report does **not** prove the drug caused "
               "the event, and counts cannot be used to calculate how often an event happens.")
    st.markdown("---")

    drug = st.text_input("Drug name (generic or brand)", "metformin")
    if not st.button("Get Adverse Events", type="primary"):
        return

    with st.spinner("Querying openFDA..."):
        r = get_adverse_events(drug)
        label = get_drug_label(drug)
    if not r:
        st.error("No FAERS reports found (or openFDA is unreachable). Check the spelling or try the generic name.")
        return

    a, b, c = st.columns(3)
    a.metric("Total FAERS reports", f"{r['total_reports']:,}")
    b.metric("Serious reports", f"{r['serious_reports']:,}")
    c.metric("Serious share", f"{100 * r['serious_reports'] / r['total_reports']:.0f}%")

    df = pd.DataFrame(r["top_events"])
    st.plotly_chart(px.bar(df, x="reports", y="event", orientation="h", color="pct_of_reports",
                           color_continuous_scale="Reds", hover_data=["pct_of_reports"],
                           labels={"reports": "Reports", "event": "", "pct_of_reports": "% of reports"},
                           title=f"Most reported reactions: {drug.title()}")
                    .update_layout(yaxis={"categoryorder": "total ascending"}, height=480),
                    width="stretch")

    if r["by_year"]:
        st.plotly_chart(px.line(pd.DataFrame(r["by_year"]), x="year", y="reports", markers=True,
                                title="Reports received per year"), width="stretch")

    if label and (label["boxed_warning"] or label["warnings"]):
        with st.expander("📋 FDA label warnings"):
            if label["boxed_warning"]:
                st.error("**Boxed warning:** " + label["boxed_warning"][:1500])
            if label["warnings"]:
                st.write(label["warnings"][:2500])
    st.caption("Source: FDA Adverse Event Reporting System (FAERS) via openFDA.")
