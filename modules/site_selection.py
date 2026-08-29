import sqlite3
import pandas as pd

def rank_sites(disease="diabetes"):
    print(f"Ranking sites for: {disease}")
    
    conn = sqlite3.connect("database/trials.db")
    df = pd.read_sql("""
        SELECT sponsor, phase, status, enrollment
        FROM trials
        WHERE disease LIKE ? AND enrollment > 0
    """, conn, params=[f"%{disease}%"])
    conn.close()

    sponsor_stats = df.groupby("sponsor").agg(
        total_trials=("sponsor", "count"),
        avg_enrollment=("enrollment", "mean"),
        completed=("status", lambda x: (x == "COMPLETED").sum())
    ).reset_index()

    sponsor_stats["success_rate"] = (
        sponsor_stats["completed"] / sponsor_stats["total_trials"] * 100
    ).round(1)

    sponsor_stats["site_score"] = (
        sponsor_stats["total_trials"] * 0.4 +
        sponsor_stats["avg_enrollment"] * 0.01 +
        sponsor_stats["success_rate"] * 0.6
    ).round(2)

    sponsor_stats = sponsor_stats.sort_values(
        "site_score", ascending=False).head(10)

    print("\n--- TOP 10 RECOMMENDED SITES ---")
    for i, row in sponsor_stats.iterrows():
        print(f"{row['sponsor'][:40]:<40} Score: {row['site_score']:.1f} | "
              f"Trials: {row['total_trials']} | "
              f"Success: {row['success_rate']}%")

    return sponsor_stats

if __name__ == "__main__":
    rank_sites("diabetes")