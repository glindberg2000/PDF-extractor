import argparse
import sys
from dataextractai.utils.normalize_api import normalize_parsed_data_df
import os


def main():
    parser = argparse.ArgumentParser(
        description="Test a modular parser on a single file using the new system."
    )
    parser.add_argument(
        "--parser",
        required=True,
        help="Parser name (as registered, e.g. 'first_republic_bank')",
    )
    parser.add_argument("--input", required=True, help="Path to input PDF file")
    parser.add_argument(
        "--client", required=True, help="Client name (for context, e.g. 'chase_test')"
    )
    parser.add_argument("--output", help="Path to save output CSV (optional)")
    args = parser.parse_args()

    try:
        df = normalize_parsed_data_df(args.input, args.parser, args.client)
    except Exception as e:
        print(f"[ERROR] Exception during parsing/normalization: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n=== DataFrame Preview ===")
    print(df.head())
    print(f"Rows: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")

    # Robust assertions
    try:
        assert not df.empty, "Output DataFrame is empty!"
        assert "transaction_hash" in df.columns, "transaction_hash column missing!"
        assert "normalized_date" in df.columns, "normalized_date column missing!"
        assert df.notna().any().any(), "All values are NaN!"
    except AssertionError as err:
        print(f"[FAIL] {err}", file=sys.stderr)
        sys.exit(2)

    if args.output:
        out_dir = os.path.dirname(args.output)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        try:
            df.to_csv(args.output, index=False)
            print(f"[OK] Saved output to {args.output}")
        except Exception as e:
            print(f"[ERROR] Could not save CSV: {e}", file=sys.stderr)
            sys.exit(3)
    print("[OK] All checks passed. Parser output is production-ready.")


if __name__ == "__main__":
    main()
