import requests
import json
import os

def fetch_trials(disease="diabetes", max_results=200):
    print(f"Fetching {max_results} trials for: {disease}")
    
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": disease,
        "pageSize": max_results,
        "format": "json"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    os.makedirs("data", exist_ok=True)
    filename = f"data/{disease}_trials.json"
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    
    total = len(data.get("studies", []))
    print(f"Done. Saved {total} trials to {filename}")
    return data

if __name__ == "__main__":
    fetch_trials("diabetes")