import os
from dataextractai.parsers.capitalone_csv_parser import main as capitalone_main
from dataextractai.parsers_core.models import ParserOutput


def test_capitalone_csv_parser_pydantic_output():
    sample_dir = os.path.join(
        os.path.dirname(__file__),
        "data",
        "clients",
        "chase_test",
        "input",
        "capitalone_csv",
    )
    csv_files = [
        os.path.join(sample_dir, f)
        for f in os.listdir(sample_dir)
        if f.endswith(".csv")
    ]
    assert csv_files, f"No CSV files found in {sample_dir}"
    for csv_file in csv_files:
        output = capitalone_main(csv_file)
        assert isinstance(
            output, ParserOutput
        ), f"Output is not ParserOutput for {csv_file}"
        assert output.transactions, f"No transactions found in output for {csv_file}"
        for tx in output.transactions:
            assert tx.transaction_date, f"Missing transaction_date in {csv_file}"
            assert tx.amount is not None, f"Missing amount in {csv_file}"
            assert tx.description, f"Missing description in {csv_file}"
