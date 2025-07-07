import os
import sys
import json
import tempfile
from PIL import Image
from difflib import get_close_matches
from dataextractai.utils.ai import extract_structured_data_from_image
import argparse

# Usage: python test_page_label_and_crop_extraction.py <single_page_pdf_path> <special_page_configs.json>


def pdf_page_to_png(pdf_path, out_dir, page_number):
    from pdf2image import convert_from_path

    images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number)
    img = images[0]
    out_path = os.path.join(out_dir, f"page_{page_number}.png")
    img.save(out_path)
    return out_path


def crop_image(img_path, crop):
    img = Image.open(img_path)
    w, h = img.size
    left = int(crop["left"] * w)
    right = int(crop["right"] * w)
    top = int(crop["top"] * h)
    bottom = int(crop["bottom"] * h)
    return img.crop((left, top, right, bottom))


def get_pdf_page_count(pdf_path):
    from PyPDF2 import PdfReader

    reader = PdfReader(pdf_path)
    return len(reader.pages)


def main():
    parser = argparse.ArgumentParser(
        description="Test label/title extraction and field lookup for single/multi-page PDFs."
    )
    parser.add_argument("pdf_path", help="Path to PDF file (single or multi-page)")
    parser.add_argument("config_path", help="Path to special_page_configs.json")
    parser.add_argument(
        "--page", type=int, default=1, help="Page number to start with (1-based)"
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path
    config_path = args.config_path
    start_page = args.page
    out_dir = tempfile.mkdtemp(prefix="test_page_label_crops_")
    print(f"[INFO] Output dir: {out_dir}")

    # Load JSON config
    with open(config_path, "r") as f:
        config = json.load(f)
    if "default" not in config:
        print("[ERROR] 'default' entry missing in special_page_configs.json.")
        sys.exit(1)
    default_fields = config["default"]
    label_crop = default_fields.get("Form_Label", {}).get("crop")
    title_crop = default_fields.get("Title", {}).get("crop")
    if not label_crop or not title_crop:
        print("[ERROR] 'default' config entry missing 'Form_Label' or 'Title' crop.")
        sys.exit(1)

    # Get page count
    page_count = get_pdf_page_count(pdf_path)
    print(f"[INFO] PDF has {page_count} page(s). Starting at page {start_page}.")
    found = False
    for page_number in range(start_page, page_count + 1):
        print(f"[INFO] Processing page {page_number}...")
        png_path = pdf_page_to_png(pdf_path, out_dir, page_number)
        print(f"[INFO] Saved page PNG: {png_path}")
        label_img = crop_image(png_path, label_crop)
        label_crop_path = os.path.join(out_dir, f"label_crop_page_{page_number}.png")
        label_img.save(label_crop_path)
        print(f"[INFO] Saved label crop: {label_crop_path}")
        try:
            label_result = extract_structured_data_from_image(
                label_crop_path, "Extract the Form_Label from this region."
            )
            label_text = label_result.get("Form_Label") or str(label_result)
        except Exception as e:
            print(f"[ERROR] Vision LLM failed on label crop: {e}")
            continue
        print(f"[RESULT] Extracted label: {label_text}")
        config_keys = [k for k in config.keys() if k != "default"]
        matches = get_close_matches(label_text, config_keys, n=1, cutoff=0.7)
        if not matches or not label_text.strip():
            print(
                f"[WARN] No confident match for label '{label_text}' on page {page_number}. Skipping."
            )
            continue
        matched_key = matches[0]
        print(
            f"[MATCH] Label '{label_text}' matched to form code '{matched_key}' on page {page_number}"
        )
        # Extract all fields for matched form code
        fields = config[matched_key]
        for field, field_cfg in fields.items():
            crop = field_cfg["crop"]
            crop_img = crop_image(png_path, crop)
            crop_path = os.path.join(
                out_dir, f"{matched_key}_{field}_page_{page_number}.png"
            )
            crop_img.save(crop_path)
            print(f"[INFO] Saved field crop: {crop_path}")
            try:
                result = extract_structured_data_from_image(
                    crop_path, f"Extract the {field} from this region."
                )
            except Exception as e:
                result = {"error": str(e)}
            print(f"[FIELD RESULT] {field}: {result}")
        found = True
        break
    if not found:
        print(
            "[SUMMARY] No standard form page found in PDF using default label crop. All pages skipped."
        )


if __name__ == "__main__":
    main()
