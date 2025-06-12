import os
from dataextractai.parsers.chase_checking_parser import main as chase_main
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_chase_checking_parser_pydantic_output():
    # Replace this with the actual path to your test PDF(s)
    test_dir = os.path.join(
        os.path.dirname(__file__), "data", "clients", "chase_test", "input", "livetests"
    )
    result = chase_main(write_to_file=False, source_dir=test_dir)
    # If multiple outputs, test each; else, test the single output
    outputs = result if isinstance(result, list) else [result]
    for output in outputs:
        assert isinstance(
            output, ParserOutput
        ), f"Output is not a ParserOutput: {type(output)}"
        # Validate with Pydantic (catches serialization issues)
        ParserOutput.model_validate(output.model_dump())
        assert output.metadata is not None, "Metadata is missing"
        assert isinstance(
            output.metadata, StatementMetadata
        ), f"Metadata is not StatementMetadata: {type(output.metadata)}"
        assert isinstance(output.transactions, list), "Transactions is not a list"
        assert all(
            isinstance(t, TransactionRecord) for t in output.transactions
        ), "Not all transactions are TransactionRecord instances"
        # Check required fields in transactions
        for t in output.transactions:
            assert t.transaction_date, "Transaction missing transaction_date"
            assert t.amount is not None, "Transaction missing amount"
            assert t.description, "Transaction missing description"
