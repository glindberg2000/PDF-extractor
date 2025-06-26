import sys
import os
import csv
from dataextractai.parsers.wellsfargo_mastercard_parser import main

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <input_pdf>")
    sys.exit(1)

pdf = sys.argv[1]
out = main(pdf)
out_csv = os.path.join("debug_outputs", os.path.basename(pdf).replace(".pdf", ".csv"))
os.makedirs("debug_outputs", exist_ok=True)

with open(out_csv, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(
        [
            "transaction_date",
            "posted_date",
            "amount",
            "description",
            "transaction_type",
            "reference_number",
            "file_path",
        ]
    )
    for t in out.transactions:
        writer.writerow(
            [
                getattr(t, "transaction_date", None),
                getattr(t, "posted_date", None),
                getattr(t, "amount", None),
                getattr(t, "description", None),
                getattr(t, "transaction_type", None),
                t.extra.get("reference_number") if t.extra else None,
                t.extra.get("file_path") if t.extra else None,
            ]
        )
