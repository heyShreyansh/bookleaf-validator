import cv2
import numpy as np
from PIL import Image
import os


def load_as_cv(image_path):
    """Load any image format as OpenCV BGR array"""
    pil_img = Image.open(image_path).convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def annotate_cover(image_path, badge_overlap, issues,
                   violations_detail=None,
                   output_dir="static/annotated"):
    """
    Draw visual annotations on the book cover image.

    Draws:
    - Red overlay on badge zone (bottom 9%)
    - Green border for safe text area
    - Orange boxes around detected text regions
    - Red boxes + labels on violating text
    - Status banner at top of front cover

    Returns path to saved annotated image.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load image
    img = load_as_cv(image_path)
    h, w = img.shape[:2]

    # Front cover = right half
    mid = w // 2
    front = img[:, mid:, :]
    fh, fw = front.shape[:2]

    # Zone calculations
    badge_h   = int(fh * 0.09)
    margin_px = int(fh * 0.0375)

    bz_y1 = fh - badge_h   # badge zone top y
    bz_y2 = fh              # badge zone bottom y

    # ── Badge zone red overlay ──
    overlay = img.copy()
    cv2.rectangle(overlay,
        (mid, bz_y1), (mid + fw, bz_y2),
        (0, 0, 200), -1)
    cv2.addWeighted(overlay, 0.38, img, 0.62, 0, img)

    # Badge zone border
    cv2.rectangle(img,
        (mid, bz_y1), (mid + fw - 1, bz_y2 - 1),
        (0, 0, 220), 2)

    # Badge zone label
    cv2.putText(img,
        "BADGE ZONE — RESERVED",
        (mid + 10, bz_y1 + 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
        (255, 255, 255), 1, cv2.LINE_AA)

    # ── Safe area green border ──
    cv2.rectangle(img,
        (mid + margin_px, margin_px),
        (mid + fw - margin_px, bz_y1 - 2),
        (0, 210, 0), 2)

    cv2.putText(img,
        "Safe area",
        (mid + margin_px + 6, margin_px + 18),
        cv2.FONT_HERSHEY_SIMPLEX, 0.42,
        (0, 210, 0), 1, cv2.LINE_AA)

    # ── Draw violation boxes if detail available ──
    if violations_detail:
        for v in violations_detail:
            x1, y1, x2, y2 = v["box"]
            text = v.get("text", "")[:25]
            pct  = v.get("overlap_percent", 0)

            # Red box for violation
            cv2.rectangle(img,
                (mid + x1, y1), (mid + x2, y2),
                (0, 0, 255), 2)

            # Label above box
            label = f"VIOLATION: '{text}' ({pct}% overlap)"
            cv2.putText(img, label,
                (mid + x1, max(y1 - 6, 14)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                (0, 0, 255), 1, cv2.LINE_AA)

            # Arrow pointing to violation
            arrow_y = bz_y1
            cv2.arrowedLine(img,
                (mid + (x1 + x2) // 2, y2 + 4),
                (mid + (x1 + x2) // 2, arrow_y - 4),
                (0, 0, 255), 1, tipLength=0.3)

    # ── Status banner ──
    if badge_overlap:
        banner_color = (30, 30, 200)
        banner_text  = "REVIEW NEEDED — Text overlaps reserved badge zone"
    else:
        banner_color = (0, 155, 0)
        banner_text  = "PASS — All zones clear"

    cv2.rectangle(img, (mid, 0), (mid + fw, 40), banner_color, -1)
    cv2.putText(img, banner_text,
        (mid + 10, 26),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52,
        (255, 255, 255), 1, cv2.LINE_AA)

    # ── Margin violation indicators ──
    if issues:
        for issue in issues:
            if "left edge" in issue.lower():
                cv2.line(img,
                    (mid + margin_px, 40),
                    (mid + margin_px, bz_y1),
                    (0, 165, 255), 2)
            if "right edge" in issue.lower():
                cv2.line(img,
                    (mid + fw - margin_px, 40),
                    (mid + fw - margin_px, bz_y1),
                    (0, 165, 255), 2)

    # ── Legend box at bottom left of front cover ──
    legend_y = bz_y2 - badge_h - 70
    if legend_y > 50:
        cv2.rectangle(img,
            (mid + 8, legend_y),
            (mid + 200, legend_y + 65),
            (30, 30, 30), -1)
        cv2.rectangle(img,
            (mid + 8, legend_y),
            (mid + 200, legend_y + 65),
            (100, 100, 100), 1)

        items = [
            ((0, 0, 220),   "Badge zone (reserved)"),
            ((0, 210, 0),   "Safe text area"),
            ((0, 0, 255),   "Violation detected"),
        ]
        for i, (color, label) in enumerate(items):
            y = legend_y + 16 + i * 18
            cv2.rectangle(img,
                (mid + 14, y - 8),
                (mid + 26, y + 4),
                color, -1)
            cv2.putText(img, label,
                (mid + 32, y + 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                (220, 220, 220), 1, cv2.LINE_AA)

    # ── Save ──
    base = os.path.splitext(os.path.basename(image_path))[0]
    out_path = os.path.join(output_dir, f"{base}_annotated.jpg")
    cv2.imwrite(out_path, img, [cv2.IMWRITE_JPEG_QUALITY, 92])

    print(f"  [Annotate] Saved → {out_path}")
    return out_path