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


class AmazonInvoicePDFParser(BaseParser):
    parser_name = "amazon_invoice_pdf"
    parser_version = "1.0"

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
            result["order_placed"] = m.group(1).strip()
        # Shipped on
        m = re.search(r"Shipped on ([A-Za-z]+ \d{1,2}, \d{4})", text)
        if m:
            result["shipped_date"] = m.group(1).strip()
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
                result["payment_date"] = m2.group(3).strip()
                result["payment_amount"] = AmazonInvoicePDFParser.parse_amount(
                    m2.group(4)
                )
        # Items Ordered
        m = re.search(r"Items OrderedPrice\n([\s\S]+?)\nShipping Address:", text)
        if m:
            items_block = m.group(1)
            # Take the first item as main
            lines = [l.strip() for l in items_block.split("\n") if l.strip()]
            if lines:
                result["item_description"] = lines[0]
                # Try to get price from the last line with a $ sign
                for l in reversed(lines):
                    if "$" in l:
                        result["item_price"] = AmazonInvoicePDFParser.parse_amount(l)
                        break
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
