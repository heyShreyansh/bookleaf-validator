from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename
import os
import time
from dotenv import load_dotenv

load_dotenv()

# ============================================
# FLAT IMPORTS — no package install required
# All modules live in the same directory as app.py
# Previously: from bookleaf_validator.detect import ...
# That required an installed package with __init__.py — broke on plain `python app.py`
# ============================================
from detect import analyze_with_retry
from email_sender import send_pass_email, send_review_email
from airtable_connect import create_record
from pipeline import AUTHORS, COVER_ISBN_MAP

# ============================================
# APP SETUP
# ============================================

app = Flask(__name__)

BASE_DIR       = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER  = os.path.join(BASE_DIR, "uploads")
MAX_MB         = 20                                     # reject uploads over 20 MB
ALLOWED_EXT    = {"png", "jpg", "jpeg", "pdf"}

app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    """Return True only for permitted image/PDF extensions."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ============================================
# ROUTES
# ============================================

@app.route("/", methods=["GET"])
def index():
    sample_covers = sorted(COVER_ISBN_MAP.keys())
    return render_template("index.html", sample_covers=sample_covers)


@app.route("/validate", methods=["POST"])
def validate():
    cover_choice    = request.form.get("cover_choice", "").strip()
    cover_upload    = request.files.get("cover_upload")
    create_airtable = request.form.get("create_airtable") == "on"
    send_email_flag = request.form.get("send_email") == "on"

    # ---- Determine cover source ----
    if cover_upload and cover_upload.filename:
        filename = secure_filename(cover_upload.filename)

        if not allowed_file(filename):
            return render_template(
                "result.html",
                error=f"Invalid file type '{filename}'. Allowed: PNG, JPG, PDF."
            )

        timestamp   = int(time.time())
        saved_path  = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        cover_upload.save(saved_path)

        selected_cover = filename
        cover_path     = saved_path
        isbn           = request.form.get("custom_isbn", "").strip() or "UNKNOWN"
        author_name    = request.form.get("custom_author_name", "").strip() or "Unknown Author"
        author_email   = request.form.get("custom_author_email", "").strip()

    elif cover_choice:
        if cover_choice not in COVER_ISBN_MAP:
            return render_template(
                "result.html",
                error=f"Unknown sample cover: '{cover_choice}'"
            )

        selected_cover = cover_choice
        cover_path     = os.path.join(BASE_DIR, cover_choice)
        isbn           = COVER_ISBN_MAP[cover_choice]
        author         = AUTHORS.get(isbn, {"name": "Unknown Author", "email": ""})
        author_name    = author["name"]
        author_email   = author["email"]

    else:
        return render_template(
            "result.html",
            error="Please choose a sample cover or upload an image."
        )

    # ---- Verify file exists on disk ----
    if not os.path.exists(cover_path):
        return render_template(
            "result.html",
            error=f"Cover file not found on server: {cover_path}"
        )

    # ---- Step 1: AI detection ----
    result = analyze_with_retry(cover_path)
    if not result:
        return render_template(
            "result.html",
            error="Cover validation failed — Gemini API returned no result. Check server logs."
        )

    status        = result.get("status", "UNKNOWN")
    confidence    = result.get("confidence", 0)
    badge_overlap = result.get("badge_overlap", False)
    issues        = result.get("issues", [])
    correction    = result.get("correction_instructions", "No instructions provided.")
    
    # Map status to CSS theme
    theme = "pass" if status == "PASS" else ("review" if status == "REVIEW NEEDED" else "fail")

    # ---- Step 2: Airtable ----
    airtable_status = None
    if create_airtable:
        try:
            record = create_record(
                isbn        = isbn,
                file_name   = selected_cover,
                status      = status,
                confidence  = confidence,
                badge_overlap = badge_overlap,
                issues      = " | ".join(issues) if issues else "None",
                how_to_fix  = correction,
                author_name = author_name,
                email       = author_email,
            )
            airtable_status = "Created" if record else "Failed"
        except Exception as exc:
            airtable_status = f"Error: {exc}"

    # ---- Step 3: Email ----
    email_status = None
    if send_email_flag:
        if not author_email:
            email_status = "Skipped — author email is missing."
        else:
            try:
                if status == "PASS":
                    send_pass_email(author_name, author_email, selected_cover, isbn)
                else:
                    send_review_email(
                        author_name, author_email, selected_cover, isbn,
                        " | ".join(issues) if issues else "None",
                        correction
                    )
                email_status = "Sent"
            except Exception as exc:
                email_status = f"Error: {exc}"

    return render_template(
        "result.html",
        filename      = selected_cover,
        status        = status,
        theme         = theme,
        confidence    = confidence,
        badge_overlap = badge_overlap,
        issues        = issues,
        correction    = correction,
        isbn          = isbn,
        author_name   = author_name,
        author_email  = author_email,
        airtable_status = airtable_status,
        email_status    = email_status,
        result          = result,
    )


# ---- Global error handlers ----

@app.errorhandler(413)
def file_too_large(e):
    return render_template(
        "result.html",
        error=f"File too large. Maximum upload size is {MAX_MB} MB."
    ), 413

@app.errorhandler(500)
def internal_error(e):
    return render_template(
        "result.html",
        error="Internal server error. Check the server log for details."
    ), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)