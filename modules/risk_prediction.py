"""
ClinicalTrial OS - Trial Risk Prediction (v2)

Predicts the chance that an interventional trial ends early
(TERMINATED or WITHDRAWN) instead of COMPLETED.

- Trained ONLY on finished trials (ongoing trials have no outcome yet).
- Uses ONLY design features known before the trial starts
  (no actual enrollment, which leaks the outcome for stopped trials).
- Reports honest cross-validated performance (ROC AUC).
"""
import sqlite3
import numpy as np
import pandas as pd
from sklearn.compose import make_column_transformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from modules.protocol_intelligence import split_criteria

DB_PATH = "database/trials.db"
CAT = ["phase", "sponsor_class", "allocation", "masking", "primary_purpose", "disease1", "itype"]
NUM = ["n_criteria", "num_primary_outcomes", "num_secondary_outcomes"]

LABELS = {
    "phase": "Phase", "sponsor_class": "Sponsor type", "allocation": "Allocation",
    "masking": "Masking", "primary_purpose": "Primary purpose", "disease1": "Disease area",
    "itype": "Intervention type", "n_criteria": "Number of eligibility criteria",
    "num_primary_outcomes": "Primary outcomes", "num_secondary_outcomes": "Secondary outcomes",
}


def _features(df):
    df = df.copy()
    df["disease1"] = df["disease"].astype(str).str.split(";").str[0].str.strip()
    df["itype"] = df["intervention_types"].fillna("").astype(str).str.split(";").str[0].str.strip()
    df["n_criteria"] = df["eligibility"].apply(lambda e: sum(map(len, split_criteria(e))))
    for c in CAT:
        df[c] = df[c].fillna("").astype(str)
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def load_training_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""SELECT * FROM trials WHERE study_type = 'INTERVENTIONAL'
                        AND status IN ('COMPLETED', 'TERMINATED', 'WITHDRAWN')""", conn)
    conn.close()
    df = _features(df)
    df["stopped"] = (df["status"] != "COMPLETED").astype(int)
    return df


def build_risk_model():
    df = load_training_data()
    pre = make_column_transformer(
        (OneHotEncoder(handle_unknown="ignore", min_frequency=10), CAT),
        (StandardScaler(), NUM))
    model = make_pipeline(pre, LogisticRegression(max_iter=2000, C=0.5))
    cv = StratifiedKFold(5, shuffle=True, random_state=42)
    auc = cross_val_score(model, df[CAT + NUM], df["stopped"], cv=cv, scoring="roc_auc").mean()
    model.fit(df[CAT + NUM], df["stopped"])
    info = {"auc": round(auc, 2), "n_trials": len(df),
            "base_rate": round(df["stopped"].mean() * 100, 1), "data": df}
    return model, info


def predict_risk_row(model, info, row):
    """row: dict with the CAT + NUM fields. Returns result dict."""
    X = pd.DataFrame([row])[CAT + NUM]
    p = float(model.predict_proba(X)[0, 1]) * 100
    base = info["base_rate"]
    if p < base * 0.75:
        level, advice = "LOW", "Lower than the average early-stop rate for similar finished trials."
    elif p < base * 1.5:
        level, advice = "MEDIUM", "Close to the average early-stop rate. Watch enrollment and site activation."
    else:
        level, advice = "HIGH", ("Well above average. Review eligibility restrictiveness, recruitment "
                                 "plan and site count before launch.")

    # Contribution of each feature (logistic regression: coefficient x value)
    pre, lr = model.named_steps["columntransformer"], model.named_steps["logisticregression"]
    contrib = pre.transform(X)
    contrib = np.asarray(contrib.todense() if hasattr(contrib, "todense") else contrib)[0] * lr.coef_[0]
    names = pre.get_feature_names_out()
    drivers = {}
    for n, v in zip(names, contrib):
        key = n.split("__", 1)[1]
        base_key = next((c for c in CAT + NUM if key == c or key.startswith(c + "_")), key)
        drivers[base_key] = drivers.get(base_key, 0) + v
    drivers = pd.DataFrame([{"factor": LABELS.get(k, k), "effect": round(v, 3)} for k, v in drivers.items()])
    drivers = drivers.reindex(drivers["effect"].abs().sort_values(ascending=False).index)
    return {"risk_score": round(p, 1), "risk_level": level, "advice": advice, "drivers": drivers}


def predict_risk(phase, enrollment=None, sponsor_name=None):
    """Backward-compatible simple call."""
    model, info = build_risk_model()
    df = info["data"]
    row = {c: df[c].mode()[0] for c in CAT}
    row.update({c: float(df[c].median()) for c in NUM})
    row["phase"] = phase
    return predict_risk_row(model, info, row)


def render_risk_page():
    import streamlit as st
    import plotly.express as px

    @st.cache_resource(show_spinner="Training risk model on finished trials...")
    def _model():
        return build_risk_model()

    st.title("⚠️ Trial Risk Prediction")
    st.markdown("Estimate the chance an interventional trial **stops early** (terminated or withdrawn), "
                "using only design choices known before the trial starts.")
    st.markdown("---")

    model, info = _model()
    df = info["data"]
    a, b, c = st.columns(3)
    a.metric("Trained on", f"{info['n_trials']:,} finished trials")
    b.metric("Average early-stop rate", f"{info['base_rate']}%")
    c.metric("Model accuracy (ROC AUC)", info["auc"],
             help="5-fold cross-validated. 0.5 = random, 1.0 = perfect. ~0.65-0.70 means a moderate signal.")

    mode = st.radio("Input", ["Score an existing trial", "Design a new trial"], horizontal=True)

    if mode == "Score an existing trial":
        nct_id = st.text_input("NCT ID", "NCT06589765").strip().upper()
        conn = sqlite3.connect(DB_PATH)
        t = pd.read_sql("SELECT * FROM trials WHERE nct_id = ?", conn, params=[nct_id])
        conn.close()
        if t.empty:
            st.warning("Trial not found. Use Search Trials to find NCT IDs.")
            return
        if t.iloc[0]["study_type"] != "INTERVENTIONAL":
            st.info("This model only covers interventional trials.")
            return
        row = _features(t).iloc[0][CAT + NUM].to_dict()
        st.caption(f"{t.iloc[0]['title']} · actual status: **{t.iloc[0]['status']}**")
    else:
        opts = lambda col: sorted(df[col].value_counts().loc[lambda s: s >= 10].index.tolist())
        x, y, z = st.columns(3)
        row = {
            "disease1": x.selectbox("Disease area", opts("disease1")),
            "phase": y.selectbox("Phase", opts("phase"), index=opts("phase").index("PHASE3")
                                 if "PHASE3" in opts("phase") else 0),
            "sponsor_class": z.selectbox("Sponsor type", opts("sponsor_class")),
            "allocation": x.selectbox("Allocation", opts("allocation")),
            "masking": y.selectbox("Masking", opts("masking")),
            "primary_purpose": z.selectbox("Primary purpose", opts("primary_purpose")),
            "itype": x.selectbox("Intervention type", opts("itype")),
            "n_criteria": y.number_input("Number of eligibility criteria", 1, 100, 15),
            "num_primary_outcomes": z.number_input("Primary outcomes", 1, 30, 1),
            "num_secondary_outcomes": x.number_input("Secondary outcomes", 0, 60, 5),
        }

    r = predict_risk_row(model, info, row)
    a, b = st.columns(2)
    a.metric("Predicted early-stop risk", f"{r['risk_score']}%",
             delta=f"{r['risk_score'] - info['base_rate']:+.1f} pts vs average", delta_color="inverse")
    b.metric("Risk level", r["risk_level"])
    {"LOW": st.success, "MEDIUM": st.warning, "HIGH": st.error}[r["risk_level"]](r["advice"])

    st.markdown("#### What drives this estimate")
    d = r["drivers"].head(8).copy()
    d["direction"] = np.where(d["effect"] > 0, "Raises risk", "Lowers risk")
    st.plotly_chart(px.bar(d, x="effect", y="factor", orientation="h", color="direction",
                           color_discrete_map={"Raises risk": "#d64545", "Lowers risk": "#2e8b57"},
                           labels={"effect": "Effect on log-odds", "factor": ""})
                    .update_layout(yaxis={"categoryorder": "total ascending"}, height=360),
                    width="stretch")

    with st.expander("ℹ️ Method and limitations"):
        st.markdown(f"""
- Logistic regression trained on {info['n_trials']:,} finished interventional trials in this database
  (completed vs. terminated/withdrawn).
- Only pre-trial design features are used. Actual enrollment and site counts are excluded because
  stopped trials report truncated values, which would make the model look better than it is.
- Cross-validated ROC AUC is **{info['auc']}**: a moderate signal, useful for comparing designs,
  not for deciding whether a specific trial will fail.
- Trials stop for many reasons not in registry data (funding, business decisions, safety findings).
""")
