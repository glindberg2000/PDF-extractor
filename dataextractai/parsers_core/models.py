from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class TransactionRecord(BaseModel):
    """
    Represents a single transaction extracted from a statement.
    Only raw transaction data fields are included; no context or metadata.
    """

    transaction_date: str = Field(
        ..., description="Transaction date in ISO 8601 format (YYYY-MM-DD)"
    )
    amount: float = Field(
        ...,
        description="Transaction amount (positive for debits, negative for credits, or as in source)",
    )
    description: str = Field(
        ..., description="Raw transaction description from the statement"
    )
    posted_date: Optional[str] = Field(
        None, description="Date transaction was posted, if available (ISO 8601)"
    )
    transaction_type: Optional[str] = Field(
        None,
        description="Type of transaction, e.g., 'debit', 'credit', if present in source",
    )
    extra: Optional[Dict] = Field(
        None, description="Parser/bank-specific or experimental fields"
    )


class StatementMetadata(BaseModel):
    """
    Statement-level metadata, not per-transaction. All fields are optional and may be omitted if not available.
    """

    statement_date: Optional[str] = Field(
        None, description="Statement end date (ISO 8601)"
    )
    statement_period_start: Optional[str] = Field(
        None, description="Statement period start date (ISO 8601)"
    )
    statement_period_end: Optional[str] = Field(
        None, description="Statement period end date (ISO 8601)"
    )
    statement_date_source: Optional[str] = Field(
        None,
        description="Where the statement date was extracted from (e.g., 'content', 'filename', 'last_row')",
    )
    original_filename: Optional[str] = Field(
        None, description="Original uploaded filename, if available"
    )
    account_number: Optional[str] = Field(
        None, description="Account number for the statement, if available"
    )
    bank_name: Optional[str] = Field(
        None, description="Bank name, e.g., 'Chase', 'Capital One'"
    )
    account_type: Optional[str] = Field(
        None, description="Account type, e.g., 'checking', 'savings', 'VISA'"
    )
    parser_name: Optional[str] = Field(None, description="Name of the parser used")
    parser_version: Optional[str] = Field(
        None, description="Version of the parser used"
    )
    currency: Optional[str] = Field("USD", description="Currency code, default 'USD'")
    extra: Optional[Dict] = Field(
        None, description="Parser/bank-specific or experimental metadata fields"
    )


class ParserOutput(BaseModel):
    """
    Canonical output structure for all modularized parsers.
    - transactions: List of TransactionRecord (raw transaction data only)
    - metadata: Statement-level metadata (optional)
    - schema_version: Output schema version (default '1.0')
    - errors: List of error messages (optional)
    - warnings: List of warning messages (optional)
    """

    transactions: List[TransactionRecord] = Field(
        ..., description="List of extracted transactions"
    )
    metadata: Optional[StatementMetadata] = Field(
        None, description="Statement-level metadata"
    )
    schema_version: Optional[str] = Field("1.0", description="Output schema version")
    errors: Optional[List[str]] = Field(
        None, description="List of error messages encountered during parsing"
    )
    warnings: Optional[List[str]] = Field(
        None, description="List of warning messages encountered during parsing"
    )
