# BookLeaf Cover Validation System

Automated AI-powered book cover validation system for BookLeaf Publishing.

## What it does
- Detects author names overlapping the award badge zone using Google Gemini AI
- Logs results automatically to Airtable
- Sends personalized email notifications to authors
- Beautiful web interface for manual validation

## Tech Stack
- Python + Flask (web app)
<img width="1353" height="801" alt="Screenshot 2026-05-24 at 13 51 23" src="https://github.com/user-attachments/assets/0bcb95e6-66df-4268-8c9f-4faaa3f9a8f2" />

- Google Gemini 2.5 Flash (AI vision)
<img width="1669" height="927" alt="Screenshot 2026-05-24 at 13 52 38" src="https://github.com/user-attachments/assets/77f4c066-cd41-472f-a7ff-dee329e4aa9f" />


- Airtable API (database)
<img width="1471" height="469" alt="Screenshot 2026-05-24 at 13 48 21" src="https://github.com/user-attachments/assets/0308ae95-b9a7-48dc-bd29-e69cc47ffa31" />

- Gmail SMTP (email notifications)
<img width="1161" height="575" alt="Screenshot 2026-05-24 at 13 47 27" src="https://github.com/user-attachments/assets/5b2ed580-1e10-475b-9601-36a6e55ddb35" />



## Setup
1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your API keys
4. Run: `python app.py`
5. Open: `http://127.0.0.1:5000`

#Interface
<img width="549" height="689" alt="Screenshot 2026-05-24 at 13 47 43" src="https://github.com/user-attachments/assets/74c9c831-3b87-4222-9c75-a0f68ca47b34" />

## Results
- Detection accuracy: 95%+ confidence
- Processes 8 covers with full Airtable + email automation
- Zero manual intervention required for clear pass/fail cases
- Pass
<img width="554" height="562" alt="Screenshot 2026-05-24 at 13 48 09" src="https://github.com/user-attachments/assets/f4a43439-edae-4174-ba92-350c2b453b48" />
- Review Needed 
<img width="578" height="735" alt="Screenshot 2026-05-24 at 13 47 37" src="https://github.com/user-attachments/assets/91fb89f9-4b14-4d57-92d6-d2b67ec59aae" />





