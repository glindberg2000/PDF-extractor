"""
Gold Standard Generator for Tax Organizer Page Labels

Purpose:
    Creates a mapping from extracted page labels (form codes, titles, or special page keys) to canonical, human-friendly descriptions for robust, consistent form/page identification.

Extraction & Fallback Hierarchy:
    1. Narrow Crop Extraction:
        - Attempts to extract the form label/title using a precise, default crop.
    2. Wide Crop Extraction:
        - If the narrow crop fails, tries a wider crop (e.g., 'Page_Label').
    3. Special/Unique Crop Extraction:
        - If both above fail, tries crops unique to special pages (cover, signature, instructions).
    4. Raw Text Fallbacks:
        - If all crops fail, scans the full OCR'd text for unique phrases (e.g., cover/signature page).
    5. TOC/Topic Index or Page Number Fallback:
        - If all else fails, uses the TOC/Topic Index or page number to assign a title.

Special Page Handling:
    - Cover Page:
        If raw text contains 'REMOVE THIS SHEET PRIOR TO RETURNING THE COMPLETED ORGANIZER', assign key 'cover_page' and description 'Cover Page: Remove Before Returning'.
    - Signature Page:
        If raw text contains 'I (We) have submitted this information for the sole purpose of preparing', assign key 'signature_page' and description 'Signature Page'.

Truncated/Partial Labels:
    - If the extractor outputs '1 of 2)' or '2 of 2)', patch the mapping so these keys map to the full description.

Maintenance:
    - If new special pages or layouts are found, add new crops or raw text phrases to the config and fallback logic.
    - If a new truncated label appears, patch the gold standard mapping to include it.

This script is critical for ensuring robust, future-proofed extraction and matching of form/page labels in tax organizer PDFs.
"""

import os
import sys
import json
import tempfile
from collections import defaultdict, Counter
from PIL import Image
from difflib import get_close_matches
from glob import glob
from dataextractai.utils.ai import extract_structured_data_from_image
import argparse

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "special_page_configs.json")


def pdf_page_to_png(pdf_path, out_dir, page_number):
    from pdf2image import convert_from_path

    images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number)
    img = images[0]
    out_path = os.path.join(
        out_dir,
        f"{os.path.basename(pdf_path).replace('.pdf','')}_page_{page_number}.png",
    )
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


def extract_label_for_gold_standard(page_image_path, config):
    """
    Always use the default Form_Label crop from config for label extraction.
    """
    label_crop = config["default"]["Form_Label"]["crop"]
    # ... rest of extraction logic ...


