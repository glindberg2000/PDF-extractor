import os
import pytest
from dataextractai.parsers_core.models import ParserOutput, TransactionRecord
from pprint import pprint

# Import the main entrypoints for each modular parser
from dataextractai.parsers.amazon_invoice_pdf_parser import main as amazon_invoice_main
from dataextractai.parsers.apple_card_csv_parser import main as apple_main
from dataextractai.parsers.capitalone_csv_parser import main as capitalone_main
from dataextractai.parsers.chase_visa_csv_parser import main as chase_visa_main
from dataextractai.parsers.first_republic_bank_parser import main as frb_main
from dataextractai.parsers.wellsfargo_bank_csv_parser import main as wf_bank_main
from dataextractai.parsers.wellsfargo_visa_parser import main as wf_visa_main
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    WellsFargoMastercardParser,
)


def _validate_parser_output(output: ParserOutput, expected_bank_name: str):
    """A helper function to run common assertions on a ParserOutput object."""
    assert isinstance(output, ParserOutput)
    assert isinstance(output.transactions, list)
    assert output.metadata is not None
    assert output.metadata.bank_name == expected_bank_name

    if output.transactions:
        for txn in output.transactions:
            assert isinstance(txn, TransactionRecord)
            assert isinstance(txn.transaction_date, str)
            assert isinstance(txn.amount, float)
            assert isinstance(txn.description, str)


def test_apple_card_parser():
    """Tests the Apple Card CSV parser for contract adherence and sign normalization."""
    test_file = "tests/samples/apple_card.csv"
    output = apple_main(test_file)
    _validate_parser_output(output, "Apple Card")

    # Verify sign normalization
    payment = next(
        (t for t in output.transactions if t.transaction_type == "credit"), None
    )
    charge = next(
        (t for t in output.transactions if t.transaction_type == "debit"), None
    )

    assert payment is not None, "Could not find a payment transaction to test."
    assert payment.amount > 0, "Payment amount should be positive."

    assert charge is not None, "Could not find a charge transaction to test."
    assert charge.amount < 0, "Charge amount should be negative."


def test_capital_one_parser():
    """Tests the Capital One CSV parser."""
    test_file = "tests/samples/capital_one.csv"
    output = capitalone_main(test_file)
    _validate_parser_output(output, "Capital One")

    debit = next(
        (t for t in output.transactions if t.transaction_type == "debit"), None
    )
    credit = next(
        (t for t in output.transactions if t.transaction_type == "credit"), None
    )

    if debit:
        assert debit.amount < 0, "Debit amount should be negative."
    if credit:
        assert credit.amount > 0, "Credit amount should be positive."


def test_amazon_invoice_parser():
    """Tests the Amazon Invoice PDF parser."""
    test_file = "tests/samples/amazon_invoice.pdf"
    output = amazon_invoice_main(test_file)
    _validate_parser_output(output, "Amazon Invoice")

    # All Amazon invoice transactions should be debits (negative)
    for txn in output.transactions:
        assert txn.amount < 0, "Amazon invoice transaction amount should be negative."


def test_chase_visa_parser():
    """Tests the Chase Visa CSV parser."""
    test_file = "tests/samples/chase_visa.csv"
    output = chase_visa_main(test_file)
    _validate_parser_output(output, "Chase Visa")

    payment = next(
        (t for t in output.transactions if t.transaction_type == "Payment"), None
    )
    sale = next((t for t in output.transactions if t.transaction_type == "Sale"), None)

    assert payment is not None, "Could not find a payment transaction to test."
    assert payment.amount > 0, "Payment amount should be positive."

    if sale:
        assert sale.amount < 0, "Sale amount should be negative."


def test_first_republic_parser():
    """Tests the First Republic Bank PDF parser."""
    test_file = "tests/samples/first_republic.pdf"
    output = frb_main(test_file)
    _validate_parser_output(output, "First Republic Bank")

    debit = next(
        (t for t in output.transactions if t.transaction_type == "debit"), None
    )
    credit = next(
        (t for t in output.transactions if t.transaction_type == "credit"), None
    )

    if debit:
        assert debit.amount < 0, "Debit amount should be negative."
    if credit:
        assert credit.amount > 0, "Credit amount should be positive."


def test_wellsfargo_bank_csv_parser():
    """Tests the Wells Fargo Bank CSV parser."""
    test_file = "tests/samples/wellsfargo_checking.csv"
    output = wf_bank_main(test_file)
    _validate_parser_output(output, "Wells Fargo")

    # In Wells Fargo CSVs, debits are already negative and credits positive
    debit = next((t for t in output.transactions if t.amount < 0), None)
    credit = next((t for t in output.transactions if t.amount > 0), None)

    assert debit is not None, "Could not find a debit transaction."
    assert credit is not None, "Could not find a credit transaction."


def test_wellsfargo_visa_parser():
    """Tests the Wells Fargo Visa PDF parser."""
    test_file = "tests/samples/wellsfargo_visa.pdf"
    output = wf_visa_main(test_file)
    _validate_parser_output(output, "Wells Fargo")

    # This parser should also produce negative debits and positive credits
    debit = next((t for t in output.transactions if t.amount < 0), None)
    credit = next((t for t in output.transactions if t.amount > 0), None)

    assert debit is not None, "Could not find a debit transaction."
    assert credit is not None, "Could not find a credit transaction."


def test_wellsfargo_mastercard_parser_contract():
    """Tests the Wells Fargo Mastercard PDF parser for full contract compliance on all fields."""
    test_folder = "tests/samples/Wells Fargo Mastercard"
    parser = WellsFargoMastercardParser()
    for fname in os.listdir(test_folder):
        if fname.endswith(".pdf"):
            fpath = os.path.join(test_folder, fname)
            raw = parser.parse_file(fpath)
            norm = parser.normalize_data(raw, file_path=fpath)
            for t in norm:
                # Check all required fields exist
                assert "transaction_date" in t
                assert "amount" in t
                assert "description" in t
                assert "posted_date" in t
                assert "transaction_type" in t
                assert "credits" in t
                assert "charges" in t
                assert "extra" in t
                # Type checks
                assert isinstance(t["transaction_date"], str)
                assert isinstance(t["amount"], float)
                assert isinstance(t["description"], str)
                # posted_date can be None or str
                assert t["posted_date"] is None or isinstance(t["posted_date"], str)
                assert isinstance(t["transaction_type"], (str, type(None)))
                assert isinstance(t["credits"], float)
                assert isinstance(t["charges"], float)
                assert isinstance(t["extra"], dict)
                # file_path must be present in extra and match fpath
                assert "file_path" in t["extra"]
                assert t["extra"]["file_path"] == fpath
                # Sign convention: credits positive, charges negative or zero
                if t["credits"] > 0:
                    assert t["amount"] > 0
                if t["charges"] > 0:
                    assert t["amount"] < 0
