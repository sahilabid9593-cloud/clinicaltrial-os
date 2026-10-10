"""
ClinicalTrial OS - Recruitment & Timeline Benchmark (v2)

Instead of guessing, this looks at REAL completed trials that are similar
(same disease area, same phase, similar size) and reports:
  - how long they took from study start to primary completion
  - how many patients each site enrolled per month
and estimates a timeline for your planned trial from those benchmarks.
"""
import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "database/trials.db"


def _months(start, end):
    s = pd.to_datetime(start, errors="coerce", format="mixed")
    e = pd.to_datetime(end, errors="coerce", format="mixed")
    return (e - s).dt.days / 30.44


def load_completed():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""SELECT nct_id, title, disease, phase, enrollment, num_sites,
                               start_date, primary_completion_date, sponsor_class
                        FROM trials
                        WHERE status = 'COMPLETED' AND study_type = 'INTERVENTIONAL'
                          AND enrollment_type = 'ACTUAL' AND enrollment > 0
                          AND start_date != '' AND primary_completion_date != ''""", conn)
    conn.close()
    df["months"] = _months(df["start_date"], df["primary_completion_date"])
    df = df[(df["months"] >= 1) & (df["months"] <= 180)].copy()
    df["pts_per_month"] = df["enrollment"] / df["months"]
    df["pts_per_site_month"] = np.where(df["num_sites"] > 0,
                                        df["enrollment"] / df["num_sites"] / df["months"], np.nan)
    return df


def benchmark(disease, phase, enrollment, sites, min_peers=15):
    df = load_completed()
    steps = [
        ("same disease, phase and similar size",
         df["disease"].str.contains(disease, regex=False) & (df["phase"] == phase)
         & df["enrollment"].between(enrollment / 2, enrollment * 2)),
        ("same disease and phase",
         df["disease"].str.contains(disease, regex=False) & (df["phase"] == phase)),
        ("same phase and similar size (all diseases)",
         (df["phase"] == phase) & df["enrollment"].between(enrollment / 2, enrollment * 2)),
        ("same phase (all diseases)", df["phase"] == phase),
    ]
    for label, mask in steps:
        peers = df[mask]
        if len(peers) >= min_peers:
            break

    q = peers["months"].quantile([0.25, 0.5, 0.75])
    rate = peers["pts_per_site_month"].dropna()
    r25, r50, r75 = rate.quantile([0.25, 0.5, 0.75]) if len(rate) else (np.nan,) * 3

    def est(r):
        return enrollment / (sites * r) if r and r > 0 else np.nan

    return {
        "peers": peers.sort_values("months"),
        "peer_rule": label,
        "n_peers": len(peers),
        "duration_median": q[0.5], "duration_q1": q[0.25], "duration_q3": q[0.75],
        "site_rate_median": r50,
        # slower rate (25th pct) -> longer time; faster rate (75th) -> shorter
        "enroll_months_median": est(r50), "enroll_months_slow": est(r25), "enroll_months_fast": est(r75),
    }


def predict_recruitment(phase, enrollment, status=None, disease="diabetes", sites=10):
    """Backward-compatible wrapper."""
    b = benchmark(disease, phase, enrollment, sites)
    return {"recruitment_speed": f"{b['site_rate_median']:.2f} pts/site/month",
            "estimated_timeline": f"{b['duration_median']:.0f} months",
            "recommendation": f"Based on {b['n_peers']} completed trials ({b['peer_rule']})."}


def render_recruitment_page():
    import streamlit as st
    import plotly.express as px

    st.title("📈 Recruitment & Timeline Benchmark")
    st.markdown("Plan your trial using what **actually happened** in similar completed trials.")
    st.markdown("---")

    df = load_completed()
    diseases = sorted({p.strip() for d in df["disease"] for p in d.split(";") if p.strip()})
    phases = [p for p in ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "N/A"]
              if p in set(df["phase"])]

    a, b, c, d = st.columns(4)
    disease = a.selectbox("Disease area", diseases,
                          index=diseases.index("diabetes") if "diabetes" in diseases else 0)
    phase = b.selectbox("Phase", phases, index=phases.index("PHASE3") if "PHASE3" in phases else 0,
                        format_func=lambda p: p.replace("_", " ").title() if p != "N/A" else "Not applicable")
    enrollment = c.number_input("Target enrollment", 10, 20000, 300, step=10)
    sites = d.number_input("Planned sites", 1, 1000, 20)

    r = benchmark(disease, phase, enrollment, sites)
    st.caption(f"Benchmark: **{r['n_peers']} completed trials** ({r['peer_rule']}), "
               f"median **{r['peers']['enrollment'].median():.0f} patients** across "
               f"**{r['peers']['num_sites'].median():.0f} site(s)**.")

    m = st.columns(3)
    m[0].metric("Typical start → primary completion",
                f"{r['duration_median']:.0f} months",
                help=f"Middle 50% of similar trials: {r['duration_q1']:.0f}–{r['duration_q3']:.0f} months")
    m[1].metric("Typical enrollment rate", f"{r['site_rate_median']:.2f}",
                help="Median patients enrolled per site per month in similar trials")
    m[2].metric("Your estimated enrollment period",
                f"{r['enroll_months_median']:.0f} months",
                help=f"Range {r['enroll_months_fast']:.0f}–{r['enroll_months_slow']:.0f} months "
                     f"using faster/slower peer site rates")
    st.info(f"With **{sites} sites** enrolling at the typical rate, reaching **{enrollment:,} patients** "
            f"would take about **{r['enroll_months_median']:.0f} months** "
            f"(range {r['enroll_months_fast']:.0f}–{r['enroll_months_slow']:.0f}). "
            f"Similar trials took **{r['duration_median']:.0f} months** from start to primary completion, "
            f"which also includes treatment and follow-up.")

    peers = r["peers"]
    st.plotly_chart(px.histogram(peers, x="months", nbins=25,
                                 labels={"months": "Months from start to primary completion"},
                                 title="Duration of similar completed trials")
                    .add_vline(x=r["duration_median"], line_dash="dash"), width="stretch")

    with st.expander(f"See the {len(peers)} benchmark trials"):
        show = peers[["nct_id", "title", "enrollment", "num_sites", "months", "pts_per_site_month"]].copy()
        show["months"] = show["months"].round(1)
        show["pts_per_site_month"] = show["pts_per_site_month"].round(2)
        st.dataframe(show, width="stretch", hide_index=True)

    with st.expander("ℹ️ Method and limitations"):
        st.markdown("""
- Uses completed interventional trials with **actual** enrollment and reported start and primary completion dates.
- Start → primary completion includes recruitment **and** treatment/follow-up, so it is longer than recruitment alone.
- Enrollment rate assumes all sites are open for the whole period; in reality sites activate gradually,
  so real timelines are usually longer than the estimate.
- If too few close matches exist, the benchmark widens (shown above the metrics).
""")
