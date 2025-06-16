import os
import re
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)
import math
import numpy as np
import PyPDF2


class AmazonPDFParser(BaseParser):
    """
    Parser for Amazon Orders PDF exports (webpage print-to-PDF).
    """

    name = "amazon_pdf"
    description = "Parser for Amazon Orders PDF exports."
    file_types = [".pdf"]

    @staticmethod
    def extract_text(input_path: str) -> str:
        text = ""
        with open(input_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text

    @staticmethod
    def parse_amount(amount_str):
        try:
            return float(amount_str.replace("$", "").replace(",", "").strip())
        except Exception:
            return 0.0

    @staticmethod
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str.strip(), "%B %d, %Y").strftime("%Y-%m-%d")
        except Exception:
            return None

    def parse_file(
        self, input_path: str, config: dict = None, original_filename: str = None
    ) -> list[dict]:
        text = self.extract_text(input_path)
        # Split into orders by 'ORDER PLACED'
        order_blocks = re.split(r"ORDER PLACED", text)[1:]  # skip preamble
        records = []
        for block in order_blocks:
            # Extract order date
            date_match = re.search(r"^([A-Za-z]+ \d{1,2}, \d{4})", block.lstrip())
            if not date_match:
                # fallback: look for the date anywhere in the first 40 chars
                date_match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})", block[:40])
            order_date = self.parse_date(date_match.group(1)) if date_match else None
            # Extract total
            total_match = re.search(r"TOTAL\n\$([\d\.,]+)", block)
            amount = self.parse_amount(total_match.group(1)) if total_match else 0.0
            # Extract order number
            ordernum_match = re.search(r"ORDER # ([\d\-]+)", block)
            order_number = ordernum_match.group(1) if ordernum_match else None
            # Extract ship to (optional)
            shipto_match = re.search(r"SHIP TO\n([A-Za-z ]+)", block)
            ship_to = shipto_match.group(1).strip() if shipto_match else None
            # Extract product lines (first non-empty lines after 'View order details' or 'View invoice')
            product_lines = []
            prod_section = re.split(
                r"View order details|View invoice", block, maxsplit=1
            )
            if len(prod_section) > 1:
                lines = prod_section[1].split("\n")
                for line in lines:
                    if (
                        line.strip()
                        and not line.strip().startswith("Return")
                        and not line.strip().startswith("Buy it again")
                        and not line.strip().startswith("Get product support")
                        and not line.strip().startswith("Write a product review")
                        and not line.strip().startswith("Ask Product Question")
                    ):
                        product_lines.append(line.strip())
                    if len(product_lines) >= 3:
                        break
            description = product_lines[0] if product_lines else "Amazon Order"
            records.append(
                {
                    "transaction_date": order_date,
                    "amount": amount,
                    "description": description,
                    "order_number": order_number,
                    "ship_to": ship_to,
                    "product_lines": product_lines,
                    "source_file": os.path.basename(input_path),
                    "file_path": input_path,
                    "file_name": os.path.basename(input_path),
                    "source": self.name,
                }
            )
        return records

    def normalize_data(self, raw_data: list[dict]) -> list[dict]:
        # For Amazon, just return as DataFrame for contract
        return raw_data


ParserRegistry.register_parser(AmazonPDFParser.name, AmazonPDFParser)


def _replace_nan_with_none(obj):
    """Recursively replace NaN/np.nan/float('nan') with None in dicts/lists/values."""
    if isinstance(obj, float) and (math.isnan(obj) or obj == np.nan):
        return None
    if isinstance(obj, dict):
        return {k: _replace_nan_with_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan_with_none(v) for v in obj]
    return obj


def main(input_path: str) -> ParserOutput:
    """
    Canonical entrypoint for contract-based integration. Parses a single Amazon Orders PDF and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    All transaction_date and metadata date fields are normalized to YYYY-MM-DD format.
    """
    errors = []
    warnings = []
    try:
        parser = AmazonPDFParser()
        raw_data = parser.parse_file(
            input_path, original_filename=os.path.basename(input_path)
        )
        transactions = []
        for idx, row in enumerate(raw_data):
            try:
                t_date = row.get("transaction_date")
                if t_date:
                    try:
                        t_date = datetime.strptime(t_date, "%Y-%m-%d").strftime(
                            "%Y-%m-%d"
                        )
                    except Exception:
                        warnings.append(
                            f"[WARN] Could not normalize transaction_date '{t_date}' at row {idx} in {input_path}"
                        )
                        t_date = None
                tr = TransactionRecord(
                    transaction_date=t_date,
                    amount=row.get("amount"),
                    description=row.get("description"),
                    posted_date=None,
                    transaction_type="Amazon Order",
                    extra={
                        k: v
                        for k, v in row.items()
                        if k
                        not in [
                            "transaction_date",
                            "amount",
                            "description",
                            "transaction_type",
                        ]
                    },
                )
                transactions.append(tr)
            except Exception as e:
                import traceback

                tb = traceback.format_exc()
                msg = f"TransactionRecord validation error at row {idx} in {input_path}: {e}\n{tb}"
                errors.append(msg)
        # Use the year from the first transaction as metadata
        year = None
        if transactions and transactions[0].transaction_date:
            year = transactions[0].transaction_date[:4]
        metadata = StatementMetadata(
            statement_date=None,
            statement_period_start=f"{year}-01-01" if year else None,
            statement_period_end=f"{year}-12-31" if year else None,
            statement_date_source="first_transaction_year" if year else None,
            original_filename=os.path.basename(input_path),
            account_number=None,
            bank_name="Amazon",
            account_type="Credit Card",
            parser_name="amazon_pdf",
            parser_version=None,
            currency="USD",
            extra=None,
        )
        output = ParserOutput(
            transactions=transactions,
            metadata=metadata,
            schema_version="1.0",
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
        )
        try:
            ParserOutput.model_validate(output.model_dump())
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            msg = f"Final ParserOutput validation error: {e}\n{tb}"
            errors.append(msg)
            output.errors = errors
            raise
        output_dict = output.model_dump()
        output_dict = _replace_nan_with_none(output_dict)
        print("[DEBUG] Cleaned ParserOutput sample:", output_dict)
        return ParserOutput.model_validate(output_dict)
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        msg = f"[FATAL] Error in main() for {input_path}: {e}\n{tb}"
        print(msg)
        return ParserOutput(
            transactions=[],
            metadata=None,
            schema_version="1.0",
            errors=[msg],
            warnings=None,
        )
