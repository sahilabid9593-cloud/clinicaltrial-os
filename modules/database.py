"""
ClinicalTrial OS - Database Builder (v2)
Builds database/trials.db from the ClinicalTrials.gov JSON files in data/.

Tables:
  trials     - one row per trial (rich fields: design, dates, outcomes, ages...)
  locations  - one row per trial site (facility, city, country, GPS)
  metadata   - build info (date, counts)

Run from the project root:
    python modules/database.py
"""
import sqlite3
import json
import os
import glob
from datetime import datetime

DB_PATH = "database/trials.db"
DATA_DIR = "data"

TRIAL_COLUMNS = [
    # --- original columns (kept so the existing app keeps working) ---
    "nct_id", "title", "status", "phase", "sponsor", "enrollment",
    "start_date", "eligibility", "disease",
    # --- new columns ---
    "official_title", "brief_summary", "conditions", "keywords",
    "interventions", "intervention_types",
    "study_type", "all_phases", "allocation", "intervention_model",
    "masking", "primary_purpose", "enrollment_type",
    "primary_completion_date", "completion_date", "first_posted",
    "last_updated", "why_stopped",
    "primary_outcomes", "secondary_outcomes",
    "num_primary_outcomes", "num_secondary_outcomes",
    "sponsor_class", "collaborators",
    "has_dmc", "fda_regulated_drug", "fda_regulated_device",
    "sex", "min_age", "max_age", "age_groups", "healthy_volunteers",
    "num_sites", "num_countries", "countries", "has_results",
]

INT_COLUMNS = ("enrollment", "num_primary_outcomes", "num_secondary_outcomes",
               "num_sites", "num_countries", "has_results", "has_dmc",
               "fda_regulated_drug", "fda_regulated_device", "healthy_volunteers")


def create_database():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Rebuild from scratch so the new schema is always applied
    cur.execute("DROP TABLE IF EXISTS trials")
    cur.execute("DROP TABLE IF EXISTS locations")
    cur.execute("DROP TABLE IF EXISTS metadata")

    cols_sql = ",\n".join(
        f"{c} TEXT PRIMARY KEY" if c == "nct_id"
        else f"{c} INTEGER" if c in INT_COLUMNS
        else f"{c} TEXT"
        for c in TRIAL_COLUMNS
    )
    cur.execute(f"CREATE TABLE trials ({cols_sql})")
    cur.execute("""
        CREATE TABLE locations (
            nct_id TEXT,
            facility TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            lat REAL,
            lon REAL,
            site_status TEXT
        )
    """)
    cur.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def _bool(value):
    """Convert True/False/None to 1/0/NULL."""
    if value is None:
        return None
    return 1 if value else 0


