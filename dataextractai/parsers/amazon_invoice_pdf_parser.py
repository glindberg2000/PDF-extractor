import re
from typing import Optional, List
from pathlib import Path
from pydantic import BaseModel, Field
import PyPDF2
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.models import (
    ParserOutput,
    TransactionRecord,
    StatementMetadata,
)
from dataextractai.parsers_core.registry import ParserRegistry


class AmazonInvoicePDFParser(BaseParser):
    parser_name = "amazon_invoice_pdf"
    parser_version = "1.0"

    @staticmethod
    def to_iso_date(date_str: str) -> Optional[str]:
        """Convert 'Month Day, Year' to 'YYYY-MM-DD'. Return None if invalid."""
        import datetime

        if not date_str or not isinstance(date_str, str):
            return None
        try:
            return datetime.datetime.strptime(date_str.strip(), "%B %d, %Y").strftime(
                "%Y-%m-%d"
            )
        except Exception:
            return None

    @classmethod
    def can_parse(cls, file_path: str, **kwargs) -> bool:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = reader.pages[0].extract_text() or ""
            return (
                "Final Details for Order" in text and "Amazon.com order number" in text
            )
        except Exception:
            return False

    @staticmethod
    def parse_amount(text: str) -> Optional[float]:
        try:
            return float(text.replace("$", "").replace(",", "").strip())
        except Exception:
            return None

    @staticmethod
    def parse_invoice_text(text: str) -> dict:
        # Extract key fields using regex and line parsing
        result = {}
        # Paid By
        m = re.search(r"Paid By: (.+)", text)
        if m:
            result["paid_by"] = m.group(1).strip()
        # Placed By
        m = re.search(r"Placed By: (.+)", text)
        if m:
            result["placed_by"] = m.group(1).strip()
        # Order Number
        m = re.search(r"Amazon.com order number: ([\d-]+)", text)
        if m:
            result["order_number"] = m.group(1).strip()
        # Order Total
        m = re.search(r"Order Total: \$([\d\.,]+)", text)
        if m:
            result["order_total"] = AmazonInvoicePDFParser.parse_amount(m.group(1))
        # Order Placed
        m = re.search(r"Order Placed: ([A-Za-z]+ \d{1,2}, \d{4})", text)
        if m:
            result["order_placed"] = AmazonInvoicePDFParser.to_iso_date(
                m.group(1).strip()
            )
        # Shipped on
        m = re.search(r"Shipped on ([A-Za-z]+ \d{1,2}, \d{4})", text)
        if m:
            result["shipped_date"] = AmazonInvoicePDFParser.to_iso_date(
                m.group(1).strip()
            )
        # Shipping Address
        m = re.search(r"Shipping Address:\n([\s\S]+?)\nShipping Speed:", text)
        if m:
            result["shipping_address"] = m.group(1).strip()
        # Payment info
        m = re.search(r"Payment information\n([\s\S]+?)To view the status", text)
        if m:
            payment_block = m.group(1)
            m2 = re.search(
                r"([A-Za-z ]+) ending in (\d+): ([A-Za-z]+ \d{1,2}, \d{4}): \$([\d\.,]+)",
                payment_block,
            )
            if m2:
                result["payment_method"] = m2.group(1).strip() + " " + m2.group(2)
                result["payment_date"] = AmazonInvoicePDFParser.to_iso_date(
                    m2.group(3).strip()
                )
                result["payment_amount"] = AmazonInvoicePDFParser.parse_amount(
                    m2.group(4)
                )
        # Items Ordered (extract the whole block as a string)
        m = re.search(r"Items Ordered\s*Price\n([\s\S]+?)\nShipping Address:", text)
        items_block = None
        if m:
            items_block = m.group(1).strip()
            result["items_ordered_block"] = items_block
            # Find all items: look for patterns like 'n of: ... $amount'
            item_pattern = re.compile(r"(\d+) of:([\s\S]+?)(?=\d+ of:|$)")
            items = []
            descriptions = []
            for match in item_pattern.finditer(items_block):
                qty = match.group(1).strip()
                item_text = match.group(2).strip()
                # Find the last $amount in the item_text
                price_match = re.findall(r"\$([\d\.,]+)", item_text)
                price = float(price_match[-1].replace(",", "")) if price_match else None
                # Remove price from description
                desc = re.sub(r"\$[\d\.,]+", "", item_text).strip()
                # Remove trailing seller/supplied/condition lines if present
                desc = re.sub(
                    r"(Sold by:.*|Supplied by:.*|Condition:.*)", "", desc
                ).strip()
                items.append({"quantity": qty, "description": desc, "price": price})
                descriptions.append(desc)
            if items:
                result["items"] = items
                # Set main description as all item descriptions joined
                result["item_description"] = "; ".join(descriptions)
            else:
                # fallback: use the full block as description
                result["item_description"] = items_block
        return result

    @classmethod
    def parse_file(cls, file_path: str, **kwargs) -> ParserOutput:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([p.extract_text() or "" for p in reader.pages])
        fields = cls.parse_invoice_text(text)
        # Build transaction
        description = fields.get("item_description")
        if not description or not isinstance(description, str):
            description = "Amazon Invoice"
        transaction = TransactionRecord(
            transaction_date=fields.get("order_placed"),
            amount=fields.get("order_total"),
            description=description,
            transaction_type="Amazon Invoice",
            extra={
                "paid_by": fields.get("paid_by"),
                "placed_by": fields.get("placed_by"),
                "order_number": fields.get("order_number"),
                "item_price": fields.get("item_price"),
                "payment_method": fields.get("payment_method"),
                "payment_date": fields.get("payment_date"),
                "payment_amount": fields.get("payment_amount"),
                "shipping_address": fields.get("shipping_address"),
                "shipped_date": fields.get("shipped_date"),
                "source_file": Path(file_path).name,
                "file_path": str(file_path),
                "source": "amazon_invoice_pdf",
                "items_ordered": fields.get("items_ordered"),
                "items": fields.get("items"),
                "items_ordered_block": fields.get("items_ordered_block"),
            },
        )
        metadata = StatementMetadata(
            parser_name=cls.parser_name,
            parser_version=cls.parser_version,
            original_filename=Path(file_path).name,
            extra={
                "order_number": fields.get("order_number"),
                "order_total": fields.get("order_total"),
                "order_placed": fields.get("order_placed"),
                "shipped_date": fields.get("shipped_date"),
                "paid_by": fields.get("paid_by"),
                "placed_by": fields.get("placed_by"),
                "shipping_address": fields.get("shipping_address"),
            },
        )
        output = ParserOutput(
            transactions=[_replace_nan_with_none(transaction.model_dump())],
            metadata=metadata,
            schema_version="1.0",
        )
        # Final contract validation as in other parsers
        try:
            ParserOutput.model_validate(output.model_dump())
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            msg = f"Final ParserOutput validation error: {e}\n{tb}"
            output.errors = [msg]
            print(msg)
            raise
        return output

    def normalize_data(self, raw_data):
        """
        Contract-compliant normalization: returns a list of transaction dicts for downstream use.
        Accepts either a ParserOutput or a list of dicts.
        """
        if hasattr(raw_data, "transactions"):
            # If raw_data is a ParserOutput, extract transactions as dicts
            return [
                t if isinstance(t, dict) else t.model_dump()
                for t in raw_data.transactions
            ]
        return raw_data


