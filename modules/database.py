import sqlite3
import json
import os

def create_database():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect("database/trials.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            nct_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            phase TEXT,
            sponsor TEXT,
            enrollment INTEGER,
            start_date TEXT,
            eligibility TEXT,
            disease TEXT
        )
    """)
    conn.commit()
    return conn

def insert_trials(disease="diabetes"):
    conn = create_database()
    cursor = conn.cursor()
    
    with open(f"data/{disease}_trials.json") as f:
        data = json.load(f)
    
    count = 0
    for study in data.get("studies", []):
        m = study.get("protocolSection", {})
        
        nct_id = m.get("identificationModule", {}).get("nctId", "")
        title = m.get("identificationModule", {}).get("briefTitle", "")
        status = m.get("statusModule", {}).get("overallStatus", "")
        phases = m.get("designModule", {}).get("phases", [])
        phase = phases[0] if phases else "N/A"
        sponsor = m.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "")
        enrollment = m.get("designModule", {}).get("enrollmentInfo", {}).get("count", 0)
        start_date = m.get("statusModule", {}).get("startDateStruct", {}).get("date", "")
        eligibility = m.get("eligibilityModule", {}).get("eligibilityCriteria", "")
        
        cursor.execute("""
            INSERT OR REPLACE INTO trials 
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (nct_id, title, status, phase, sponsor, 
              enrollment, start_date, eligibility, disease))
        count += 1
    
    conn.commit()
    conn.close()
    print(f"Done. {count} trials saved to database.")

if __name__ == "__main__":
    insert_trials("diabetes")