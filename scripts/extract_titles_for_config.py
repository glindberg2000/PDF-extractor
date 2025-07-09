#!/usr/bin/env python3
"""
extract_titles_for_config.py

Extracts the title (form label) from a set of page PNGs using the default narrow label crop and Vision LLM/OCR, and outputs a JSON config with 'main_area' crops for each label.

Usage:
    python extract_titles_for_config.py --pages 10 24 25 31 33 35 18 21 22 --png_dir <dir> --config <special_page_configs.json> --output <output.json>
"""
import argparse
import json
import os
from PIL import Image
from dataextractai.utils.ai import extract_structured_data_from_image


def main():
    parser = argparse.ArgumentParser(description="Extract titles for config.")
    parser.add_argument(
        "--pages", nargs="+", type=int, required=True, help="Page numbers to process"
    )
    parser.add_argument("--png_dir", required=True, help="Directory of PNGs")
    parser.add_argument(
        "--config", required=True, help="Path to special_page_configs.json"
    )
    parser.add_argument("--output", required=True, help="Output JSON config file")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)
    crop = config["default"]["Title"]["crop"]
    main_crop = {"top": 0.12, "bottom": 0.92, "left": 0.05, "right": 0.95}
    out = {}

    for page_num in args.pages:
        img_path = os.path.join(args.png_dir, f"page_{page_num}.png")
        with Image.open(img_path) as img:
            w, h = img.size
            left = int(crop["left"] * w)
            right = int(crop["right"] * w)
            top = int(crop["top"] * h)
            bottom = int(crop["bottom"] * h)
            crop_img = img.crop((left, top, right, bottom))
            crop_img_path = os.path.join(
                args.png_dir, f"title_crop_{page_num}_for_config.png"
            )
            crop_img.save(crop_img_path)
            result = extract_structured_data_from_image(
                crop_img_path, "Extract the Title from this region."
            )
            title = result.get("Title") or str(result)
            if not title or str(title).strip() in (
                "",
                "None",
                "{}",
                "{'Title': ''}",
            ):
                continue
            # Also extract the label for the key (using Form_Label crop)
            label_crop = config["default"]["Form_Label"]["crop"]
            l_left = int(label_crop["left"] * w)
            l_right = int(label_crop["right"] * w)
            l_top = int(label_crop["top"] * h)
            l_bottom = int(label_crop["bottom"] * h)
            label_img = img.crop((l_left, l_top, l_right, l_bottom))
            label_img_path = os.path.join(
                args.png_dir, f"label_crop_{page_num}_for_config.png"
            )
            label_img.save(label_img_path)
            label_result = extract_structured_data_from_image(
                label_img_path, "Extract the Form_Label from this region."
            )
            label = label_result.get("Form_Label") or str(label_result)
            if not label or str(label).strip() in (
                "",
                "None",
                "{}",
                "{'Form_Label': ''}",
            ):
                continue
            out[label] = {"Title": title, "main_area": {"crop": main_crop}}
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Config written to {args.output}")


if __name__ == "__main__":
    main()
