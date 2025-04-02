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
    """Normalizes and aggregates transactions from different bank outputs."""

    def __init__(self, client_name: str):
        self.client_name = client_name
        self.output_dir = os.path.join("data", "clients", client_name, "output")
        self._transaction_counter = 0  # Counter for generating unique IDs

    def _generate_transaction_id(self, source: str, index: int) -> str:
        """Generate a unique transaction ID that includes the source."""
        self._transaction_counter += 1
        return f"{source}_{self._transaction_counter}"

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
        """Aggregate and normalize all transaction files into a single DataFrame."""
        all_transactions = []

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

                    # Reset index to avoid duplicate indices
                    df = df.reset_index(drop=True)

                    # Add transaction_id if not present
                    if "transaction_id" not in df.columns:
                        df["transaction_id"] = [
                            self._generate_transaction_id(source, i)
                            for i in range(len(df))
                        ]

                    # Ensure source is set (do this before transformations)
                    df["source"] = source

                    # Add file_path if not present
                    if "file_path" not in df.columns:
                        df["file_path"] = file_path

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

                    # Convert dates and amounts
                    if "transaction_date" in df.columns:
                        df["normalized_date"] = df.apply(
                            lambda row: self.normalize_date(
                                row["transaction_date"], row
                            ),
                            axis=1,
                        )
                        # Handle invalid dates
                        invalid_dates = df["normalized_date"].isna()
                        if invalid_dates.any():
                            logger.warning(
                                f"Found {invalid_dates.sum()} invalid dates in {file}"
                            )
                            # For invalid dates, try to use statement dates
                            for idx in df[invalid_dates].index:
                                row = df.loc[idx]
                                logger.warning(f"Invalid date in row: {row.to_dict()}")

                                # Try to use statement end date first
                                if "statement_end_date" in row and pd.notnull(
                                    row["statement_end_date"]
                                ):
                                    df.loc[idx, "normalized_date"] = pd.to_datetime(
                                        row["statement_end_date"],
                                        format="%Y-%m-%d",
                                        errors="coerce",
                                    )
                                    logger.info(
                                        f"Using statement end date {row['statement_end_date']} for transaction"
                                    )
                                # Then try statement start date
                                elif "statement_start_date" in row and pd.notnull(
                                    row["statement_start_date"]
                                ):
                                    df.loc[idx, "normalized_date"] = pd.to_datetime(
                                        row["statement_start_date"],
                                        format="%Y-%m-%d",
                                        errors="coerce",
                                    )
                                    logger.info(
                                        f"Using statement start date {row['statement_start_date']} for transaction"
                                    )

                        # Use normalized dates
                        df.loc[:, "transaction_date"] = df["normalized_date"].apply(
                            lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None
                        )
                        df = df.drop("normalized_date", axis=1)
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

                    all_transactions.append(df)
                    logger.info(
                        f"Successfully processed {len(df)} transactions from {file}"
                    )
                except Exception as e:
                    logger.error(f"Error loading {file}: {e}")

        if not all_transactions:
            logger.warning("No transaction files found to normalize")
            return pd.DataFrame()

        # Combine all transactions
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
            # For interest credits, use statement end date
            interest_credits = combined_df["description"].str.contains(
                "INTEREST CREDIT", na=False
            )
            combined_df.loc[interest_credits, "transaction_date"] = combined_df.loc[
                interest_credits, "statement_end_date"
            ]

            # For other transactions, use normalized date
            other_transactions = ~interest_credits
            combined_df.loc[other_transactions, "transaction_date"] = combined_df.loc[
                other_transactions, "normalized_date"
            ].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)

            # Ensure all dates are in YYYY-MM-DD format
            combined_df["transaction_date"] = pd.to_datetime(
                combined_df["transaction_date"], format="%Y-%m-%d", errors="coerce"
            ).apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)

            # Double-check interest credits and set their dates to statement end date
            interest_credits = combined_df["description"].str.contains(
                "INTEREST CREDIT", na=False
            )
            combined_df.loc[interest_credits, "transaction_date"] = combined_df.loc[
                interest_credits, "statement_end_date"
            ].apply(
                lambda x: (
                    pd.to_datetime(x, format="%Y-%m-%d", errors="coerce").strftime(
                        "%Y-%m-%d"
                    )
                    if pd.notnull(x)
                    else None
                )
            )

            # Log any rows with missing transaction dates
            missing_dates = combined_df["transaction_date"].isna().sum()
            if missing_dates > 0:
                logger.warning(f"Found {missing_dates} rows with missing dates")
                # Log the problematic rows
                problematic_rows = combined_df[combined_df["transaction_date"].isna()]
                for _, row in problematic_rows.iterrows():
                    logger.warning(f"Row with missing date: {row.to_dict()}")
                    # For interest credits with missing dates, use the statement end date
                    if (
                        "description" in row
                        and "INTEREST CREDIT" in str(row["description"])
                        and "statement_end_date" in row
                        and not pd.isna(row["statement_end_date"])
                    ):
                        combined_df.loc[row.name, "transaction_date"] = pd.to_datetime(
                            row["statement_end_date"],
                            format="%Y-%m-%d",
                            errors="coerce",
                        ).strftime("%Y-%m-%d")

            # Final check for interest credits
            interest_credits = combined_df["description"].str.contains(
                "INTEREST CREDIT", na=False
            )
            for idx in combined_df[interest_credits].index:
                if pd.isna(combined_df.loc[idx, "transaction_date"]):
                    combined_df.loc[idx, "transaction_date"] = combined_df.loc[
                        idx, "statement_end_date"
                    ]

            # Final check for any remaining missing dates
            missing_dates = combined_df["transaction_date"].isna().sum()
            if missing_dates > 0:
                logger.warning(
                    f"Found {missing_dates} rows with missing dates after all checks"
                )
                # Log the problematic rows
                problematic_rows = combined_df[combined_df["transaction_date"].isna()]
                for _, row in problematic_rows.iterrows():
                    logger.warning(f"Row with missing date: {row.to_dict()}")
                    # For interest credits with missing dates, use the statement end date
                    if (
                        "description" in row
                        and "INTEREST CREDIT" in str(row["description"])
                        and "statement_end_date" in row
                        and not pd.isna(row["statement_end_date"])
                    ):
                        combined_df.loc[row.name, "transaction_date"] = row[
                            "statement_end_date"
                        ]
                        # Double-check that the date was set
                        if pd.isna(combined_df.loc[row.name, "transaction_date"]):
                            logger.warning(
                                f"Failed to set date for row: {row.to_dict()}"
                            )
                            logger.warning(
                                f"Statement end date: {row['statement_end_date']}"
                            )
                            logger.warning(
                                f"Current transaction date: {combined_df.loc[row.name, 'transaction_date']}"
                            )

            # Final check for any remaining missing dates
            missing_dates = combined_df["transaction_date"].isna().sum()
            if missing_dates > 0:
                logger.warning(
                    f"Found {missing_dates} rows with missing dates after all checks"
                )
                # Log the problematic rows
                problematic_rows = combined_df[combined_df["transaction_date"].isna()]
                for _, row in problematic_rows.iterrows():
                    logger.warning(f"Row with missing date: {row.to_dict()}")
                    # For interest credits with missing dates, use the statement end date
                    if (
                        "description" in row
                        and "INTEREST CREDIT" in str(row["description"])
                        and "statement_end_date" in row
                        and not pd.isna(row["statement_end_date"])
                    ):
                        # Try one last time to set the date
                        try:
                            date_str = row["statement_end_date"]
                            if pd.notnull(date_str):
                                combined_df.loc[row.name, "transaction_date"] = date_str
                                logger.warning(
                                    f"Successfully set date to {date_str} for row: {row.to_dict()}"
                                )
                        except Exception as e:
                            logger.error(f"Error setting date: {e}")
                            logger.error(f"Row: {row.to_dict()}")

            # Final check for any remaining missing dates
            missing_dates = combined_df["transaction_date"].isna().sum()
            if missing_dates > 0:
                logger.warning(
                    f"Found {missing_dates} rows with missing dates after all checks"
                )
                # Log the problematic rows
                problematic_rows = combined_df[combined_df["transaction_date"].isna()]
                for _, row in problematic_rows.iterrows():
                    logger.warning(f"Row with missing date: {row.to_dict()}")
                    # For interest credits with missing dates, use the statement end date
                    if (
                        "description" in row
                        and "INTEREST CREDIT" in str(row["description"])
                        and "statement_end_date" in row
                        and not pd.isna(row["statement_end_date"])
                    ):
                        # Try one last time to set the date
                        try:
                            date_str = row["statement_end_date"]
                            if pd.notnull(date_str):
                                combined_df.loc[row.name, "transaction_date"] = date_str
                                logger.warning(
                                    f"Successfully set date to {date_str} for row: {row.to_dict()}"
                                )
                        except Exception as e:
                            logger.error(f"Error setting date: {e}")
                            logger.error(f"Row: {row.to_dict()}")

            # Final check for any remaining missing dates
            missing_dates = combined_df["transaction_date"].isna().sum()
            if missing_dates > 0:
                logger.warning(
                    f"Found {missing_dates} rows with missing dates after all checks"
                )
                # Log the problematic rows
                problematic_rows = combined_df[combined_df["transaction_date"].isna()]
                for _, row in problematic_rows.iterrows():
                    logger.warning(f"Row with missing date: {row.to_dict()}")
                    # For interest credits with missing dates, use the statement end date
                    if (
                        "description" in row
                        and "INTEREST CREDIT" in str(row["description"])
                        and "statement_end_date" in row
                        and not pd.isna(row["statement_end_date"])
                    ):
                        # Try one last time to set the date
                        try:
                            date_str = row["statement_end_date"]
                            if pd.notnull(date_str):
                                combined_df.loc[row.name, "transaction_date"] = date_str
                                logger.warning(
                                    f"Successfully set date to {date_str} for row: {row.to_dict()}"
                                )
                        except Exception as e:
                            logger.error(f"Error setting date: {e}")
                            logger.error(f"Row: {row.to_dict()}")

            combined_df = combined_df.drop("normalized_date", axis=1)

        # Log the final DataFrame shape and source counts
        logger.info(f"Final DataFrame shape: {combined_df.shape}")
        source_counts = combined_df["source"].value_counts()
        logger.info(f"Transactions per source:\n{source_counts}")

        # Save normalized transactions
        output_file = os.path.join(
            self.output_dir, f"{self.client_name}_normalized_transactions.csv"
        )
        combined_df.to_csv(output_file, index=False)
        logger.info(f"Saved normalized transactions to {output_file}")

        return combined_df

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
