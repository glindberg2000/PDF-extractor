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


# Define a function to normalize the amount based on the source
def normalize_amount(amount, source):
    # For bank statements, deposits are positive and withdrawals are negative
    # For credit cards and Amazon, spending is positive and payments/credits are negative
    # We want to normalize so that spending is always positive
    if (
        "_bank" in source or "amazon" in source
    ):  # Adjust this condition based on your data
        return -amount if amount < 0 else amount  # Inverts withdrawals to be positive
    else:
        return amount  # Spending on credit cards is already positive


def apply_transformation_map(df, source):
    transformation_map = TRANSFORMATION_MAPS[source]
    transformed_df = pd.DataFrame()

    for target_col, source_col in transformation_map.items():
        if callable(source_col):
            # Apply the lambda function to the DataFrame
            transformed_df[target_col] = df.apply(lambda row: source_col(row), axis=1)
        else:
            # Directly map the source column to the target column
            transformed_df[target_col] = df[source_col]

    return transformed_df
