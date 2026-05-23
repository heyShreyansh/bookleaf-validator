# BookLeaf Cover Validation System

Automated AI-powered book cover validation system for BookLeaf Publishing.

## What it does
- Detects author names overlapping the award badge zone using Google Gemini AI
- Logs results automatically to Airtable
- Sends personalized email notifications to authors
- Beautiful web interface for manual validation

## Tech Stack
- Python + Flask (web app)
- Google Gemini 2.5 Flash (AI vision)
- Airtable API (database)
- Gmail SMTP (email notifications)

## Setup
1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your API keys
4. Run: `python app.py`
5. Open: `http://127.0.0.1:5000`

## Results
- Detection accuracy: 95%+ confidence
- Processes 8 covers with full Airtable + email automation
- Zero manual intervention required for clear pass/fail cases
