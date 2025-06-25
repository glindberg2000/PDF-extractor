import os
import csv
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    WellsFargoMastercardParser,
)
from dataextractai.parsers_core.models import TransactionRecord

folder = "tests/samples/Wells Fargo Mastercard"
outfile = "wells_fargo_mastercard_all.csv"

parser = WellsFargoMastercardParser()
rows = []

for fname in os.listdir(folder):
    if fname.lower().endswith(".pdf"):
        fpath = os.path.join(folder, fname)
        try:
            raw = parser.parse_file(fpath)
            norm = parser.normalize_data(raw)
            meta = parser.extract_metadata(raw, fpath)
            for t in norm:
                t["original_filename"] = fname.strip()
                t["account_number"] = getattr(meta, "account_number", None)
                t["statement_date"] = getattr(meta, "statement_date", None)
                t["statement_period_start"] = getattr(
                    meta, "statement_period_start", None
                )
                t["statement_period_end"] = getattr(meta, "statement_period_end", None)
                rows.append(t)
        except Exception as e:
            print(f"Error processing {fname}: {e}")

fieldnames = [
    "original_filename",
    "transaction_date",
    "posted_date",
    "description",
    "amount",
    "transaction_type",
    "account_number",
    "statement_date",
    "statement_period_start",
    "statement_period_end",
    "extra",
]

with open(outfile, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} transactions to {outfile}")
