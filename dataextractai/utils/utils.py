# utils/utils.py

import re


def standardize_column_names(df):
    """
    Standardizes column names by:
    - Replacing spaces with underscores
    - Converting to lowercase
    - Removing special characters (except underscores)
    """
    df.columns = [re.sub(r"\W+", "_", col).strip("_").lower() for col in df.columns]
    return df
