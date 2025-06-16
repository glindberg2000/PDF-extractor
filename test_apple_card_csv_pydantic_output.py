import os
from dataextractai.parsers.apple_card_csv_parser import main as apple_main
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_apple_card_csv_parser_pydantic_output():
    test_file = os.path.join(
        os.path.dirname(__file__),
        "data",
        "clients",
        "Greg",
        "Apple Card",
        "Apple Card Transactions - April 2024.csv",
    )
    output = apple_main(test_file)
    print("[TEST OUTPUT]", output.model_dump())
    assert isinstance(output, ParserOutput)
    assert isinstance(output.transactions, list)
    for txn in output.transactions:
        assert isinstance(txn, TransactionRecord)
        assert isinstance(txn.transaction_date, str) or txn.transaction_date is None
        assert isinstance(txn.amount, float)
        assert isinstance(txn.description, str)
    assert isinstance(output.metadata, StatementMetadata)
    assert output.metadata.bank_name == "Apple Card"
