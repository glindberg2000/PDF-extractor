import os
import json
from dataextractai.parsers.special_page_configs import special_page_configs
from PIL import Image
import tempfile
import datetime
from dataextractai.utils.ai import extract_structured_data_from_image

# from your_vision_llm_module import run_vision_llm  # Implement this for your API


def crop_by_percent(img, crop):
    w, h = img.size
    left = int(crop["left"] * w)
    right = int(crop["right"] * w)
    top = int(crop["top"] * h)
    bottom = int(crop["bottom"] * h)
    return img.crop((left, top, right, bottom))


def run_vision_llm(img_path, region_cfg):
    # Modular prompt for business expense extraction
    prompt = (
        "Extract all business expense fields and values from this cropped region of a tax organizer page. "
        "Return as a JSON object with field names as keys and values as numbers or strings. "
        "Ignore any page numbers, footers, or unrelated text."
    )
    return extract_structured_data_from_image(img_path, prompt)


def filter_to_previous_year(expense_data, tax_year):
    # If the data is a nested dict with year columns, keep only the previous year (tax_year-1)
    prev_year = str(int(tax_year) - 1)
    filtered = {}
    for k, v in expense_data.items():
        if isinstance(v, dict):
            # Look for year keys
            prev_val = None
            for year_key, amount in v.items():
                if prev_year in year_key and amount is not None:
                    prev_val = amount
            if prev_val is not None:
                filtered[k] = prev_val
        elif v is not None:
            filtered[k] = v
    return filtered


def enhance_manifest_with_vision(manifest_path, output_path=None):
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Try to get tax year from manifest (first page with a year field)
    tax_year = None
    for page in manifest:
        pf = page.get("prefilled_fields")
        if pf and ("tax_year" in pf or "year" in pf):
            tax_year = pf.get("tax_year") or pf.get("year")
            break
    if not tax_year:
        tax_year = datetime.datetime.now().year

    log_dir = os.path.dirname(manifest_path)
    log_path = os.path.join(log_dir, "vision_overlay_debug.log")
    log_entries = []
    updated = False
    debug_dir = os.path.join(os.path.dirname(manifest_path), "crops")
    os.makedirs(debug_dir, exist_ok=True)
    vision_overlay_count = 0
    for page in manifest:
        page_num = page.get("page_number")
        form_code = (
            page.get("topic_index_match", {}).get("form_code")
            if page.get("topic_index_match")
            else None
        )
        if not form_code:
            continue
        config = None
        codes = [c.strip() for c in form_code.split(",")]
        for code in codes:
            if code in special_page_configs:
                config = special_page_configs[code]
                break
        if not config:
            continue
        new_prefilled = {}
        for field, region_cfg in config.items():
            if region_cfg.get("method") == "vision":
                img_path = os.path.join(
                    os.path.dirname(manifest_path),
                    page["pdf_page_file"].replace(".pdf", "_full.png"),
                )
                with Image.open(img_path) as img:
                    cropped = crop_by_percent(img, region_cfg["crop"])
                    crop_filename = f"page_{page['page_number']}_{field}.png"
                    crop_path = os.path.join(debug_dir, crop_filename)
                    cropped.save(crop_path)
                    vision_result = run_vision_llm(crop_path, region_cfg)
                    if isinstance(vision_result, dict):
                        if any(isinstance(v, dict) for v in vision_result.values()):
                            vision_result = filter_to_previous_year(
                                vision_result, tax_year
                            )
                    new_prefilled[field] = vision_result
                    model_used = os.getenv("OPENAI_MODEL_OCR", "gpt-4o")
                    page["prefilled_model"] = model_used
                    log_entries.append(
                        {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "page_number": page_num,
                            "field": field,
                            "crop": region_cfg.get("crop"),
                            "img_path": crop_path,
                            "vision_llm_response": vision_result,
                        }
                    )
        if new_prefilled:
            page["prefilled_fields"] = new_prefilled
            page["has_prefilled_data"] = True
            updated = True
            vision_overlay_count += 1
            print(
                f"[VISION] Replaced all prefilled fields on page {page_num} (form_code {form_code}) with Vision LLM data: fields {list(new_prefilled.keys())}"
            )
        # --- ENSURE CONSISTENT TOP-LEVEL FIELDS ---
        if "has_prefilled_data" not in page:
            page["has_prefilled_data"] = False
        if "prefilled_fields" not in page:
            page["prefilled_fields"] = None
        if "prefilled_model" not in page:
            page["prefilled_model"] = None
    if log_entries:
        with open(log_path, "a") as logf:
            for entry in log_entries:
                logf.write(json.dumps(entry) + "\n")
        print(f"[VISION] Debug log written to {log_path}")
    if updated:
        out_path = output_path or manifest_path.replace(".json", "_vision.json")
        with open(out_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[VISION] Enhanced manifest written to {out_path}")
    else:
        print("[VISION] No pages required Vision enhancement.")
    print(f"[VISION] Vision overlay applied to {vision_overlay_count} page(s).")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python organizer_vision_enhancer.py <manifest_json_path> [output_json_path]"
        )
        exit(1)
    manifest_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    enhance_manifest_with_vision(manifest_path, output_path)
