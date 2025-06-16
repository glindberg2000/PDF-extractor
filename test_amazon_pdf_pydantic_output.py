import os
from dataextractai.parsers.amazon_pdf_parser import main as amazon_main
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)


def test_amazon_pdf_parser_pydantic_output():
    test_file = os.path.join(
        os.path.dirname(__file__),
        "data",
        "clients",
        "Greg",
        "Amazon",
        "Your Orders 17.pdf",
    )
    output = amazon_main(test_file)
    print("[TEST OUTPUT]", output.model_dump())
    assert isinstance(output, ParserOutput)
    assert isinstance(output.transactions, list)
    assert len(output.transactions) > 0
    for txn in output.transactions:
        assert isinstance(txn, TransactionRecord)
        assert isinstance(txn.transaction_date, str) or txn.transaction_date is None
        assert isinstance(txn.amount, float)
        assert isinstance(txn.description, str)
        assert hasattr(txn, "transaction_type")
    assert isinstance(output.metadata, StatementMetadata)
    assert output.metadata.bank_name == "Amazon"
    # Check for contract fields in output
    out_dict = output.model_dump()
    assert "transactions" in out_dict
    assert "metadata" in out_dict
    assert "schema_version" in out_dict
    print("[VERIFIED OUTPUT SAMPLE]", out_dict)
