import os
from dataextractai.parsers.first_republic_bank_parser import main as frb_main
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_first_republic_bank_parser_pydantic_output():
    # Use the provided directory with sample files
    test_dir = os.path.join(
        os.path.dirname(__file__),
        "data",
        "clients",
        "chase_test",
        "input",
        "first_republic",
    )
    sample_files = [f for f in os.listdir(test_dir) if f.lower().endswith(".pdf")]
    for fname in sample_files:
        fpath = os.path.join(test_dir, fname)
        output = frb_main(fpath)
        assert isinstance(output, ParserOutput)
        assert isinstance(output.transactions, list)
        for txn in output.transactions:
            assert isinstance(txn, TransactionRecord)
            assert isinstance(txn.transaction_date, str)
            assert isinstance(txn.amount, float)
            assert isinstance(txn.description, str)
        assert isinstance(output.metadata, StatementMetadata)
        assert output.metadata.bank_name == "First Republic Bank"