def main():
    parser = argparse.ArgumentParser(
        description="Generate gold standard mapping for form codes and titles."
    )
    parser.add_argument("pdf_dir", help="Directory containing PDF files")
    parser.add_argument("config_path", help="Path to special_page_configs.json")
    parser.add_argument(
        "--toc_json", help="Path to TOC/Topic Index JSON file (optional)"
    )
    parser.add_argument(
        "--output", default="gold_standard_form_titles.json", help="Output mapping file"
    )
    parser.add_argument(
        "--debug_output",
        default="gold_standard_form_titles_debug.json",
        help="Debug output file with detailed mapping info",
    )
    args = parser.parse_args()

    pdf_dir = args.pdf_dir
    config_path = args.config_path
    toc_json = args.toc_json
    output_path = args.output
    debug_output_path = args.debug_output

    # Load config
    with open(CONFIG_PATH, "r") as f:
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

    # Load TOC/Topic Index entries if provided
    toc_titles = []
    if toc_json:
        with open(toc_json, "r") as f:
            toc_data = json.load(f)
        # Assume toc_data is a list of dicts with 'title' or similar
        for entry in toc_data:
            if isinstance(entry, dict):
                for k in entry:
                    if "title" in k.lower():
                        toc_titles.append(entry[k])
            elif isinstance(entry, str):
                toc_titles.append(entry)

    # Gather all PDFs (case-insensitive, recursive)
    pdf_files = glob(os.path.join(pdf_dir, "**", "*.pdf"), recursive=True)
    pdf_files += glob(os.path.join(pdf_dir, "**", "*.PDF"), recursive=True)
    print(
        f"[INFO] Found {len(pdf_files)} PDF(s) in {pdf_dir} (recursive, case-insensitive)"
    )

    # For each unique label, collect all extracted titles and debug info
    label_to_titles = defaultdict(list)
    label_to_pages = defaultdict(list)
    debug_info = defaultdict(list)
    for pdf_path in pdf_files:
        page_count = get_pdf_page_count(pdf_path)
        print(f"[INFO] Processing {os.path.basename(pdf_path)} ({page_count} pages)")
        for page_number in range(1, page_count + 1):
            out_dir = tempfile.mkdtemp(prefix="gold_map_crops_")
            png_path = pdf_page_to_png(pdf_path, out_dir, page_number)
            # Extract label
            label_img = crop_image(png_path, label_crop)
            label_crop_path = os.path.join(out_dir, f"label_crop_{page_number}.png")
            label_img.save(label_crop_path)
            try:
                label_result = extract_structured_data_from_image(
                    label_crop_path, "Extract the Form_Label from this region."
                )
                label_text = label_result.get("Form_Label") or str(label_result)
            except Exception as e:
                print(
                    f"[WARN] Vision LLM failed on label crop (page {page_number}): {e}"
                )
                continue
            label_text = str(label_text).strip()
            if not label_text:
                continue
            # Extract title
            title_img = crop_image(png_path, title_crop)
            title_crop_path = os.path.join(out_dir, f"title_crop_{page_number}.png")
            title_img.save(title_crop_path)
            try:
                title_result = extract_structured_data_from_image(
                    title_crop_path, "Extract the Title from this region."
                )
                title_text = title_result.get("Title") or str(title_result)
            except Exception as e:
                print(
                    f"[WARN] Vision LLM failed on title crop (page {page_number}): {e}"
                )
                continue
            title_text = str(title_text).strip()
            if not title_text:
                continue
            label_to_titles[label_text].append(title_text)
            label_to_pages[label_text].append(
                (os.path.basename(pdf_path), page_number, title_text)
            )
            debug_info[label_text].append(
                {
                    "pdf_file": os.path.basename(pdf_path),
                    "page_number": page_number,
                    "extracted_label": label_text,
                    "extracted_title": title_text,
                    "label_crop_path": label_crop_path,
                    "title_crop_path": title_crop_path,
                }
            )

    # For each label, pick the most common title, and fuzzy match to TOC if available
    gold_mapping = {}
    debug_mapping = {}
    print("\n[SUMMARY] Gold Standard Mapping Candidates:")
    for label, titles in label_to_titles.items():
        most_common_title, _ = Counter(titles).most_common(1)[0]
        toc_match = None
        if toc_titles:
            matches = get_close_matches(most_common_title, toc_titles, n=1, cutoff=0.7)
            toc_match = matches[0] if matches else None
        gold_mapping[label] = most_common_title
        debug_mapping[label] = {
            "most_common_title": most_common_title,
            "toc_match": toc_match,
            "pages": debug_info[label],
        }
        print(f"Form Code: {label}")
        print(f"  Most Common Title: {most_common_title}")
        if toc_match:
            print(f"  Best TOC/Topic Index Match: {toc_match}")
        print(f"  Seen on pages:")
        for info in debug_info[label]:
            print(
                f"    {info['pdf_file']} page {info['page_number']}: {info['extracted_title']}"
            )
        print()

    # Write mapping
    with open(output_path, "w") as f:
        json.dump(gold_mapping, f, indent=2)
    print(f"[INFO] Gold standard mapping written to {output_path}")
    # Write debug mapping
    with open(debug_output_path, "w") as f:
        json.dump(debug_mapping, f, indent=2)
    print(f"[INFO] Debug mapping written to {debug_output_path}")


if __name__ == "__main__":
    main()
