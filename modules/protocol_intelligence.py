"""
ClinicalTrial OS - Protocol Intelligence (v2)

Always works (no AI needed):
  - splits eligibility into inclusion / exclusion criteria
  - measures eligibility complexity and compares it with similar trials
  - flags common restrictive criteria (lab thresholds, prior therapy, pregnancy...)
Optional AI layer (Groq or local Ollama): ideal patient profile + key risks.
"""
import re
import sqlite3
import pandas as pd
from modules.llm import ask_llm_json, provider

DB_PATH = "database/trials.db"

FLAGS = {
    "Lab value thresholds": r"\b(hba1c|egfr|creatinine|alt|ast|bilirubin|hemoglobin|platelet|neutrophil|bmi)\b",
    "Prior / concomitant therapy limits": r"\b(prior|previous|concomitant|washout|treated with|treatment with)\b",
    "Pregnancy / contraception": r"\b(pregnan|breastfeed|breast-feed|lactat|contracepti)",
    "Organ function / comorbidity exclusions": r"\b(renal|hepatic|cardiac|heart failure|liver|kidney|stroke|myocardial)\b",
    "Cancer history exclusion": r"\b(malignan|cancer|neoplasm|tumou?r)\b",
    "Psychiatric / cognitive requirements": r"\b(psychiatric|depress|dementia|cognitive|mmse|suicid)",
    "Consent / language requirement": r"\b(informed consent|able to understand|speak|language)\b",
    "Recent trial participation exclusion": r"\b(investigational (drug|product|device)|another (clinical )?(trial|study))\b",
}


def _items(block):
    out = []
    for line in block.splitlines():
        line = re.sub(r"^([*\-•]|\d+[.)])\s*", "", line.strip()).strip()
        if len(line) > 3:
            out.append(line)
    return out


def split_criteria(text):
    text = text or ""
    m = re.search(r"exclusion criteria\s*:?", text, re.I)
    if m:
        inc, exc = text[:m.start()], text[m.end():]
    else:
        inc, exc = text, ""
    inc = re.sub(r"inclusion criteria\s*:?", "", inc, flags=re.I)
    return _items(inc), _items(exc)


def _count(text):
    inc, exc = split_criteria(text)
    return len(inc) + len(exc)


def analyze_protocol(nct_id, use_ai=True):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trials WHERE nct_id = ?", conn, params=[nct_id])
    if df.empty:
        conn.close()
        return None
    t = df.iloc[0].to_dict()
    first_disease = str(t["disease"]).split(";")[0].strip()
    peers = pd.read_sql("SELECT eligibility FROM trials WHERE disease LIKE ? AND study_type = ?",
                        conn, params=[f"%{first_disease}%", t["study_type"]])
    conn.close()

    inclusion, exclusion = split_criteria(t["eligibility"])
    n = len(inclusion) + len(exclusion)
    peer_counts = peers["eligibility"].apply(_count)
    percentile = round((peer_counts < n).mean() * 100) if len(peer_counts) else None

    low = (t["eligibility"] or "").lower()
    flags = [name for name, pat in FLAGS.items() if re.search(pat, low)]

    if percentile is None:
        complexity = "Unknown"
    elif percentile >= 75:
        complexity = "High"
    elif percentile >= 35:
        complexity = "Medium"
    else:
        complexity = "Low"

    result = {
        "trial": t,
        "inclusion_criteria": inclusion,
        "exclusion_criteria": exclusion,
        "num_criteria": n,
        "peer_median": int(peer_counts.median()) if len(peer_counts) else None,
        "peer_percentile": percentile,
        "peer_group": f"{first_disease} · {str(t['study_type']).title()}",
        "complexity": complexity,
        "flags": flags,
        "ai": None,
    }

    if use_ai:
        prompt = f"""You are a clinical trial feasibility expert at a CRO.
Read this trial's eligibility criteria and return a JSON object with exactly these fields:
- ideal_patient_profile: one short paragraph describing the typical eligible patient
- recruitment_difficulty: one of "Easy", "Medium", "Hard"
- recruitment_reason: one sentence explaining why
- key_risks: list of 3 short feasibility risks (screen failure, recruitment, retention)

Trial: {t['title']}
Phase: {t['all_phases']}
Conditions: {t['conditions']}
Eligibility criteria:
{(t['eligibility'] or '')[:3500]}

Return only valid JSON."""
        result["ai"] = ask_llm_json(prompt)
    return result


def render_protocol_page():
    import streamlit as st

    st.title("🧠 Protocol Intelligence")
    st.markdown("Break down a trial's eligibility criteria, measure how restrictive they are "
                "compared with similar trials, and (optionally) get an AI feasibility read.")
    st.markdown("---")

    nct_id = st.text_input("Enter NCT ID", "NCT06589765",
                           help="Find NCT IDs in Search Trials").strip().upper()
    if not st.button("Analyze Protocol", type="primary"):
        return
    with st.spinner("Analyzing eligibility criteria..."):
        r = analyze_protocol(nct_id)
    if not r:
        st.warning("Trial not found in the database. Use Search Trials to find NCT IDs.")
        return

    t = r["trial"]
    st.markdown(f"#### {t['title']}")
    st.markdown(f"[View on ClinicalTrials.gov ↗](https://clinicaltrials.gov/study/{nct_id})")

    c = st.columns(4)
    c[0].metric("Inclusion criteria", len(r["inclusion_criteria"]))
    c[1].metric("Exclusion criteria", len(r["exclusion_criteria"]))
    c[2].metric("Eligibility complexity", r["complexity"],
                help="Total number of criteria compared with similar trials")
    if r["peer_percentile"] is not None:
        c[3].metric("More criteria than", f"{r['peer_percentile']}% of peers",
                    help=f"Peer group: {r['peer_group']} (median {r['peer_median']} criteria)")

    if r["flags"]:
        st.markdown("**Restrictive criteria detected:** " + " · ".join(f"`{f}`" for f in r["flags"]))

    a, b = st.columns(2)
    with a:
        st.markdown("### ✅ Inclusion criteria")
        for i in r["inclusion_criteria"]:
            st.markdown(f"- {i}")
    with b:
        st.markdown("### ❌ Exclusion criteria")
        for i in r["exclusion_criteria"]:
            st.markdown(f"- {i}")

    st.markdown("---")
    st.markdown("### 🤖 AI feasibility read")
    ai = r["ai"]
    if ai:
        st.caption(f"Generated by {provider()}. AI output can be wrong; always check the full protocol.")
        x, y = st.columns([1, 3])
        x.metric("Recruitment difficulty (AI)", ai.get("recruitment_difficulty", "N/A"))
        y.write(ai.get("recruitment_reason", ""))
        st.info(ai.get("ideal_patient_profile", ""))
        for risk in ai.get("key_risks", []):
            st.warning(risk)
    else:
        st.info("AI analysis is not configured on this deployment. "
                "The data-driven analysis above works without it.")
