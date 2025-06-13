import os
from dataextractai.parsers.chase_checking import ChaseCheckingParser
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_chase_checking_parser_pydantic_output():
    parser = ChaseCheckingParser()
    # Replace with the correct sample file path as needed
    sample_file = "tests/samples/chase_checking/sample_statement.pdf"
    output = parser.parse_file(sample_file)
    assert isinstance(output, ParserOutput)
    # Optionally, add more assertions on output.transactions, output.metadata, etc.

    # If multiple outputs, test each; else, test the single output
    if isinstance(output, list):
        for o in output:
            assert isinstance(
                o, ParserOutput
            ), f"Output is not a ParserOutput: {type(o)}"
            # Validate with Pydantic (catches serialization issues)
            ParserOutput.model_validate(o.model_dump())
            assert o.metadata is not None, "Metadata is missing"
            assert isinstance(
                o.metadata, StatementMetadata
            ), f"Metadata is not StatementMetadata: {type(o.metadata)}"
            assert isinstance(o.transactions, list), "Transactions is not a list"
            assert all(
                isinstance(t, TransactionRecord) for t in o.transactions
            ), "Not all transactions are TransactionRecord instances"
            # Check required fields in transactions
            for t in o.transactions:
                assert t.transaction_date, "Transaction missing transaction_date"
                assert t.amount is not None, "Transaction missing amount"
                assert t.description, "Transaction missing description"
    else:
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
