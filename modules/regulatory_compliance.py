import sqlite3
import requests
import json

# ICH GCP Guidelines - key requirements every trial must have
GCP_REQUIREMENTS = [
    "informed consent",
    "inclusion criteria",
    "exclusion criteria",
    "primary endpoint",
    "secondary endpoint",
    "sample size",
    "randomization",
    "adverse event",
    "stopping rules",
    "ethics committee"
]

def check_compliance(nct_id):
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
    text = (eligibility or "").lower()

    print(f"\nChecking compliance for: {nct_id}")
    print(f"Title: {title[:60]}")
    print(f"\n--- ICH GCP COMPLIANCE CHECK ---")

    passed = []
    failed = []

    for requirement in GCP_REQUIREMENTS:
        if requirement.lower() in text:
            passed.append(requirement)
            print(f"  ✓ {requirement}")
        else:
            failed.append(requirement)
            print(f"  ✗ {requirement} — NOT FOUND")

    score = len(passed) / len(GCP_REQUIREMENTS) * 100

    print(f"\n--- COMPLIANCE SCORE ---")
    print(f"Score: {score:.0f}%")
    print(f"Passed: {len(passed)}/{len(GCP_REQUIREMENTS)} requirements")

    if score >= 80:
        status = "COMPLIANT"
        advice = "Trial meets most GCP requirements."
    elif score >= 50:
        status = "PARTIALLY COMPLIANT"
        advice = f"Missing: {', '.join(failed[:3])}"
    else:
        status = "NON COMPLIANT"
        advice = f"Major gaps found. Missing: {', '.join(failed)}"

    print(f"Status: {status}")
    print(f"Advice: {advice}")

    result = {
        "nct_id": nct_id,
        "title": title,
        "compliance_score": score,
        "status": status,
        "passed": passed,
        "failed": failed,
        "advice": advice
    }

    # Now use AI to give deeper analysis
    print("\nAI doing deeper analysis...")
    prompt = f"""You are a GCP regulatory expert.
Review this clinical trial eligibility criteria and identify:
1. Top 3 compliance strengths
2. Top 3 compliance gaps
3. One key recommendation

Trial: {title}
Phase: {phase}
Criteria: {(eligibility or '')[:2000]}

Be specific and professional. Keep response under 200 words."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        ai_analysis = response.json()["response"]
        result["ai_analysis"] = ai_analysis
        print(f"\nAI Analysis:\n{ai_analysis}")
    except:
        result["ai_analysis"] = "AI analysis unavailable"

    return result

if __name__ == "__main__":
    conn = sqlite3.connect("database/trials.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nct_id FROM trials LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        check_compliance(row[0])