#!/usr/bin/env python3
"""
pdf_splitter.py

Split a PDF into individual page PDFs.

Usage:
    python pdf_splitter.py --input <input.pdf> --output_dir <output_dir>

Each page will be saved as page_{n}.pdf in the output directory.
"""
import os
import argparse
from PyPDF2 import PdfReader, PdfWriter


def split_pdf(input_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    reader = PdfReader(input_path)
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = os.path.join(output_dir, f"page_{i+1}.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
    print(f"Split {len(reader.pages)} pages to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Split a PDF into individual page PDFs."
    )
    parser.add_argument("--input", required=True, help="Path to input PDF")
    parser.add_argument(
        "--output_dir", required=True, help="Directory to save split pages"
    )
    args = parser.parse_args()
    split_pdf(args.input, args.output_dir)


if __name__ == "__main__":
    main()
