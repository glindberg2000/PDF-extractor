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
    transformed_df = pd.DataFrame()

    for target_col, source_col in transformation_map.items():
        if callable(source_col):
            # Apply the lambda function to the DataFrame
            transformed_df[target_col] = df.apply(lambda row: source_col(row), axis=1)
        else:
            # Directly map the source column to the target column
            transformed_df[target_col] = df[source_col]

    return transformed_df
