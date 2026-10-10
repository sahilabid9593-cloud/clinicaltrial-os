# 🧬 ClinicalTrial OS

**Open-source intelligence platform for clinical trial planning**, built on real public data from ClinicalTrials.gov and the FDA.

🔗 **Live demo:** https://clinicaltrial-os.streamlit.app

| | |
|---|---|
| Trials | 4,785 across 10 disease areas |
| Trial sites | 32,498 (20,000+ facilities in 124 countries) |
| Sources | ClinicalTrials.gov API v2, FDA FAERS (openFDA) |

## Modules

| Module | What it does |
|---|---|
| 🔍 Search Trials | Search by drug, sponsor, condition or NCT ID; full trial detail view (design, eligibility, outcomes, sites map, timeline) |
| 🧠 Protocol Intelligence | Splits eligibility into inclusion/exclusion, scores complexity vs. peer trials, flags restrictive criteria; optional AI feasibility read |
| 🕸️ Knowledge Graph | Sponsor → trial → disease → phase network |
| 📄 Generate Report | Downloadable PDF trial report |
| 📈 Recruitment Prediction | Timeline and enrollment-rate benchmarks from similar **completed** trials |
| 📍 Site Selection | Ranks real sites by experience, completion rate and current activity, on a world map |
| 📊 Analytics | Landscape trends by disease, phase, country and sponsor type |
| ⚠️ Risk Prediction | Early-stop risk model trained on finished trials, with cross-validated accuracy shown |
| ✅ Compliance Check | 23-point registry quality / transparency check |
| 💊 Pharmacovigilance | FDA FAERS adverse event reports and label warnings |

Every model shows its method and limitations in the app.

## Run locally

```bash
git clone https://github.com/sahilabid9593-cloud/clinicaltrial-os.git
cd clinicaltrial-os
pip install -r requirements.txt
python modules/database.py        # rebuild the database from data/ (optional)
streamlit run app/main.py
```

### Optional: AI features
AI summaries use [Groq](https://console.groq.com) (free tier) or a local [Ollama](https://ollama.com) model.
Everything else works without AI. To enable Groq, add to `.streamlit/secrets.toml` or `.env`:

```toml
GROQ_API_KEY = "your-key"
```

## Tech stack
Python · Streamlit · SQLite · pandas · scikit-learn · NetworkX · Plotly · ReportLab

## Disclaimer
For research and educational use only. Not medical, regulatory or legal advice.
Registry data may be incomplete or out of date; always verify against the official record.

## License
MIT. Contributions and issues welcome.
