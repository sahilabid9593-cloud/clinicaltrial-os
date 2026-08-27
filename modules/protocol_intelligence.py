import sqlite3
import json
import requests

def analyze_protocol(nct_id):
    conn = sqlite3.connect("database/trials.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, eligibility, phase, sponsor 
        FROM trials WHERE nct_id=?
    """, (nct_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("Trial not found")
        return None
    
    title, eligibility, phase, sponsor = row
    
    if not eligibility:
        print("No eligibility criteria found")
        return None

    prompt = f"""You are a clinical trial expert working at a CRO.
Analyze this clinical trial and return a JSON object with exactly these fields:
- inclusion_criteria: list of requirements to join the trial
- exclusion_criteria: list of reasons a patient cannot join
- ideal_patient_profile: one paragraph describing the perfect patient
- recruitment_difficulty: one word - Easy, Medium, or Hard
- recruitment_reason: one sentence explaining why
- estimated_patient_pool: one word - Large, Medium, or Small
- key_risks: list of 3 main risks for this trial

Trial Title: {title}
Phase: {phase}
Sponsor: {sponsor}
Eligibility Criteria:
{eligibility[:3000]}

Return only valid JSON. No extra text."""

    print(f"Analyzing trial: {nct_id}")
    print(f"Title: {title}")
    print("AI is thinking... please wait 30 seconds...")
    
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )
    
    result_text = response.json()["response"]
    
    # Extract JSON from response
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    json_str = result_text[start:end]
    result = json.loads(json_str)
    
    print("\n--- PROTOCOL ANALYSIS ---")
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    conn = sqlite3.connect("database/trials.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nct_id, title FROM trials LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        print(f"Testing with: {row[0]}")
        analyze_protocol(row[0])