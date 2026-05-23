from google import genai
import json
import PIL.Image
import time
import requests
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import io

# ============================================
# CONFIGURATION
# ============================================

from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")
AIRTABLE_TOKEN    = os.getenv("AIRTABLE_TOKEN")
BASE_ID           = os.getenv("BASE_ID")
TABLE_ID          = os.getenv("TABLE_ID")
GMAIL_ADDRESS     = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Optional: Google Drive folder ID to poll for new covers
DRIVE_FOLDER_ID   = os.getenv("DRIVE_FOLDER_ID", "")

# ============================================
# ISBN → AUTHOR DATABASE
# FIX: removed duplicate key 9789373147765
# ============================================

AUTHORS = {
    "9789373145068": {"name": "Ojal Jain",       "email": "shreyansh412t@gmail.com"},
    "9789373147765": {"name": "Pratik Kolekar",  "email": "shreyansh412t@gmail.com"},
    "9789373147994": {"name": "Benny James SDB", "email": "shreyansh412t@gmail.com"},
    "9789898652364": {"name": "Benny James SDB", "email": "shreyansh412t@gmail.com"},
    "9789898652753": {"name": "Pulak Das",        "email": "shreyansh412t@gmail.com"},
    "9789898652616": {"name": "Parisha Shodhan", "email": "shreyansh412t@gmail.com"},
    "9789373147499": {"name": "Parisha Shodhan", "email": "shreyansh412t@gmail.com"},
}

# Cover files mapped to ISBNs
# FIX: cover3.png was incorrectly mapped to 9789373147765 (Pratik Kolekar / Inner Mirror)
# cover3.png is the second version of Shabd (Parisha Shodhan) — corrected to 9789373147499
COVER_ISBN_MAP = {
    "cover1.png": "9789898652616",   # Shabd v1      — Parisha Shodhan
    "cover2.png": "9789373147765",   # Inner Mirror  — Pratik Kolekar
    "cover3.png": "9789373147499",   # Shabd v2      — Parisha Shodhan  ← FIXED
    "cover4.png": "9789898652364",   # Echoes v1     — Benny James SDB
    "cover5.png": "9789373147994",   # Echoes v2     — Benny James SDB
    "cover6.png": "9789898652753",   # Offline Sorrows — Pulak Das
    "cover7.png": "9789373147499",   # Shabd v3      — Parisha Shodhan
    "cover8.png": "9789373145068",   # Tainted By Emotion — Ojal Jain
}

# ============================================
# STEP 1 — AI DETECTION
# ============================================

