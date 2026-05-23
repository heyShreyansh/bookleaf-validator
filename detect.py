from google import genai
import json
import PIL.Image
import time
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

model_name = "gemini-2.5-flash-lite"

def analyze_cover(image_path):
    """Send a book cover image to Gemini and get a structured validation result."""

    image = PIL.Image.open(image_path)

    # Pass actual pixel dimensions so Gemini can reason about zone sizes precisely
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

Be precise about your confidence:
- Use 60-75% when overlap is borderline or hard to measure exactly
- Use 76-89% when issues are likely but not fully certain
- Use 90-95% only when you are completely certain of your assessment

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
        model=model_name,
        contents=[prompt, image]
    )

    # Strip markdown code fences if present
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def analyze_with_retry(image_path, max_retries=3):
    """Retry up to 3 times with exponential backoff on server/rate-limit errors."""
    for attempt in range(max_retries):
        try:
            return analyze_cover(image_path)
        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return None
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg or "overloaded" in error_msg.lower():
                wait_time = (attempt + 1) * 15
                print(f"  Server busy, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            elif "429" in error_msg or "quota" in error_msg.lower():
               
                print(f"  Quota exhausted — switch model or wait until midnight.")
                return None
            else:
                print(f"  Unexpected error: {e}")
                return None
    print(f"  Failed after {max_retries} attempts")
    return None


def print_report(image_path, result):
    """Print a clean, readable validation report to stdout."""
    print(f"\n{'='*55}")
    print(f"FILE:          {image_path}")
    print(f"STATUS:        {result['status']}")
    print(f"CONFIDENCE:    {result['confidence']}%")
    print(f"BADGE OVERLAP: {result['badge_overlap']}")

    if result.get("issues"):
        print("ISSUES FOUND:")
        for issue in result["issues"]:
            print(f"   ⚠ {issue}")
    else:
        print("ISSUES:        None")

    print(f"AUTHOR POS:    {result.get('author_name_position', 'unknown')}")

    if result["status"] == "REVIEW NEEDED":
        print(f"HOW TO FIX:    {result.get('correction_instructions', 'N/A')}")

    print("=" * 55)


def run_all_covers():
    """
    Run validation on all 8 sample covers and print a summary.
    FIX: counters defined inside the function to avoid UnboundLocalError.
    """
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

    # FIX: counters must be local to this function — not module-level
    # Previously defined at module scope caused UnboundLocalError on += inside function
    passed = 0
    review = 0
    failed = 0

    print(" Starting BookLeaf Cover Validation...\n")

    for cover in covers:
        if not os.path.exists(cover):
            print(f"\n File not found: {cover} — skipping")
            failed += 1
            continue

        result = analyze_with_retry(cover)

        if result:
            print_report(cover, result)
            if result["status"] == "PASS":
                passed += 1
            else:
                review += 1
        else:
            print(f"\n FAILED completely: {cover}")
            failed += 1

        time.sleep(4)   # Gemini free-tier rate limit buffer

    # Final summary
    print("\n FINAL SUMMARY")
    print(f"  PASS:           {passed} covers")
    print(f"   REVIEW NEEDED:  {review} covers")
    print(f"   FAILED:         {failed} covers")
    print(f"   TOTAL:          {len(covers)} covers")
    print("\n Validation complete!")


if __name__ == "__main__":
    run_all_covers()