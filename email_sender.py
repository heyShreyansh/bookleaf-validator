import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def send_pass_email(author_name, author_email, file_name, isbn):
    """Send PASS confirmation email to author."""

    subject = f" Your Book Cover is Approved — {isbn}"

    body = f"""Dear {author_name},

Great news! Your book cover has been reviewed and approved.

 File:   {file_name}
 ISBN:   {isbn}
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

    return send_email(author_email, subject, body)


def send_review_email(author_name, author_email, file_name, isbn, issues, how_to_fix):
    """Send REVIEW NEEDED email with specific fix instructions."""

    subject = f" Action Required — Cover Needs Revision — {isbn}"

    body = f"""Dear {author_name},

Thank you for submitting your book cover. Our automated review found issues that need fixing before we can proceed.

 File:    {file_name}
 ISBN:    {isbn}
 Status:  REVISION REQUIRED

ISSUES FOUND:
 {issues}

HOW TO FIX:
➡ {how_to_fix}

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

    return send_email(author_email, subject, body)


def send_email(to_email, subject, body):
    """
    Core SMTP send via Gmail.
    Returns True on success, False on failure.
    Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env
    (Use a Gmail App Password — not your main account password)
    """
    # Guard: skip gracefully if credentials are missing
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("    Gmail credentials not configured — skipping email")
        print("      Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in your .env file")
        return False

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # timeout=30 prevents hanging indefinitely on network issues
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"   Email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("   Email failed: authentication error")
        print("      Check that GMAIL_APP_PASSWORD is a valid Gmail App Password")
        print("      Generate one at: myaccount.google.com/apppasswords")
        return False

    except smtplib.SMTPRecipientsRefused:
        print(f"  Email failed: recipient address rejected — {to_email}")
        return False

    except TimeoutError:
        print("   Email failed: connection to smtp.gmail.com timed out")
        return False

    except Exception as e:
        print(f"  Email failed: {e}")
        return False