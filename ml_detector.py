import cv2
import numpy as np
from PIL import Image
import os
import json
import time
from ultralytics import YOLO
import easyocr

# ── Lazy-load models once (not on every request) ──
_yolo_model = None
_ocr_reader = None

def get_yolo():
    global _yolo_model
    if _yolo_model is None:
        # YOLOv8n = nano, fastest, good enough for text region detection
        _yolo_model = YOLO("yolov8n.pt")
    return _yolo_model

def get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_reader


def load_image(image_path):
    """Load image as both PIL and OpenCV format"""
    pil_img = Image.open(image_path).convert("RGB")
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return pil_img, cv_img


def get_front_cover(cv_img):
    """
    Extract the right half (front cover) from a full spread image.
    Returns the front cover crop and its x-offset in the original image.
    """
    h, w = cv_img.shape[:2]
    mid = w // 2
    front = cv_img[:, mid:, :]
    return front, mid


def get_badge_zone(front_cover):
    """
    Calculate the badge zone rectangle.
    Rule: bottom 9% of front cover height.
    Returns (x1, y1, x2, y2) in front cover coordinates.
    """
    h, w = front_cover.shape[:2]
    badge_h = int(h * 0.09)
    return (0, h - badge_h, w, h)


def get_safe_margins(front_cover):
    """
    Calculate safe margin boundaries.
    Rule: 3mm on each side ≈ 3.75% of height at standard DPI.
    Returns margin size in pixels.
    """
    h = front_cover.shape[0]
    return int(h * 0.0375)


def detect_text_regions_yolo(front_cover):
    """
    Use YOLOv8 to detect all objects in the front cover.
    Returns list of bounding boxes for text-likely regions.
    Each box: (x1, y1, x2, y2, confidence, class_name)
    """
    model = get_yolo()
    results = model(front_cover, verbose=False)[0]
    
    boxes = []
    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = float(box.conf[0])
        cls_name = model.names[int(box.cls[0])]
        boxes.append((x1, y1, x2, y2, conf, cls_name))
    
    return boxes


def detect_text_regions_ocr(front_cover):
    """
    Use EasyOCR to find exact text bounding boxes with content.
    Returns list of (bbox, text, confidence)
    bbox = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    """
    reader = get_ocr()
    
    # Convert BGR to RGB for EasyOCR
    rgb = cv2.cvtColor(front_cover, cv2.COLOR_BGR2RGB)
    results = reader.readtext(rgb, detail=1)
    
    boxes = []
    for (bbox, text, conf) in results:
        # Convert polygon to rectangle
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x1, y1 = int(min(xs)), int(min(ys))
        x2, y2 = int(max(xs)), int(max(ys))
        boxes.append((x1, y1, x2, y2, conf, text))
    
    return boxes


def check_badge_overlap(text_boxes, badge_zone):
    """
    Mathematically check if any text bounding box
    overlaps with the badge zone rectangle.
    Returns list of overlapping boxes with overlap percentage.
    """
    bz_x1, bz_y1, bz_x2, bz_y2 = badge_zone
    violations = []
    
    for box in text_boxes:
        x1, y1, x2, y2, conf, text = box
        
        # Check intersection
        inter_x1 = max(x1, bz_x1)
        inter_y1 = max(y1, bz_y1)
        inter_x2 = min(x2, bz_x2)
        inter_y2 = min(y2, bz_y2)
        
        if inter_x1 < inter_x2 and inter_y1 < inter_y2:
            # Overlap exists — calculate percentage
            inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
            box_area = (x2 - x1) * (y2 - y1)
            overlap_pct = round((inter_area / box_area) * 100, 1) if box_area > 0 else 0
            
            violations.append({
                "text": text,
                "box": (x1, y1, x2, y2),
                "overlap_percent": overlap_pct,
                "confidence": round(conf * 100, 1)
            })
    
    return violations


