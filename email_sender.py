import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")


def _get_greeting():
    hour = datetime.now().hour
    if hour < 12:   return "Good morning"
    elif hour < 17: return "Good afternoon"
    else:           return "Good evening"


def _gemini_write_email(prompt):
    """
    Ask Gemini to write a warm, human email body.
    Falls back to template if Gemini is unavailable.
    """
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[prompt]
        )
        return response.text.strip()
    except Exception as e:
        print(f"  [Email] Gemini unavailable ({e}), using fallback template")
        return None


def send_pass_email(author_name, author_email, file_name, isbn):
    """Send Gemini-written PASS email"""

    first_name = author_name.split()[0]
    greeting   = _get_greeting()

    gemini_prompt = f"""You are a warm, professional editor at BookLeaf Publishing.
Write a short, genuine email to an author whose book cover just passed automated validation.

Author first name: {first_name}
File: {file_name}
ISBN: {isbn}
Time of day greeting: {greeting}

The email should:
- Open with "{greeting} {first_name},"
- Feel warm and human, like a real editor wrote it
- Congratulate them genuinely — not over the top
- Mention their cover passed all checks (badge zone clear, margins good, image quality fine)
- Tell them their book is moving to the next production stage
- Invite them to reach out if they want to make any last changes
- Close with "Warm regards, The BookLeaf Editorial Team"
- Be 150-200 words maximum
- NO subject line in the body
- NO markdown formatting

Write only the email body, nothing else."""

    body = _gemini_write_email(gemini_prompt)

    # Fallback if Gemini fails
    if not body:
        body = f"""{greeting} {first_name},

Great news — your book cover has passed our automated review and everything looks wonderful!

Your cover meets all BookLeaf Publishing standards:
  Award badge zone is completely clear
  Text is within safe margins
  Image quality is print-ready

Your book is now moving to the next stage of production.
If you'd like to make any last-minute changes, now is the time — just reply here.

Warm regards,
The BookLeaf Editorial Team

—
BookLeaf Publishing · info@bookleafpub.com · India | USA | UK"""

    subject = f"Your cover is approved, {first_name}! — ISBN {isbn}"
    return _send(author_email, subject, body)


def send_review_email(author_name, author_email, file_name,
                      isbn, issues, how_to_fix):
    """Send Gemini-written REVIEW NEEDED email"""

    first_name = author_name.split()[0]
    greeting   = _get_greeting()

    # Format issues cleanly for Gemini
    if isinstance(issues, list):
        issues_text = "\n".join(f"- {i}" for i in issues)
    else:
        issues_text = f"- {issues}"

    gemini_prompt = f"""You are a warm, professional editor at BookLeaf Publishing.
Write a short, genuine email to an author whose book cover needs a small revision.

Author first name: {first_name}
File: {file_name}
ISBN: {isbn}
Time of day greeting: {greeting}

Issues detected by our system:
{issues_text}

How to fix it:
{how_to_fix}

The email should:
- Open with "{greeting} {first_name},"
- Feel warm and reassuring — this is a small fix, not a big problem
- Acknowledge the effort they put in
- Clearly explain what the issue is in plain language (no jargon)
- Give the fix instructions in a friendly, step-by-step way
- Mention the bottom 9mm badge zone rule simply and clearly
- Ask them to resubmit within 48 hours
- Offer to help if they are stuck (mention they can reply to the email)
- Close with "Warm regards, The BookLeaf Editorial Team"
- End with a P.S. offering help if they use Canva, Photoshop or InDesign
- Be 200-250 words maximum
- NO subject line in the body
- NO markdown formatting

Write only the email body, nothing else."""

    body = _gemini_write_email(gemini_prompt)

    # Fallback if Gemini fails
    if not body:
        body = f"""{greeting} {first_name},

Thank you for submitting your cover — we can see the care you've put into it.

Our review found one small issue that needs a quick fix:

{issues_text}

How to fix it:
{how_to_fix}

Please remember: the bottom 9mm of your front cover is reserved exclusively
for the award badge. No other text should sit in or touch that zone.

Please resubmit within 48 hours — just reply to this email with your updated file.
If you need any help, we're happy to walk you through it!

Warm regards,
The BookLeaf Editorial Team

—
BookLeaf Publishing · info@bookleafpub.com · India | USA | UK

P.S. Using Canva, Photoshop or InDesign? Just reply and tell us
which tool you're using — we'll send you the exact steps."""

    subject = f"Quick fix needed on your cover, {first_name} — easy to resolve!"
    return _send(author_email, subject, body)


def _send(to_email, subject, body):
    """Core SMTP send"""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  [Email] Gmail credentials missing — skipping")
        return False

    msg = MIMEMultipart()
    msg["From"]     = f"BookLeaf Publishing <{GMAIL_ADDRESS}>"
    msg["To"]       = to_email
    msg["Subject"]  = subject
    msg["Reply-To"] = GMAIL_ADDRESS
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"  [Email] Sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("  [Email] Auth failed — check app password")
        return False
    except Exception as e:
        print(f"  [Email] Failed: {e}")
        return False