def parse_study(study, disease):
    p = study.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status = p.get("statusModule", {})
    sponsor = p.get("sponsorCollaboratorsModule", {})
    desc = p.get("descriptionModule", {})
    cond = p.get("conditionsModule", {})
    design = p.get("designModule", {})
    design_info = design.get("designInfo", {})
    arms = p.get("armsInterventionsModule", {})
    outcomes = p.get("outcomesModule", {})
    elig = p.get("eligibilityModule", {})
    oversight = p.get("oversightModule", {})
    locs = p.get("contactsLocationsModule", {}).get("locations", [])

    phases = design.get("phases", [])
    interventions = arms.get("interventions", [])
    prim = outcomes.get("primaryOutcomes", [])
    sec = outcomes.get("secondaryOutcomes", [])
    countries = sorted({l.get("country") for l in locs if l.get("country")})

    row = {
        "nct_id": ident.get("nctId", ""),
        "title": ident.get("briefTitle", ""),
        "status": status.get("overallStatus", ""),
        "phase": phases[-1] if phases else "N/A",
        "sponsor": sponsor.get("leadSponsor", {}).get("name", ""),
        "enrollment": design.get("enrollmentInfo", {}).get("count", 0),
        "start_date": status.get("startDateStruct", {}).get("date", ""),
        "eligibility": elig.get("eligibilityCriteria", ""),
        "disease": disease,
        "official_title": ident.get("officialTitle", ""),
        "brief_summary": desc.get("briefSummary", ""),
        "conditions": "; ".join(cond.get("conditions", [])),
        "keywords": "; ".join(cond.get("keywords", [])),
        "interventions": "; ".join(i.get("name", "") for i in interventions),
        "intervention_types": "; ".join(sorted({i.get("type", "") for i in interventions})),
        "study_type": design.get("studyType", ""),
        "all_phases": "/".join(phases) if phases else "N/A",
        "allocation": design_info.get("allocation", ""),
        "intervention_model": design_info.get("interventionModel", ""),
        "masking": design_info.get("maskingInfo", {}).get("masking", ""),
        "primary_purpose": design_info.get("primaryPurpose", ""),
        "enrollment_type": design.get("enrollmentInfo", {}).get("type", ""),
        "primary_completion_date": status.get("primaryCompletionDateStruct", {}).get("date", ""),
        "completion_date": status.get("completionDateStruct", {}).get("date", ""),
        "first_posted": status.get("studyFirstPostDateStruct", {}).get("date", ""),
        "last_updated": status.get("lastUpdatePostDateStruct", {}).get("date", ""),
        "why_stopped": status.get("whyStopped", ""),
        "primary_outcomes": json.dumps(
            [{"measure": o.get("measure", ""), "timeFrame": o.get("timeFrame", "")} for o in prim]),
        "secondary_outcomes": json.dumps(
            [{"measure": o.get("measure", ""), "timeFrame": o.get("timeFrame", "")} for o in sec]),
        "num_primary_outcomes": len(prim),
        "num_secondary_outcomes": len(sec),
        "sponsor_class": sponsor.get("leadSponsor", {}).get("class", ""),
        "collaborators": "; ".join(c.get("name", "") for c in sponsor.get("collaborators", [])),
        "has_dmc": _bool(oversight.get("oversightHasDmc")),
        "fda_regulated_drug": _bool(oversight.get("isFdaRegulatedDrug")),
        "fda_regulated_device": _bool(oversight.get("isFdaRegulatedDevice")),
        "sex": elig.get("sex", ""),
        "min_age": elig.get("minimumAge", ""),
        "max_age": elig.get("maximumAge", ""),
        "age_groups": "; ".join(elig.get("stdAges", [])),
        "healthy_volunteers": _bool(elig.get("healthyVolunteers")),
        "num_sites": len(locs),
        "num_countries": len(countries),
        "countries": "; ".join(countries),
        "has_results": _bool(study.get("hasResults", False)),
    }

    location_rows = [
        (row["nct_id"], l.get("facility", ""), l.get("city", ""), l.get("state", ""),
         l.get("country", ""), l.get("geoPoint", {}).get("lat"),
         l.get("geoPoint", {}).get("lon"), l.get("status", ""))
        for l in locs
    ]
    return row, location_rows


def build_all():
    conn = create_database()
    cur = conn.cursor()
    placeholders = ",".join("?" * len(TRIAL_COLUMNS))
    seen = set()
    total_sites = 0

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*_trials.json")))
    for path in files:
        disease = os.path.basename(path).replace("_trials.json", "")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for study in data.get("studies", []):
            row, loc_rows = parse_study(study, disease)
            nct = row["nct_id"]
            if not nct:
                continue
            if nct in seen:
                # Same trial under two diseases: keep one row, record both
                cur.execute("UPDATE trials SET disease = disease || '; ' || ? WHERE nct_id=?",
                            (disease, nct))
                continue
            seen.add(nct)
            cur.execute(f"INSERT INTO trials ({','.join(TRIAL_COLUMNS)}) VALUES ({placeholders})",
                        [row[c] for c in TRIAL_COLUMNS])
            cur.executemany("INSERT INTO locations VALUES (?,?,?,?,?,?,?,?)", loc_rows)
            total_sites += len(loc_rows)
            count += 1
        print(f"{disease:<20} {count:>5} trials")

    cur.execute("CREATE INDEX idx_loc_nct ON locations(nct_id)")
    cur.execute("CREATE INDEX idx_trials_disease ON trials(disease)")
    cur.executemany("INSERT INTO metadata VALUES (?,?)", [
        ("built_at", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("total_trials", str(len(seen))),
        ("total_sites", str(total_sites)),
        ("source", "ClinicalTrials.gov API v2"),
    ])
    conn.commit()
    conn.close()
    print(f"\nDone. {len(seen)} unique trials, {total_sites} trial sites saved to {DB_PATH}")


if __name__ == "__main__":
    build_all()