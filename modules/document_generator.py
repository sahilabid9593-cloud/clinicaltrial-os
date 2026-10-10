"""
ClinicalTrial OS - Trial Report Generator (v2)
Builds a PDF report in memory (works on Streamlit Cloud) with design,
eligibility, outcomes, sites and registry quality. AI summary is optional.
"""
import io
import json
import sqlite3
from datetime import date
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.llm import ask_llm

DB_PATH = "database/trials.db"
NAVY = colors.HexColor("#1a3a5c")


def _v(x, default="Not reported"):
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() in ("", "NA", "N/A"):
        return default
    s = str(x)
    return s.replace("_", " ").title() if s.isupper() else s


def _p(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def ai_summary(t):
    prompt = f"""Write a factual 2-paragraph executive summary of this clinical trial for a CRO
feasibility team. Use only the information given. No headings.

Title: {t['title']}
Phase: {t['all_phases']} | Status: {t['status']} | Sponsor: {t['sponsor']}
Design: {t['allocation']}, {t['masking']} masking, {t['primary_purpose']}
Enrollment: {t['enrollment']} | Sites: {t['num_sites']} in {t['num_countries']} countries
Summary: {(t['brief_summary'] or '')[:1500]}"""
    return ask_llm(prompt, max_tokens=600)


def generate_report(nct_id, use_ai=True):
    """Return (pdf_bytes, used_ai) or (None, False) if the trial is not found."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trials WHERE nct_id = ?", conn, params=[nct_id])
    sites = pd.read_sql("""SELECT country, COUNT(*) AS sites FROM locations WHERE nct_id = ?
                           GROUP BY country ORDER BY sites DESC LIMIT 10""", conn, params=[nct_id])
    conn.close()
    if df.empty:
        return None, False
    t = df.iloc[0].to_dict()

    summary = ai_summary(t) if use_ai else None
    used_ai = bool(summary)
    if not summary:
        summary = t["brief_summary"] or "No summary reported."

    label = ParagraphStyle("Label", fontSize=8, fontName="Helvetica-Bold", textColor=colors.grey)
    title = ParagraphStyle("T", fontSize=16, fontName="Helvetica-Bold", textColor=NAVY,
                           leading=20, spaceAfter=8)
    h = ParagraphStyle("H", fontSize=12, fontName="Helvetica-Bold", textColor=NAVY,
                       spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("B", fontSize=9.5, fontName="Helvetica", leading=14, spaceAfter=6)
    cell = ParagraphStyle("C", fontSize=8.5, fontName="Helvetica", leading=11)
    cellw = ParagraphStyle("CW", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")

    def grid(rows, widths):
        data = [[Paragraph(escape(str(a)), cellw), Paragraph(escape(str(b)), cell),
                 Paragraph(escape(str(c)), cellw), Paragraph(escape(str(d)), cell)] for a, b, c, d in rows]
        tb = Table(data, colWidths=widths)
        tb.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
            ("BACKGROUND", (0, 0), (0, -1), NAVY), ("BACKGROUND", (2, 0), (2, -1), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.white)]))
        return tb

    c = [
        _p(f"ClinicalTrial OS · Trial Report · {date.today():%d %b %Y}", label),
        Spacer(1, 6),
        _p(t["title"], title),
        _p(f"{t['nct_id']} · https://clinicaltrials.gov/study/{t['nct_id']}", label),
        Spacer(1, 10),
        grid([
            ("Status", _v(t["status"]), "Phase", _v(t["all_phases"])),
            ("Sponsor", _v(t["sponsor"]), "Sponsor type", _v(t["sponsor_class"])),
            ("Enrollment", f"{_v(t['enrollment'])} ({_v(t['enrollment_type'])})", "Sites",
             f"{int(t['num_sites'] or 0)} in {int(t['num_countries'] or 0)} countries"),
            ("Start", _v(t["start_date"]), "Primary completion", _v(t["primary_completion_date"])),
            ("Allocation", _v(t["allocation"]), "Masking", _v(t["masking"])),
            ("Purpose", _v(t["primary_purpose"]), "Results posted", "Yes" if t["has_results"] else "No"),
        ], [75, 165, 85, 165]),
        _p("Executive summary" + (" (AI-generated)" if used_ai else " (from registry)"), h),
        _p(summary, body),
        _p("Interventions", h),
        _p(_v(t["interventions"]), body),
    ]
    if t.get("why_stopped"):
        c += [_p("Why stopped", h), _p(t["why_stopped"], body)]

    for name, col in [("Primary outcomes", "primary_outcomes"), ("Secondary outcomes", "secondary_outcomes")]:
        items = json.loads(t[col] or "[]")[:8]
        if items:
            c.append(_p(name, h))
            for o in items:
                c.append(_p(f"• {o['measure']}  [{o.get('timeFrame', '')}]", body))

    c += [_p("Eligibility", h),
          _p(f"Age: {_v(t['min_age'], 'Any')} to {_v(t['max_age'], 'Any')} · Sex: {_v(t['sex'])}", body),
          _p((t["eligibility"] or "Not reported")[:2500], body)]

    if not sites.empty:
        c.append(_p("Site footprint (top countries)", h))
        c.append(_p(", ".join(f"{r.country} ({r.sites})" for r in sites.itertuples()), body))

    try:
        from modules.regulatory_compliance import score_trial
        score, grade, _ = score_trial(t)
        c += [_p("Registry quality", h), _p(f"{score:.0f}% ({grade}) on ClinicalTrial OS registry checks.", body)]
    except Exception:
        pass

    c += [Spacer(1, 18),
          _p("Source: ClinicalTrials.gov. For research and educational use only; not medical, "
             "regulatory or legal advice. Generated by ClinicalTrial OS (open source).", label)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, rightMargin=45, leftMargin=45,
                      topMargin=45, bottomMargin=45, title=f"{t['nct_id']} report").build(c)
    return buf.getvalue(), used_ai


def render_report_page():
    import streamlit as st

    st.title("📄 Generate Trial Report")
    st.markdown("Create a downloadable PDF report for any trial: design, outcomes, "
                "eligibility, site footprint and registry quality.")
    st.markdown("---")

    nct_id = st.text_input("Enter NCT ID", "NCT06589765").strip().upper()
    if st.button("Generate PDF Report", type="primary"):
        with st.spinner("Building report..."):
            pdf, used_ai = generate_report(nct_id)
        if not pdf:
            st.warning("Trial not found in the database. Use Search Trials to find NCT IDs.")
            return
        st.success("Report ready" + (" (with AI summary)" if used_ai else ""))
        st.download_button("⬇️ Download PDF", pdf, file_name=f"{nct_id}_report.pdf",
                           mime="application/pdf", type="primary")
