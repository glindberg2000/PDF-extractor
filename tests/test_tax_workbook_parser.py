import os
import pytest

# Import the main entrypoint for the tax workbook parser
from dataextractai.parsers.tax_workbook_parser import main as tax_workbook_main

SAMPLES = [
    "data/_examples/workbooks/22I_GORMAN_D_Organizer_V1_04235.PDF",
    "data/_examples/workbooks/22I_VALENTI_T_Organizer_V1_13710.PDF",
]


@pytest.mark.skipif(
    pytest.importorskip(
        "pdfplumber", reason="pdfplumber required for tax workbook parser"
    )
    is None,
    reason="pdfplumber not installed",
)
def test_tax_workbook_parser_schema():
    """
    Test the TaxWorkbookParser on sample workbooks.
    Asserts the output has the expected top-level keys and prints a summary for manual inspection.
    """
    for sample in SAMPLES:
        assert os.path.exists(sample), f"Sample file not found: {sample}"
        output = tax_workbook_main(sample)
        # Check top-level keys
        for key in [
            "organizer_sections",
            "documents",
            "unclassified_fields",
            "metadata",
        ]:
            assert key in output, f"Missing key '{key}' in output for {sample}"
        # Print summary for manual inspection
        print(f"\nParsed: {os.path.basename(sample)}")
        print(f"  Sections: {len(output['organizer_sections'])}")
        print(f"  Documents: {len(output['documents'])}")
        print(f"  Unclassified fields: {len(output['unclassified_fields'])}")
        print(f"  Errors: {len(output.get('metadata', {}).get('errors', []))}")
