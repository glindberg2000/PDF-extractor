"""Transaction normalizer for aggregating bank outputs into a single CSV."""

import os
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging
import re
from .data_transformation import apply_transformation_map
from .config import TRANSFORMATION_MAPS

logger = logging.getLogger(__name__)


class TransactionNormalizer:
    """Normalizes and aggregates transactions from different bank outputs.

    If dump_per_statement is True, writes a normalized CSV for each input statement file
    (containing only valid rows) to output/normalized_per_statement/.
    """

    def __init__(self, client_name: str, dump_per_statement: bool = False):
        self.client_name = client_name
        self.output_dir = os.path.join("data", "clients", client_name, "output")
        self.problem_rows = []  # Store tuples of (row_dict, reason)
        self.dump_per_statement = dump_per_statement
        if self.dump_per_statement:
            self.per_statement_dir = os.path.join(
                self.output_dir, "normalized_per_statement"
            )
            os.makedirs(self.per_statement_dir, exist_ok=True)

    def get_problem_rows(self):
        """Return a DataFrame of problem rows with reasons."""
        if not self.problem_rows:
            return pd.DataFrame()
        return pd.DataFrame(
            [{**row, "problem_reason": reason} for row, reason in self.problem_rows]
        )

    def _is_valid_row(self, row):
        # Check required fields are present and valid
        required = ["transaction_date", "description", "amount"]
        for field in required:
            value = row.get(field, None)
            if (
                value is None
                or (isinstance(value, float) and pd.isna(value))
                or str(value).strip() == ""
            ):
                return False, f"Missing or invalid field: {field}"
            if field == "transaction_date":
                # Must be a string in YYYY-MM-DD or similar format
                if not isinstance(value, str):
                    return False, f"transaction_date is not a string: {value}"
                try:
                    pd.to_datetime(value)
                except Exception:
                    return False, f"transaction_date not parseable: {value}"
            if field == "amount":
                try:
                    float(value)
                except Exception:
                    return False, f"amount not parseable: {value}"
        return True, None

    def normalize_date(self, date_str, row=None):
        """Normalize a date string to a pandas datetime object."""
        if pd.isna(date_str):
            if (
                row is not None
                and "description" in row
                and "INTEREST CREDIT" in str(row["description"])
                and "statement_end_date" in row
                and not pd.isna(row["statement_end_date"])
            ):
                # For interest credits with missing dates, use the statement end date if available
                return pd.to_datetime(
                    row["statement_end_date"], format="%Y-%m-%d", errors="coerce"
                )
            return pd.NaT

        # For interest credits, always use the statement end date
        if (
            row is not None
            and "description" in row
            and "INTEREST CREDIT" in str(row["description"])
            and "statement_end_date" in row
            and not pd.isna(row["statement_end_date"])
        ):
            return pd.to_datetime(
                row["statement_end_date"], format="%Y-%m-%d", errors="coerce"
            )

        # Try to parse the date string directly first
        try:
            date = pd.to_datetime(date_str)
            if not pd.isna(date):
                return date
        except:
            pass

        # If that fails, try specific formats
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
        for fmt in formats:
            try:
                date = pd.to_datetime(date_str, format=fmt, errors="coerce")
                if not pd.isna(date):
                    return date
            except:
                continue

        return pd.NaT

    def normalize_transactions(self) -> pd.DataFrame:
        """Aggregate and normalize all transaction files into a single DataFrame. Only valid rows are included in the output. Problem rows are stored for review.
        If dump_per_statement is True, also writes a normalized CSV for each input statement file (valid rows only).
        Interest credit date logic is only applied if 'statement_end_date' exists.
        """
        all_transactions = []
        self.problem_rows = []  # Reset for each run

        # Find all CSV files in the output directory
        for file in os.listdir(self.output_dir):
            if file.endswith("_output.csv"):
                file_path = os.path.join(self.output_dir, file)
                try:
                    # Read CSV with all columns as strings initially
                    df = pd.read_csv(file_path, dtype=str)
                    logger.info(f"Loaded {len(df)} rows from {file}")
                    logger.info(f"Columns in {file}: {df.columns.tolist()}")

                    # Get source name from file
                    source = file.replace("_output.csv", "")

                    # Add source column if not present
                    if "source" not in df.columns:
                        df["source"] = source

                    # Reset index to avoid duplicate indices
                    df = df.reset_index(drop=True)

                    # Apply transformation map if available
                    if source in TRANSFORMATION_MAPS:
                        logger.info(f"Applying transformation map for {source}")
                        logger.info(
                            f"Transformation map: {TRANSFORMATION_MAPS[source]}"
                        )
                        logger.info(
                            f"Available columns before transform: {df.columns.tolist()}"
                        )

                        # Create a new DataFrame with transformed columns
                        transformed_df = pd.DataFrame()
                        transform_map = TRANSFORMATION_MAPS[source]

                        for target_col, source_col in transform_map.items():
                            if callable(source_col):
                                transformed_df[target_col] = df.apply(
                                    source_col, axis=1
                                )
                            elif source_col in df.columns:
                                transformed_df[target_col] = df[source_col]
                            else:
                                logger.warning(
                                    f"Column {source_col} not found in source data for {target_col}"
                                )

                        df = transformed_df
                        logger.info(f"Columns after transform: {df.columns.tolist()}")

                    # Log any rows with missing required columns
                    required_cols = ["transaction_date", "description", "amount"]
                    missing_cols = [
                        col for col in required_cols if col not in df.columns
                    ]
                    if missing_cols:
                        logger.error(
                            f"Missing required columns in {file}: {missing_cols}"
                        )
                        logger.error(f"Available columns: {df.columns.tolist()}")
                        continue

                    # Log any rows with missing transaction dates
                    missing_dates = df["transaction_date"].isna().sum()
                    if missing_dates > 0:
                        logger.warning(
                            f"Found {missing_dates} rows with missing dates in {file}"
                        )
                        # Log the problematic rows
                        problematic_rows = df[df["transaction_date"].isna()]
                        for _, row in problematic_rows.iterrows():
                            logger.warning(f"Row with missing date: {row.to_dict()}")
                            # For interest credits with missing dates, use the statement end date
                            if (
                                "description" in row
                                and "INTEREST CREDIT" in str(row["description"])
                                and "statement_end_date" in row
                                and not pd.isna(row["statement_end_date"])
                            ):
                                df.loc[row.name, "transaction_date"] = row[
                                    "statement_end_date"
                                ]

                    # Add file_path if not present
                    if "file_path" not in df.columns:
                        df["file_path"] = file_path

                    # Convert dates and amounts
                    if "transaction_date" in df.columns:
                        df["normalized_date"] = df.apply(
                            lambda row: self.normalize_date(
                                row["transaction_date"], row
                            ),
                            axis=1,
                        )
                        # Count and log rows with NaT dates
                        nat_count = df["normalized_date"].isna().sum()
                        if nat_count > 0:
                            logger.warning(
                                f"Warning: {nat_count} rows have invalid dates in {file}"
                            )
                            # Log the problematic rows
                            problematic_rows = df[df["normalized_date"].isna()]
                            for _, row in problematic_rows.iterrows():
                                logger.warning(
                                    f"Row with missing date: {row.to_dict()}"
                                )
                                # For interest credits with missing dates, use the statement end date
                                if (
                                    "description" in row
                                    and "INTEREST CREDIT" in str(row["description"])
                                    and "statement_end_date" in row
                                    and not pd.isna(row["statement_end_date"])
                                ):
                                    df.loc[row.name, "normalized_date"] = (
                                        pd.to_datetime(
                                            row["statement_end_date"],
                                            format="%Y-%m-%d",
                                            errors="coerce",
                                        )
                                    )
                    else:
                        logger.warning(
                            f"Warning: 'transaction_date' column not found in {file}"
                        )
                        logger.warning(f"Available columns: {df.columns.tolist()}")

                    if "amount" in df.columns:
                        df["normalized_amount"] = pd.to_numeric(
                            df["amount"].str.replace("$", "").str.replace(",", ""),
                            errors="coerce",
                        )
                    else:
                        logger.warning(f"Warning: 'amount' column not found in {file}")

                    # After transformation, strict validation for this file
                    valid_rows = []
                    for row in df.to_dict(orient="records"):
                        is_valid, reason = self._is_valid_row(row)
                        if is_valid:
                            valid_rows.append(row)
                        else:
                            self.problem_rows.append((row, f"{file}: {reason}"))
                            logger.warning(
                                f"Dropping invalid row from {file}: {reason} | Data: {row}"
                            )
                    valid_df = pd.DataFrame(valid_rows)
                    all_transactions.append(valid_df)

                    # Dump per-statement file if enabled
                    if self.dump_per_statement:
                        out_name = os.path.splitext(file)[0] + "_normalized.csv"
                        out_path = os.path.join(self.per_statement_dir, out_name)
                        valid_df.to_csv(out_path, index=False)
                        logger.info(f"Wrote per-statement normalized file: {out_path}")

                except Exception as e:
                    logger.error(f"Error loading {file}: {e}")

        if not all_transactions:
            logger.warning("No transaction files found to normalize")
            return pd.DataFrame()

        # Combine all valid transactions
        combined_df = pd.concat(all_transactions, ignore_index=True)

        # Add a unique transaction ID
        combined_df["transaction_id"] = combined_df.index + 1

        # Ensure required columns exist
        required_columns = ["transaction_date", "description", "amount", "source"]
        for col in required_columns:
            if col not in combined_df.columns:
                logger.error(f"Missing required column: {col}")
                return pd.DataFrame()

        # Use normalized_date as transaction_date if available
        if "normalized_date" in combined_df.columns:
            # Only apply interest credit logic if 'statement_end_date' exists
            if "statement_end_date" in combined_df.columns:
                interest_credits = combined_df["description"].str.contains(
                    "INTEREST CREDIT", na=False
                )
                combined_df.loc[interest_credits, "transaction_date"] = combined_df.loc[
                    interest_credits, "statement_end_date"
                ]
            else:
                logger.warning(
                    "'statement_end_date' column not found; skipping interest credit date logic."
                )
            # For other transactions, use normalized date
            if "normalized_date" in combined_df.columns:
                other_transactions = ~combined_df["description"].str.contains(
                    "INTEREST CREDIT", na=False
                )
                combined_df.loc[other_transactions, "transaction_date"] = (
                    combined_df.loc[other_transactions, "normalized_date"].apply(
                        lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None
                    )
                )
            # Ensure all dates are in YYYY-MM-DD format
            combined_df["transaction_date"] = pd.to_datetime(
                combined_df["transaction_date"], format="%Y-%m-%d", errors="coerce"
            ).apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)

        # Log the final DataFrame shape and source counts
        logger.info(f"Final DataFrame shape: {combined_df.shape}")
        source_counts = combined_df["source"].value_counts()
        logger.info(f"Transactions per source:\n{source_counts}")

        # Final strict validation: filter out invalid/problem rows
        valid_rows = []
        for row in combined_df.to_dict(orient="records"):
            is_valid, reason = self._is_valid_row(row)
            if is_valid:
                valid_rows.append(row)
            else:
                self.problem_rows.append((row, reason))
                logger.warning(f"Dropping invalid row: {reason} | Data: {row}")
        valid_df = pd.DataFrame(valid_rows)
        logger.info(
            f"Valid rows: {len(valid_df)} | Problem rows: {len(self.problem_rows)}"
        )

        # Save valid transactions
        output_file = os.path.join(
            self.output_dir, f"{self.client_name}_normalized_transactions.csv"
        )
        valid_df.to_csv(output_file, index=False)
        logger.info(f"Saved normalized transactions to {output_file}")

        return valid_df

    def _normalize_description(self, description: str) -> str:
        """Normalize transaction description by removing common patterns and standardizing format."""
        if pd.isna(description):
            return ""

        # Convert to string and clean
        desc = str(description).strip()

        # Remove common patterns
        patterns_to_remove = [
            r"POS\s+DEBIT\s+\d+",  # POS DEBIT numbers
            r"ACH\s+DEBIT\s+\d+",  # ACH DEBIT numbers
            r"ACH\s+CREDIT\s+\d+",  # ACH CREDIT numbers
            r"POS\s+CREDIT\s+\d+",  # POS CREDIT numbers
            r"\d{4}\*",  # Card numbers
            r"REF\s*\d+",  # Reference numbers
            r"TRANS\s*\d+",  # Transaction numbers
            r"PURCHASE\s+AUTH\s+\d+",  # Purchase authorization numbers
        ]

        for pattern in patterns_to_remove:
            desc = re.sub(pattern, "", desc, flags=re.IGNORECASE)

        # Clean up whitespace
        desc = " ".join(desc.split())

        return desc
