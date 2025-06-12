import os
from dataextractai.parsers.wellsfargo_checking_csv_parser import (
    WellsFargoCheckingCSVParser,
)
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_wellsfargo_checking_csv_parser_pydantic_output():
    # Use the provided directory with a sample file
    test_dir = os.path.join(
        os.path.dirname(__file__),
        "data",
        "clients",
        "chase_test",
        "input",
        "wellsfargo_checking_csv",
    )
    parser = WellsFargoCheckingCSVParser()
    result = parser.main(write_to_file=False, source_dir=test_dir)
    outputs = result if isinstance(result, list) else [result]
    for output in outputs:
        assert isinstance(output, ParserOutput)
        assert isinstance(output.transactions, list)
        for txn in output.transactions:
            assert isinstance(txn, TransactionRecord)
            assert isinstance(txn.transaction_date, str)
            assert isinstance(txn.amount, float)
            assert isinstance(txn.description, str)
        assert isinstance(output.metadata, StatementMetadata)
        assert output.metadata.bank_name == "Wells Fargo"