def _replace_nan_with_none(obj):
    """Recursively replace NaN/np.nan/float('nan') with None in dicts/lists/values."""
    import math

    try:
        import numpy as np
    except ImportError:
        np = None
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if np is not None and obj == np.nan:
            return None
    if isinstance(obj, dict):
        return {k: _replace_nan_with_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan_with_none(v) for v in obj]
    return obj


ParserRegistry.register_parser(
    AmazonInvoicePDFParser.parser_name, AmazonInvoicePDFParser
)


def main(input_path: str) -> ParserOutput:
    """
    Canonical entrypoint for contract-based integration. Parses a single Amazon Invoice PDF and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    """
    parser = AmazonInvoicePDFParser()
    return parser.parse_file(input_path)


# --- TEST: Contract Adherence ---
if __name__ == "__main__":
    import sys

    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_file:
        print("Usage: python amazon_invoice_pdf_parser.py <pdf_file>")
        sys.exit(1)
    parser = AmazonInvoicePDFParser()
    output = parser.parse_file(test_file)
    # Validate contract
    try:
        ParserOutput.model_validate(output.model_dump())
        print("[PASS] ParserOutput contract validated.")
        # Print transaction_date for inspection
        for tx in output.transactions:
            print(
                "transaction_date:",
                tx["transaction_date"] if isinstance(tx, dict) else tx.transaction_date,
            )
    except Exception as e:
        print("[FAIL] ParserOutput contract validation failed:", e)
        sys.exit(2)
