import os
from dataextractai.parsers.first_republic_bank_parser import FirstRepublicBankParser

TEST_DIR = "data/clients/chase_test/input/first_republic"


def main():
    parser = FirstRepublicBankParser()
    files = [f for f in os.listdir(TEST_DIR) if f.lower().endswith(".pdf")]
    if not files:
        print("No PDF files found in", TEST_DIR)
        return
    print(f"Testing metadata extraction for {len(files)} files in {TEST_DIR}\n")
    for fname in sorted(files):
        fpath = os.path.join(TEST_DIR, fname)
        try:
            meta = parser.extract_metadata(fpath)
            print(f"File: {fname}")
            for k, v in meta.items():
                print(f"  {k}: {v}")
            print("-" * 60)
        except Exception as e:
            print(f"File: {fname} -- ERROR: {e}")
            print("-" * 60)


if __name__ == "__main__":
    main()
