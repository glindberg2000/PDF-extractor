"""
data_transformation.py

This script contains the function to transform various financial DataFrames into
a unified core data structure.

Author: Gregory Lindberg
Date: November 5, 2023
"""

import pandas as pd
from dataextractai.utils.config import DATA_MANIFESTS
from dataextractai.utils.config import TRANSFORMATION_MAPS


def apply_transformation_map(df, source):
    transformation_map = TRANSFORMATION_MAPS[source]
    transformed_df = df.copy()  # Start with a copy of the original DataFrame

    for target_col, source_col in transformation_map.items():
        if callable(source_col):
            # Apply the lambda function to the DataFrame
            transformed_df[target_col] = df.apply(lambda row: source_col(row), axis=1)
        else:
            # Directly map the source column to the target column
            transformed_df[target_col] = df[source_col]

    return transformed_df


def normalize_transaction_amount(
    amount: float, transaction_type: str, is_charge_positive: bool = False
) -> float:
    """
    Normalizes a transaction amount based on its type to enforce the convention:
    - Expenses/Debits/Charges are negative.
    - Income/Credits/Payments are positive.

    Args:
        amount (float): The original transaction amount.
        transaction_type (str): The type of transaction (e.g., 'debit', 'credit', 'charge', 'payment').
        is_charge_positive (bool): Flag for sources where charges are positive and credits are negative
                                     (e.g., Apple Card). If True, the logic is inverted.

    Returns:
        float: The normalized amount with the correct sign.
    """
    if amount is None:
        return 0.0

    from decimal import Decimal, InvalidOperation

    try:
        amount_dec = Decimal(str(amount))
    except InvalidOperation:
        return 0.0

    # Ensure amount is absolute before applying logic, except when it's already correct
    # For standard bank accounts, debits are often already negative.
    # We will assume the input 'amount' reflects the source file.

    charge_keywords = ["debit", "charge", "withdrawal", "purchase"]
    credit_keywords = ["credit", "payment", "deposit", "income"]

    # Lowercase for case-insensitive matching
    ttype_lower = transaction_type.lower()

    is_charge = any(keyword in ttype_lower for keyword in charge_keywords)
    is_credit = any(keyword in ttype_lower for keyword in credit_keywords)

    if is_charge_positive:
        # Inverted logic (Apple Card, Capital One)
        # Charges are positive in the file, should be negative.
        # Credits are negative in the file, should be positive.
        return float(-amount_dec)
    else:
        # Standard logic
        if is_charge and amount_dec > 0:
            return float(-amount_dec)
        if is_credit and amount_dec < 0:
            return float(-amount_dec)  # Make credits positive

    return float(amount_dec)
