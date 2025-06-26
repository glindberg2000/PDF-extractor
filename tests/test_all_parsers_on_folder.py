import os
import sys
import pytest
import traceback
from collections import defaultdict
import time
import importlib
from dataextractai.parsers_core.models import ParserOutput

# No need to modify sys.path, pytest handles it.


def get_parser_map():
    """Builds a map of parser names to their main functions by importing them as modules."""
    parser_map = {}
    # Assuming pytest runs from the project root
    parsers_dir = os.path.join("dataextractai", "parsers")

    for filename in os.listdir(parsers_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            parser_module_name = filename.replace(".py", "")
            module_path = f"dataextractai.parsers.{parser_module_name}"
            try:
                module = importlib.import_module(module_path)
                if hasattr(module, "main"):
                    parser_map[parser_module_name] = module.main
            except Exception as e:
                # pytest will capture stdout, so print is fine for debugging.
                print(f"Could not import main from {module_path}: {e}")

    return parser_map


FILENAME_KEYWORD_MAP = {
    "chase_visa_csv": "chase_visa_csv_parser",
    "chase_visa": "chase_visa_csv_parser",
    "chase_checking": "chase_checking",
    "bofa_bank": "bofa_bank_parser",
    "bofa_visa": "bofa_visa_parser",
    "wellsfargo_bank_csv": "wellsfargo_bank_csv_parser",
    "wellsfargo_checking_csv": "wellsfargo_checking_csv_parser",
    "wellsfargo_mastercard": "wellsfargo_mastercard_parser",
    "wellsfargo_visa": "wellsfargo_visa_parser",
    "wellsfargo_bank": "wellsfargo_bank_parser",
    "first_republic_bank": "first_republic_bank_parser",
    "first_republic": "first_republic_bank_parser",
    "amazon_invoice_pdf": "amazon_invoice_pdf_parser",
    "amazon_invoice": "amazon_invoice_pdf_parser",
    "amazon_pdf": "amazon_pdf_parser",
    "amazon_order": "amazon_parser",
    "apple_card_csv": "apple_card_csv_parser",
    "apple_card": "apple_card_csv_parser",
    "capitalone_visa_print": "capitalone_visa_print_parser",
    "capitalone_csv": "capitalone_csv_parser",
    "capital_one": "capitalone_csv_parser",
    "wellsfargo_checking": "wellsfargo_checking_csv_parser",
}


def find_parser(filename, parser_map):
    """Finds the appropriate parser for a given filename. Tries keyword match, then content-based detection."""
    normalized_filename = filename.lower().replace("-", "_").replace(" ", "_")
    sorted_keywords = sorted(FILENAME_KEYWORD_MAP.keys(), key=len, reverse=True)

    for keyword in sorted_keywords:
        if keyword in normalized_filename:
            parser_name = FILENAME_KEYWORD_MAP[keyword]
            if parser_name in parser_map:
                return parser_map[parser_name], parser_name

    # Fallback: try content-based detection (call can_parse on each parser)
    for parser_name, parser_func in parser_map.items():
        try:
            # Import the parser class to call can_parse
            module = importlib.import_module(f"dataextractai.parsers.{parser_name}")
            parser_cls = None
            if hasattr(module, parser_name[0].upper() + parser_name[1:]):
                parser_cls = getattr(module, parser_name[0].upper() + parser_name[1:])
            elif hasattr(module, "WellsFargoMastercardParser"):
                parser_cls = getattr(module, "WellsFargoMastercardParser")
            elif hasattr(module, "Parser"):
                parser_cls = getattr(module, "Parser")
            if parser_cls and hasattr(parser_cls, "can_parse"):
                parser = parser_cls()
                file_path = (
                    filename
                    if os.path.exists(filename)
                    else os.path.join("tests/samples", filename)
                )
                if parser.can_parse(file_path):
                    return parser_func, parser_name
        except Exception as e:
            print(
                f"[DEBUG] Content-based detection failed for {parser_name} on {filename}: {e}"
            )
    return None, None


def run_parsers_on_directory(directory, parser_map):
    """Runs parsers on all files in a directory and returns results."""
    results = defaultdict(lambda: {"success": [], "failed": []})
    unparsed_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("."):
                continue

            file_path = os.path.join(root, file)
            parser_func, parser_name = find_parser(file, parser_map)

            if parser_func:
                try:
                    output = parser_func(file_path)
                    if not isinstance(output, ParserOutput):
                        raise TypeError(
                            f"Parser did not return a ParserOutput object. Got {type(output)} instead."
                        )
                    if output.errors:
                        results[parser_name]["failed"].append(
                            {"file": file_path, "error": output.errors}
                        )
                    else:
                        results[parser_name]["success"].append(
                            {
                                "file": file_path,
                                "transactions": len(output.transactions),
                            }
                        )
                except Exception as e:
                    error_info = traceback.format_exc()
                    results[parser_name]["failed"].append(
                        {"file": file_path, "error": error_info}
                    )
            else:
                unparsed_files.append(file_path)

    return results, unparsed_files


def print_summary(results, unparsed_files, start_time):
    """Prints a summary of the parser run."""
    end_time = time.time()
    print("\n" + "=" * 80)
    print("PARSER RUN SUMMARY")
    print("=" * 80)
    print(f"Total time: {end_time - start_time:.2f} seconds")

    total_success = 0
    total_failed = 0

    for parser_name, res in sorted(results.items()):
        success_count = len(res["success"])
        failed_count = len(res["failed"])
        total_success += success_count
        total_failed += failed_count

        print(f"\n--- {parser_name} ---")
        print(f"  [+] Success: {success_count}")
        print(f"  [-] Failed:  {failed_count}")

        if res["failed"]:
            for failure in res["failed"]:
                print(f"\n    [!] FILE: {failure['file']}")
                print(f"    [!] ERROR: {failure['error']}")

    print("\n" + "-" * 80)
    print(f"OVERALL: {total_success} succeeded, {total_failed} failed.")

    if unparsed_files:
        print("\n--- UNPARSED FILES ---")
        for f in unparsed_files:
            print(f"  - {f}")
    print("=" * 80)

    # For pytest, assert that there were no failures.
    assert (
        total_failed == 0
    ), f"{total_failed} parsers failed. Check the log for details."
    assert (
        not unparsed_files
    ), f"{len(unparsed_files)} files could not be parsed. Check the log."


def test_run_all_parsers_on_samples():
    """
    Pytest discoverable function to run all parsers on the tests/samples directory.
    """
    samples_directory = "tests/samples"

    start_time = time.time()
    parser_map = get_parser_map()
    print(f"\nLoaded {len(parser_map)} parsers.")

    results, unparsed_files = run_parsers_on_directory(samples_directory, parser_map)
    print_summary(results, unparsed_files, start_time)