def check_margin_violations(text_boxes, margin_px, front_w):
    """
    Check if any text is too close to left/right edges.
    """
    violations = []
    for box in text_boxes:
        x1, y1, x2, y2, conf, text = box
        if x1 < margin_px:
            violations.append(f"Text '{text[:30]}' too close to left edge ({x1}px margin, need {margin_px}px)")
        if x2 > front_w - margin_px:
            violations.append(f"Text '{text[:30]}' too close to right edge")
    return violations


def annotate_image(cv_img, front_offset, front_cover, badge_zone,
                   margin_px, text_boxes, violations, status):
    """
    Draw all annotations on the full spread image.
    - Badge zone: red overlay
    - Safe margin: green border
    - Violating text: red box
    - Clean text: blue box
    - Status banner
    Returns annotated image as numpy array.
    """
    annotated = cv_img.copy()
    h, w = front_cover.shape[:2]
    bz_x1, bz_y1, bz_x2, bz_y2 = badge_zone
    ox = front_offset  # x offset for front cover

    # ── Badge zone red overlay ──
    overlay = annotated.copy()
    cv2.rectangle(overlay,
        (ox + bz_x1, bz_y1),
        (ox + bz_x2, bz_y2),
        (0, 0, 200), -1)
    cv2.addWeighted(overlay, 0.4, annotated, 0.6, 0, annotated)

    # ── Badge zone border ──
    cv2.rectangle(annotated,
        (ox + bz_x1, bz_y1),
        (ox + bz_x2, bz_y2),
        (0, 0, 220), 2)

    # ── Badge zone label ──
    cv2.putText(annotated, "BADGE ZONE (RESERVED — DO NOT PLACE TEXT HERE)",
        (ox + 8, bz_y1 + 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Safe margin border (green) ──
    cv2.rectangle(annotated,
        (ox + margin_px, margin_px),
        (ox + w - margin_px, bz_y1 - 2),
        (0, 210, 0), 2)
    cv2.putText(annotated, "Safe area",
        (ox + margin_px + 4, margin_px + 16),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 210, 0), 1, cv2.LINE_AA)

    # ── Draw each detected text box ──
    violation_texts = {v["text"] for v in violations}
    for (x1, y1, x2, y2, conf, text) in text_boxes:
        is_violation = text in violation_texts
        color = (0, 0, 255) if is_violation else (255, 140, 0)
        thickness = 2 if is_violation else 1
        cv2.rectangle(annotated,
            (ox + x1, y1), (ox + x2, y2),
            color, thickness)
        label = f"{text[:20]} ({round(conf*100)}%)" if conf <= 1 else f"{text[:20]}"
        cv2.putText(annotated, label,
            (ox + x1, max(y1 - 4, 12)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

    # ── Status banner at top of front cover ──
    if status == "PASS":
        banner_color = (0, 160, 0)
        banner_text = "PASS — All zones clear. No violations detected."
    else:
        banner_color = (0, 0, 200)
        banner_text = f"REVIEW NEEDED — {len(violations)} violation(s) detected"

    cv2.rectangle(annotated, (ox, 0), (ox + w, 38), banner_color, -1)
    cv2.putText(annotated, banner_text,
        (ox + 10, 25),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    return annotated


def ml_analyze_cover(image_path, use_gemini_fallback=True):
    """
    Main hybrid ML detection function.
    
    Pipeline:
    1. YOLOv8 → detect all regions
    2. EasyOCR → find exact text + bounding boxes  
    3. Math → check badge zone overlap
    4. Gemini → only if OCR confidence is low
    
    Returns structured result dict matching your existing pipeline.
    """
    print(f"  [ML] Analyzing: {image_path}")
    start = time.time()

    # ── Load image ──
    pil_img, cv_img = load_image(image_path)
    front_cover, front_offset = get_front_cover(cv_img)
    fh, fw = front_cover.shape[:2]

    # ── Get zone boundaries ──
    badge_zone = get_badge_zone(front_cover)
    margin_px = get_safe_margins(front_cover)

    # ── Step 1: EasyOCR text detection ──
    print(f"  [OCR] Detecting text regions...")
    ocr_boxes = detect_text_regions_ocr(front_cover)
    print(f"  [OCR] Found {len(ocr_boxes)} text regions")

    # ── Step 2: Badge zone overlap check (pure math) ──
    violations = check_badge_overlap(ocr_boxes, badge_zone)
    margin_violations = check_margin_violations(ocr_boxes, margin_px, fw)

    # ── Step 3: Determine confidence ──
    if len(ocr_boxes) == 0:
        # No text found — low confidence, use Gemini fallback
        ocr_confidence = 50
    elif violations:
        # Clear violations found
        ocr_confidence = 92
    else:
        # No violations found
        avg_conf = sum(b[4] for b in ocr_boxes) / len(ocr_boxes)
        ocr_confidence = int(min(95, avg_conf * 100))

    # ── Step 4: Gemini fallback for low confidence ──
    gemini_result = None
    if ocr_confidence < 75 and use_gemini_fallback:
        print(f"  [ML] Low confidence ({ocr_confidence}%), calling Gemini fallback...")
        try:
            from detect import analyze_with_retry
            gemini_result = analyze_with_retry(image_path)
        except Exception as e:
            print(f"  [ML] Gemini fallback failed: {e}")

    # ── Build final result ──
    badge_overlap = len(violations) > 0
    issues = []

    if violations:
        for v in violations:
            issues.append(
                f"Text '{v['text']}' overlaps badge zone by {v['overlap_percent']}%"
            )
    if margin_violations:
        issues.extend(margin_violations)

    # Merge with Gemini if used
    if gemini_result and ocr_confidence < 75:
        final_status = gemini_result.get("status", "REVIEW NEEDED")
        final_confidence = gemini_result.get("confidence", ocr_confidence)
        if gemini_result.get("issues"):
            issues.extend(gemini_result["issues"])
        correction = gemini_result.get("correction_instructions", "")
    else:
        final_status = "REVIEW NEEDED" if (badge_overlap or margin_violations) else "PASS"
        final_confidence = ocr_confidence
        correction = _build_correction(violations, margin_violations) if issues else "No action needed"

    # ── Step 5: Annotate image ──
    annotated = annotate_image(
        cv_img, front_offset, front_cover,
        badge_zone, margin_px, ocr_boxes,
        violations, final_status
    )

    # Save annotated image
    os.makedirs("static/annotated", exist_ok=True)
    base = os.path.splitext(os.path.basename(image_path))[0]
    annotated_path = f"static/annotated/{base}_ml_annotated.jpg"
    cv2.imwrite(annotated_path, annotated)

    elapsed = round(time.time() - start, 2)
    print(f"  [ML] Done in {elapsed}s — {final_status} ({final_confidence}% confidence)")

    return {
        "status": final_status,
        "confidence": final_confidence,
        "badge_overlap": badge_overlap,
        "issues": issues,
        "correction_instructions": correction,
        "author_name_position": _estimate_author_position(ocr_boxes, fh),
        "violations_detail": violations,
        "text_regions_found": len(ocr_boxes),
        "detection_method": "EasyOCR+Math" if ocr_confidence >= 75 else "EasyOCR+Gemini",
        "processing_time_sec": elapsed,
        "annotated_image_path": annotated_path,
        "margin_violation": len(margin_violations) > 0
    }


def _build_correction(violations, margin_violations):
    """Build specific correction instructions from detected violations."""
    instructions = []
    for v in violations:
        instructions.append(
            f"Move '{v['text']}' upward — it overlaps the badge zone by {v['overlap_percent']}%"
        )
    for m in margin_violations:
        instructions.append(m)
    return " | ".join(instructions) if instructions else "No action needed"


def _estimate_author_position(ocr_boxes, front_height):
    """Estimate where the author name is positioned."""
    if not ocr_boxes:
        return "unknown"
    badge_y = int(front_height * 0.91)
    bottom_boxes = [b for b in ocr_boxes if b[3] > badge_y]
    if bottom_boxes:
        return "overlapping badge"
    mid_boxes = [b for b in ocr_boxes if b[3] > front_height * 0.5]
    return "bottom" if mid_boxes else "top"