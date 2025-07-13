#!/usr/bin/env python3
"""
extract_labels_from_pngs.py

Extract form labels from split PNGs using the default narrow crop from special_page_configs.json.

Usage:
    python extract_labels_from_pngs.py --input_dir <png_dir> --config <special_page_configs.json> --output <report.txt>

Outputs a text report listing all found labels and any new/unknown labels not present in the config.
"""
import os
import argparse
import json
from PIL import Image
from dataextractai.utils.ai import extract_structured_data_from_image


def is_garbage_label(label):
    return not label or str(label).strip() in ("", "None", "{}", "{'Form_Label': ''}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract form labels from PNGs using default crop."
    )
    parser.add_argument("--input_dir", required=True, help="Directory of PNGs")
    parser.add_argument(
        "--config", required=True, help="Path to special_page_configs.json"
    )
    parser.add_argument("--output", required=True, help="Path to output text report")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)
    crop = config["default"]["Form_Label"]["crop"]
    known_labels = set(config.keys())
    found_labels = set()
    label_to_page = {}

    pngs = sorted([f for f in os.listdir(args.input_dir) if f.endswith(".png")])
    for fname in pngs:
        page_num = int(fname.split("_")[1].split(".")[0])
        img_path = os.path.join(args.input_dir, fname)
        with Image.open(img_path) as img:
            w, h = img.size
            left = int(crop["left"] * w)
            right = int(crop["right"] * w)
            top = int(crop["top"] * h)
            bottom = int(crop["bottom"] * h)
            crop_img = img.crop((left, top, right, bottom))
            crop_img_path = os.path.join(args.input_dir, f"label_crop_{page_num}.png")
            crop_img.save(crop_img_path)
            result = extract_structured_data_from_image(
                crop_img_path, "Extract the Form_Label from this region."
            )
            label = result.get("Form_Label") or str(result)
            if is_garbage_label(label):
                continue
            found_labels.add(label)
            label_to_page[label] = page_num

    new_labels = found_labels - known_labels
    with open(args.output, "w") as f:
        f.write("All found labels ({}):\n".format(len(found_labels)))
        for label in sorted(found_labels):
            f.write(f"  {label} (page {label_to_page[label]})\n")
        f.write("\nNew/unknown labels ({}):\n".format(len(new_labels)))
        for label in sorted(new_labels):
            f.write(f"  {label} (page {label_to_page[label]})\n")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
