"""
data_transformation.py

This script contains the function to transform various financial DataFrames into
a unified core data structure.

Author: Gregory Lindberg
Date: November 5, 2023
"""
import pandas as pd
from config import DATA_MANIFESTS
from config import TRANSFORMATION_MAPS


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

    # Initialize a dictionary to hold our transformed data
    transformed_data = {core_field: [] for core_field in transformation_map.values()}

    # Iterate over each row in the DataFrame
    for _, row in df.iterrows():
        # Apply the transformation map to each row
        for source_field, core_field in transformation_map.items():
            # If the value is callable, it's a function we need to apply to the row
            if callable(core_field):
                transformed_data[core_field].append(core_field(row))
            else:
                transformed_data[core_field].append(row[source_field])

    # Convert the transformed data dictionary to a DataFrame
    transformed_df = pd.DataFrame(transformed_data)

    return transformed_df
