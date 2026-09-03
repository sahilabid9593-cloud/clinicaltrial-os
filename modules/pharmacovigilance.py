import requests
import json

def get_adverse_events(drug_name):
    print(f"\nFetching adverse events for: {drug_name}")
    print("Connecting to FDA FAERS database...")

    url = "https://api.fda.gov/drug/event.json"
    params = {
        "search": f"patient.drug.medicinalproduct:{drug_name}",
        "count": "patient.reaction.reactionmeddrapt.exact",
        "limit": 10
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "results" not in data:
            print("No data found for this drug")
            return None

        results = data["results"]

        print(f"\n--- TOP 10 ADVERSE EVENTS FOR {drug_name.upper()} ---")
        print(f"Source: FDA FAERS Database (Real Data)")
        print(f"{'Adverse Event':<40} {'Reports':>10}")
        print("-" * 52)

        events = []
        for item in results:
            term = item.get("term", "Unknown")
            count = item.get("count", 0)
            print(f"{term:<40} {count:>10,}")
            events.append({"event": term, "count": count})

        return {
            "drug": drug_name,
            "total_events_found": len(events),
            "top_events": events,
            "source": "FDA FAERS Database"
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

def get_drug_labels(drug_name):
    print(f"\nFetching drug label warnings for: {drug_name}")

    url = "https://api.fda.gov/drug/label.json"
    params = {
        "search": f"openfda.brand_name:{drug_name}",
        "limit": 1
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "results" not in data:
            print("No label found")
            return None

        label = data["results"][0]

        warnings = label.get("warnings", ["Not available"])[0][:500]
        boxed = label.get("boxed_warning", ["None"])[0][:300]

        print(f"\n--- DRUG LABEL WARNINGS ---")
        print(f"Boxed Warning: {boxed}")
        print(f"\nWarnings: {warnings}")

        return {
            "drug": drug_name,
            "boxed_warning": boxed,
            "warnings": warnings
        }

    except Exception as e:
        print(f"Error fetching label: {e}")
        return None

if __name__ == "__main__":
    get_adverse_events("metformin")
    print("\n" + "="*52)
    get_adverse_events("insulin")