client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_cover(image_path_or_bytes):
    """
    Accepts either a file path string or raw bytes (for Drive-fetched images).
    Returns parsed JSON result dict.
    """
    if isinstance(image_path_or_bytes, bytes):
        image = PIL.Image.open(io.BytesIO(image_path_or_bytes))
    else:
        image = PIL.Image.open(image_path_or_bytes)

    # Get image dimensions for accurate zone calculation
    width, height = image.size
    badge_zone_px = int(height * 0.09)

    prompt = f"""You are a strict book cover validator for BookLeaf Publishing.

This image shows BOTH front and back cover side by side.
Focus ONLY on the RIGHT HALF — that is the front cover.

IMAGE DIMENSIONS: {width}x{height}px (full spread). Front cover is the right half.
BADGE ZONE: The bottom {badge_zone_px}px of the front cover height is RESERVED exclusively
for the "Winner of the 21st Century Emily Dickinson Award" badge.
NO other text may overlap or even touch this zone.

Carefully check ALL of the following:
1. BADGE OVERLAP (critical): Does any text — author name, tagline, subtitle, or any 
   other element — overlap or sit inside the bottom badge zone? Even partial overlap counts.
2. MARGIN VIOLATIONS: Is any text closer than 3mm to the left or right edge?
3. IMAGE QUALITY: Is the cover sharp and print-ready, or blurry/pixelated?
4. TEXT READABILITY: Is all text clearly legible at print resolution?

Be precise about your confidence. Use lower confidence (60-80%) when overlap is borderline
or hard to measure exactly. Use high confidence (90-95%) only when you are certain.

Respond ONLY in this exact JSON format with no extra text or markdown:
{{
  "status": "PASS or REVIEW NEEDED",
  "confidence": <integer 60-95>,
  "badge_overlap": <true or false>,
  "issues": ["describe each specific problem found, or empty list if none"],
  "author_name_position": "top / middle / bottom / overlapping badge",
  "correction_instructions": "specific actionable steps to fix, or No action needed"
}}"""

    response = client.models.generate_content(
        model_name = "gemini-2.5-flash-lite",
        contents=[prompt, image]
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def analyze_with_retry(image_path_or_bytes, max_retries=3):
    """Retry up to 3 times on 503 server errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return analyze_cover(image_path_or_bytes)
        except json.JSONDecodeError as e:
            print(f"  JSON parse error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return None
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg or "overloaded" in error_msg.lower():
                wait = (attempt + 1) * 15
                print(f"  Server busy, retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            elif "429" in error_msg or "quota" in error_msg.lower():
                wait = 60
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Unexpected error: {e}")
                return None
    print(f"  Failed after {max_retries} attempts")
    return None


# ============================================
# STEP 2 — AIRTABLE RECORD
# ============================================

def create_airtable_record(isbn, file_name, status, confidence,
                            badge_overlap, issues, how_to_fix,
                            author_name, email):
    """Create a validation record in Airtable. Returns record ID or None on failure."""
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            "ISBN":         isbn,
            "File Name":    file_name,
            "Status":       status,
            "Confidence":   confidence,
            "Badge Overlap": badge_overlap,
            "Issues":       issues,
            "How To Fix":   how_to_fix,
            "Timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Author Name":  author_name,
            "Email":        email,
        }
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code in (200, 201):
            record_id = response.json().get("id", "")
            print(f"  Airtable record created: {record_id}")
            return record_id
        else:
            print(f"   Airtable failed ({response.status_code}): {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"   Airtable request error: {e}")
        return None


# ============================================
# STEP 3 — EMAIL
# ============================================

def send_email(to_email, subject, body):
    """Core SMTP send. Returns True on success, False on failure."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("    Gmail credentials not configured — skipping email")
        return False
    msg = MIMEMultipart()
    msg['From']    = GMAIL_ADDRESS
    msg['To']      = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"   Email sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("   Email failed: authentication error — check GMAIL_APP_PASSWORD")
        return False
    except Exception as e:
        print(f"   Email failed: {e}")
        return False


def send_pass_email(author_name, author_email, file_name, isbn):
    subject = f" Your Book Cover is Approved — {isbn}"
    body = f"""Dear {author_name},

Great news! Your book cover has been reviewed and approved.

 File: {file_name}
 ISBN: {isbn}
 Status: APPROVED

Your cover meets all BookLeaf Publishing standards:
   Award badge zone is clear
   Text within safe margins
   Image quality is good

Your book is now moving to the next stage of production.

Warm regards,
BookLeaf Publishing Team
info@bookleafpub.com
India | USA | UK"""
    send_email(author_email, subject, body)


def send_review_email(author_name, author_email, file_name, isbn, issues, how_to_fix):
    subject = f" Action Required — Cover Needs Revision — {isbn}"
    body = f"""Dear {author_name},

Thank you for submitting your book cover. Our automated review found issues that need fixing before we can proceed.

 File: {file_name}
 ISBN: {isbn}
 Status: REVISION REQUIRED

ISSUES FOUND:
 {issues}

HOW TO FIX:
 {how_to_fix}

IMPORTANT RULES:
  - Bottom 9mm of front cover is reserved for the award badge only
  - No text should overlap or touch the badge zone
  - Maintain 3mm margins on all sides

Please fix and resubmit within 48 hours.
Reply to this email if you need help.

Warm regards,
BookLeaf Publishing Team
info@bookleafpub.com
India | USA | UK"""
    send_email(author_email, subject, body)


# ============================================
# GOOGLE DRIVE POLLING (optional)
# ============================================

def get_drive_service():
    """
    Returns an authenticated Google Drive service object.
    Requires: google-api-python-client, google-auth-httplib2, google-auth-oauthlib
    Credentials file: service_account.json in working directory.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            "service_account.json",
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds)
    except ImportError:
        print("    google-api-python-client not installed — Drive polling unavailable")
        return None
    except FileNotFoundError:
        print("    service_account.json not found — Drive polling unavailable")
        return None


def fetch_new_drive_covers(service, folder_id, processed_ids: set):
    """
    Lists PNG/PDF files in the Drive folder not yet in processed_ids.
    Returns list of (file_id, file_name, isbn) tuples.
    """
    query = (
        f"'{folder_id}' in parents "
        f"and (mimeType='image/png' or mimeType='application/pdf') "
        f"and trashed=false"
    )
    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    new_files = []
    for f in results.get("files", []):
        if f["id"] not in processed_ids:
            # Extract ISBN from filename: e.g. "9789373145068_text.png" → "9789373145068"
            isbn = f["name"].split("_")[0]
            new_files.append((f["id"], f["name"], isbn))
    return new_files


def download_drive_file(service, file_id) -> bytes:
    """Download a file from Drive and return its raw bytes."""
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def poll_drive_and_process(poll_interval_seconds=60):
    """
    Continuously polls the Drive folder for new covers and runs the full pipeline.
    Set DRIVE_FOLDER_ID in your .env to enable.
    Runs indefinitely — use Ctrl+C or a process manager to stop.
    """
    if not DRIVE_FOLDER_ID:
        print("DRIVE_FOLDER_ID not set in .env — skipping Drive polling")
        return

    service = get_drive_service()
    if not service:
        return

    processed_ids = set()
    print(f" Polling Drive folder: {DRIVE_FOLDER_ID}")
    print(f"   Checking every {poll_interval_seconds}s. Press Ctrl+C to stop.\n")

    while True:
        try:
            new_files = fetch_new_drive_covers(service, DRIVE_FOLDER_ID, processed_ids)
            if new_files:
                print(f"  Found {len(new_files)} new cover(s) in Drive")
                for file_id, file_name, isbn in new_files:
                    print(f"\n  Processing from Drive: {file_name}")
                    image_bytes = download_drive_file(service, file_id)
                    _process_single_cover(
                        image_source=image_bytes,
                        file_name=file_name,
                        isbn=isbn
                    )
                    processed_ids.add(file_id)
                    time.sleep(4)   # Gemini rate limit buffer
            else:
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] No new covers found")

            time.sleep(poll_interval_seconds)

        except KeyboardInterrupt:
            print("\n  Drive polling stopped.")
            break
        except Exception as e:
            print(f"  Drive poll error: {e}")
            time.sleep(30)


# ============================================
# SHARED SINGLE-COVER PROCESSOR
# ============================================

def _process_single_cover(image_source, file_name, isbn):
    """
    Shared logic for processing one cover — used by both batch pipeline
    and Drive polling. image_source can be a file path or bytes.
    Returns (status, passed_flag) tuple.
    """
    author_info = AUTHORS.get(isbn, {"name": "Unknown Author", "email": ""})
    author_name  = author_info["name"]
    author_email = author_info["email"]

    if not author_email:
        print(f"    No email found for ISBN {isbn}")

    # Step 1 — AI detection
    result = analyze_with_retry(image_source)

    if not result:
        print(f"   Detection failed for {file_name}")
        return "FAILED", False

    status       = result["status"]
    confidence   = result["confidence"]
    badge_overlap = result["badge_overlap"]
    issues       = " | ".join(result["issues"]) if result["issues"] else "None"
    how_to_fix   = result.get("correction_instructions", "No action needed")

    print(f"  Status: {status} ({confidence}% confidence)")
    if result["issues"]:
        for issue in result["issues"]:
            print(f"   {issue}")

    # Step 2 — Airtable
    create_airtable_record(
        isbn, file_name, status, confidence,
        badge_overlap, issues, how_to_fix,
        author_name, author_email
    )

    # Step 3 — Email
    if author_email:
        if status == "PASS":
            send_pass_email(author_name, author_email, file_name, isbn)
        else:
            send_review_email(author_name, author_email, file_name, isbn, issues, how_to_fix)

    return status, (status == "PASS")


# ============================================
# MAIN BATCH PIPELINE
# ============================================

def run_pipeline():
    """Run validation on all 8 local cover files."""
    covers = [
        "cover1.png",
        "cover2.png",
        "cover3.png",
        "cover4.png",
        "cover5.png",
        "cover6.png",
        "cover7.png",
        "cover8.png",
    ]

    passed = 0
    review = 0
    failed = 0

    print(" BookLeaf Automated Cover Validation Pipeline")
    print("=" * 50)

    for cover in covers:
        isbn = COVER_ISBN_MAP.get(cover, "UNKNOWN")
        print(f"\n Processing: {cover}  (ISBN: {isbn})")

        if not os.path.exists(cover):
            print(f"   File not found: {cover} — skipping")
            failed += 1
            continue

        status, ok = _process_single_cover(
            image_source=cover,
            file_name=cover,
            isbn=isbn
        )

        if status == "FAILED":
            failed += 1
        elif ok:
            passed += 1
        else:
            review += 1

        time.sleep(4)   # Gemini free-tier rate limit buffer

    # Final summary
    print(" FINAL SUMMARY")
    print(f"   PASS:           {passed} covers")
    print(f"   REVIEW NEEDED:  {review} covers")
    print(f"   FAILED:         {failed} covers")
    print(f"   TOTAL:          {len(covers)} covers")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--drive":
        # Run in Drive polling mode: python pipeline.py --drive
        poll_drive_and_process(poll_interval_seconds=60)
    else:
        # Default: run local batch pipeline
        run_pipeline()