import os
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    WellsFargoMastercardParser,
)
from dataextractai.parsers_core.models import TransactionRecord

folder = "tests/samples/Wells Fargo Mastercard"
parser = WellsFargoMastercardParser()
all_valid = True

for fname in os.listdir(folder):
    if fname.endswith(".pdf"):
        fpath = os.path.join(folder, fname)
        try:
            raw = parser.parse_file(fpath)
            norm = parser.normalize_data(raw)
            txs = [TransactionRecord(**t) for t in norm]
            valid = all(isinstance(t, TransactionRecord) for t in txs)
            print(f"{fname}: {valid}, {len(txs)} transactions")
            all_valid = all_valid and valid
        except Exception as e:
            print(f"{fname}: ERROR - {e}")
            all_valid = False
print("All files valid:", all_valid)
