import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np

def build_risk_model():
    print("Building trial risk prediction model...")
    conn = sqlite3.connect("database/trials.db")
    df = pd.read_sql("""
        SELECT phase, enrollment, status, sponsor
        FROM trials
        WHERE enrollment > 0 AND status != ''
    """, conn)
    conn.close()

    df["enrollment"] = pd.to_numeric(df["enrollment"], errors="coerce")
    df = df.dropna()

    df["is_terminated"] = df["status"].apply(
        lambda x: 1 if x in ["TERMINATED", "WITHDRAWN", "SUSPENDED"] else 0
    )

    le_phase = LabelEncoder()
    df["phase_enc"] = le_phase.fit_transform(df["phase"].astype(str))

    df["sponsor_size"] = df["sponsor"].apply(
        lambda x: 2 if any(big in str(x).upper() for big in 
        ["PFIZER","NOVARTIS","ROCHE","JOHNSON","MERCK","ASTRA"]) 
        else 1
    )

    X = df[["phase_enc", "enrollment", "sponsor_size"]]
    y = df["is_terminated"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    score = model.score(X_test, y_test)
    print(f"Model accuracy: {score:.0%}")
    return model, le_phase

def predict_risk(phase, enrollment, sponsor_name):
    model, le_phase = build_risk_model()

    try:
        phase_enc = le_phase.transform([phase])[0]
    except:
        phase_enc = 0

    sponsor_size = 2 if any(big in sponsor_name.upper() for big in
        ["PFIZER","NOVARTIS","ROCHE","JOHNSON","MERCK","ASTRA"]) else 1

    prob = model.predict_proba([[phase_enc, enrollment, sponsor_size]])[0]
    risk_score = round(prob[1] * 100, 1)

    if risk_score < 20:
        risk_level = "LOW"
        color = "GREEN"
        advice = "Trial has good chance of completion."
    elif risk_score < 50:
        risk_level = "MEDIUM"
        color = "YELLOW"
        advice = "Monitor recruitment and protocol carefully."
    else:
        risk_level = "HIGH"
        color = "RED"
        advice = "Consider simplifying eligibility criteria and adding more sites."

    result = {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "color": color,
        "advice": advice,
        "phase": phase,
        "enrollment": enrollment,
        "sponsor": sponsor_name
    }

    print(f"\n--- TRIAL RISK PREDICTION ---")
    print(f"Risk Score: {risk_score}%")
    print(f"Risk Level: {risk_level}")
    print(f"Advice: {advice}")
    return result

if __name__ == "__main__":
    predict_risk("PHASE3", 500, "Small Biotech Inc")
    predict_risk("PHASE1", 50, "Pfizer")