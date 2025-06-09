import os
from dataextractai.parsers.wellsfargo_visa_parser import WellsFargoVisaParser
from PyPDF2 import PdfReader

TEST_DIR = "data/clients/chase_test/input/wellsfargo_visa"


def main():
    parser = WellsFargoVisaParser()
    files = [f for f in os.listdir(TEST_DIR) if f.lower().endswith(".pdf")]
    if not files:
        print("No PDF files found in", TEST_DIR)
        return
    print(f"Testing metadata extraction for {len(files)} files in {TEST_DIR}\n")
    for fname in sorted(files):
        fpath = os.path.join(TEST_DIR, fname)
        try:
            # DEBUG: Print last page text for the first file only
            if fname == sorted(files)[0]:
                reader = PdfReader(fpath)
                last_page_text = reader.pages[-1].extract_text() if reader.pages else ""
                print("\n[DEBUG] Raw last page text for", fname)
                print(
                    "-----\n" + (last_page_text or "<NO TEXT EXTRACTED>") + "\n-----\n"
                )
            meta = parser.extract_metadata(fpath)
            print(f"File: {fname}")
            for k, v in meta.items():
                print(f"  {k}: {v}")
            print("-" * 60)
        except Exception as e:
            print(f"Error processing {fname}: {e}")
            print("-" * 60)


if __name__ == "__main__":
    main()
