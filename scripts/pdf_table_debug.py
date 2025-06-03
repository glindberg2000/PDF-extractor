import sys
import pdfplumber

if len(sys.argv) < 2:
    print("Usage: python scripts/pdf_table_debug.py <path_to_pdf>")
    sys.exit(1)

pdf_path = sys.argv[1]

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, 1):
        print(f"\n--- Page {page_num} ---")
        table = page.extract_table()
        if table:
            for row in table:
                print(row)
        else:
            print("No table found on this page.")
            print("[RAW TEXT]")
            print(page.extract_text())
