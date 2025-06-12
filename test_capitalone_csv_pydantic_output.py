import os
from dataextractai.parsers.capitalone_csv_parser import main as capitalone_main
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_capitalone_csv_parser_pydantic_output():
    # Use the provided directory with sample files
    test_dir = os.path.join(
        os.path.dirname(__file__),
        "data",
        "clients",
        "chase_test",
        "input",
        "capitalone_csv",
    )
    result = capitalone_main(write_to_file=False, source_dir=test_dir)
    outputs = result if isinstance(result, list) else [result]
    for output in outputs:
        assert isinstance(output, ParserOutput)
        assert isinstance(output.transactions, list)
        assert all(isinstance(t, TransactionRecord) for t in output.transactions)
        if output.metadata is not None:
            assert isinstance(output.metadata, StatementMetadata)
        # Validate required fields in transactions
        for t in output.transactions:
            assert t.transaction_date is not None
            assert t.amount is not None
            assert t.description is not None
