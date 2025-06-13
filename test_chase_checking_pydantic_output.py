import os
from dataextractai.parsers.chase_checking import main as chase_main
from dataextractai.parsers_core.models import ParserOutput


def test_chase_checking_parser_pydantic_output():
    sample_dir = "data/clients/chase_test/input/chase_checking"
    pdf_files = [
        os.path.join(sample_dir, f)
        for f in os.listdir(sample_dir)
        if f.endswith(".pdf")
    ]
    assert pdf_files, f"No PDF files found in {sample_dir}"
    for pdf_file in pdf_files:
        output = chase_main(pdf_file)
        assert isinstance(
            output, ParserOutput
        ), f"Output is not ParserOutput for {pdf_file}"
        assert output.transactions, f"No transactions returned for {pdf_file}"
        for t in output.transactions:
            assert (
                t.transaction_date
            ), f"Transaction missing transaction_date in {pdf_file}"
            assert t.amount is not None, f"Transaction missing amount in {pdf_file}"
            assert t.description, f"Transaction missing description in {pdf_file}"
