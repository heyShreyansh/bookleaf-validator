import requests
from datetime import datetime
from dotenv import load_dotenv
import os
import time

load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID        = os.getenv("BASE_ID")
TABLE_ID       = os.getenv("TABLE_ID")

# Base URL reused across all functions
def _base_url():
    return f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"

def _headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type":  "application/json"
    }

def _check_credentials():
    """Return True if all Airtable env vars are set."""
    if not all([AIRTABLE_TOKEN, BASE_ID, TABLE_ID]):
        print("    Airtable credentials not fully configured — skipping")
        print("      Set AIRTABLE_TOKEN, BASE_ID, TABLE_ID in your .env file")
        return False
    return True


def create_record(isbn, file_name, status, confidence,
                  badge_overlap, issues, how_to_fix, author_name, email):
    """
    Create a new validation record in Airtable.
    Returns the record ID string on success, None on failure.

    FIX: Airtable returns 200 on create (not 201).
    Added: credential guard, request timeout, 429 rate-limit retry,
           detailed error logging, returns record ID instead of full response blob.
    """
    if not _check_credentials():
        return None

    data = {
        "fields": {
            "ISBN":          isbn,
            "File Name":     file_name,
            "Status":        status,
            "Confidence":    confidence,
            "Badge Overlap": badge_overlap,
            "Issues":        issues,
            "How To Fix":    how_to_fix,
            "Timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Author Name":   author_name,
            "Email":         email,
        }
    }

    for attempt in range(3):
        try:
            response = requests.post(
                _base_url(),
                headers=_headers(),
                json=data,
                timeout=15
            )

            # Airtable returns 200 on successful record creation
            if response.status_code in (200, 201):
                record_id = response.json().get("id", "")
                print(f"   Airtable record created: {record_id} ({file_name})")
                return record_id

            # Rate limited — wait and retry
            elif response.status_code == 429:
                wait = (attempt + 1) * 30
                print(f"    Airtable rate limited, retrying in {wait}s...")
                time.sleep(wait)

            # Auth failure — no point retrying
            elif response.status_code == 401:
                print("   Airtable auth failed — check AIRTABLE_TOKEN in .env")
                return None

            # Bad request — log full response for debugging
            elif response.status_code == 422:
                print(f"   Airtable rejected record (422) — field mismatch?")
                print(f"      Response: {response.text}")
                return None

            else:
                print(f"   Airtable error ({response.status_code}): {response.text}")
                return None

        except requests.exceptions.Timeout:
            print(f"   Airtable request timed out (attempt {attempt + 1}/3)")
        except requests.exceptions.ConnectionError:
            print(f"   Airtable connection error (attempt {attempt + 1}/3)")
        except Exception as e:
            print(f"   Airtable unexpected error: {e}")
            return None

    print("   Airtable failed after 3 attempts")
    return None


def update_record(record_id, fields: dict):
    """
    Update an existing Airtable record by record ID.
    Useful for tracking resubmissions — patch only the changed fields.
    Returns True on success, False on failure.
    """
    if not _check_credentials():
        return False

    if not record_id:
        print("   update_record called with empty record_id")
        return False

    url = f"{_base_url()}/{record_id}"

    try:
        response = requests.patch(
            url,
            headers=_headers(),
            json={"fields": fields},
            timeout=15
        )

        if response.status_code in (200, 201):
            print(f"   Airtable record updated: {record_id}")
            return True
        else:
            print(f"   Airtable update failed ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        print(f"   Airtable update error: {e}")
        return False


def get_record(record_id):
    """
    Fetch a single record by ID.
    Returns the record dict or None on failure.
    """
    if not _check_credentials():
        return None

    url = f"{_base_url()}/{record_id}"

    try:
        response = requests.get(url, headers=_headers(), timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"   Airtable fetch failed ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"   Airtable fetch error: {e}")
        return None