import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np

def build_model():
    print("Building recruitment prediction model...")
    conn = sqlite3.connect("database/trials.db")
    df = pd.read_sql("""
        SELECT phase, enrollment, status, sponsor
        FROM trials 
        WHERE enrollment > 0
    """, conn)
    conn.close()

    df["enrollment"] = pd.to_numeric(df["enrollment"], errors="coerce")
    df = df.dropna()

    df["recruitment_speed"] = df["enrollment"].apply(
        lambda x: "Fast" if x < 100 else ("Medium" if x < 500 else "Slow")
    )

    le_phase = LabelEncoder()
    le_status = LabelEncoder()
    df["phase_enc"] = le_phase.fit_transform(df["phase"].astype(str))
    df["status_enc"] = le_status.fit_transform(df["status"].astype(str))

    X = df[["phase_enc", "status_enc", "enrollment"]]
    y = df["recruitment_speed"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    score = model.score(X_test, y_test)
    print(f"Model accuracy: {score:.0%}")

    return model, le_phase, le_status

def predict_recruitment(phase, enrollment, status="RECRUITING"):
    model, le_phase, le_status = build_model()

    try:
        phase_enc = le_phase.transform([phase])[0]
    except:
        phase_enc = 0

    try:
        status_enc = le_status.transform([status])[0]
    except:
        status_enc = 0

    prediction = model.predict([[phase_enc, status_enc, enrollment]])[0]
    
    timeline = {
        "Fast": "3 to 6 months",
        "Medium": "6 to 18 months", 
        "Slow": "18 to 36 months"
    }

    result = {
        "recruitment_speed": prediction,
        "estimated_timeline": timeline[prediction],
        "enrollment_target": enrollment,
        "phase": phase,
        "recommendation": f"This {phase} trial with {enrollment} patients is predicted to have {prediction} recruitment."
    }

    print(f"\n--- RECRUITMENT PREDICTION ---")
    print(f"Speed: {result['recruitment_speed']}")
    print(f"Timeline: {result['estimated_timeline']}")
    print(f"Recommendation: {result['recommendation']}")
    return result

if __name__ == "__main__":
    predict_recruitment("PHASE3", 500)