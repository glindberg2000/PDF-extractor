# utils/utils.py

import re
import os
import pandas as pd

from dataextractai.utils.config import (
    PARSER_OUTPUT_PATHS,
    COMMON_CONFIG,
    PERSONAL_EXPENSES,
    EXPENSE_THRESHOLD,
)

CONSOLIDATED_BATCH_PATH = PARSER_OUTPUT_PATHS["consolidated_batched"]["csv"]


def standardize_column_names(df):
    """
    Standardizes column names by:
    - Replacing spaces with underscores
    - Converting to lowercase
    - Removing special characters (except underscores)
    """
    df.columns = [re.sub(r"\W+", "_", col).strip("_").lower() for col in df.columns]
    return df


def get_parent_dir_and_file(path):
    # This function returns the file name and one directory up
    parent_directory, filename = os.path.split(path)  # Split the path and the file
    parent_directory_name = os.path.basename(
        parent_directory
    )  # Get the name of the parent directory
    return os.path.join(
        parent_directory_name, filename
    )  # Combine the parent directory name with the file name


def create_directory_if_not_exists(directory_path):
    """
    Create a directory if it does not exist.

    :param directory_path: Path of the directory to be created.
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        print(f"New batch file created at {directory_path}")
    except Exception as e:
        print(f"An error occurred while creating the directory: {e}")


def filter_by_keywords(df, keywords, exclude=True):
    """
    Filter transactions based on keywords.

    :param df: DataFrame containing transactions.
    :param keywords: List of keywords to include or exclude.
    :param exclude: Boolean, when True excludes transactions with given keywords,
                    when False includes them.
    :return: DataFrame after filtering.
    """

    def keyword_filter(description):
        return any(keyword.lower() in description.lower() for keyword in keywords)

    if exclude:
        return df[~df["description"].apply(keyword_filter)]
    else:
        return df[df["description"].apply(keyword_filter)]


def filter_by_amount(df, threshold):
    """
    Exclude transactions below a certain amount threshold.

    :param df: DataFrame containing transactions.
    :param threshold: Numeric threshold to filter transactions.
    :return: DataFrame after filtering.
    """
    return df[df["amount"] >= threshold]


# Example usage:
# df = pd.read_csv(CONSOLIDATED_BATCH_PATH)  # Load your DataFrame
# print(f"source df rows: {len(df)}")
# # excluded_keywords = [...]  # Your list of keywords to exclude
# # EXPENSE_THRESHOLD = 100  # Your expense threshold

# # Apply filters
# df_filtered = filter_by_keywords(df, PERSONAL_EXPENSES)
# df_filtered = filter_by_amount(df_filtered, EXPENSE_THRESHOLD)

# print(f"output df rows: {len(df_filtered)}")
# # Save the filtered DataFrame
# df_filtered.to_csv(CONSOLIDATED_BATCH_PATH, index=False)


def standardize_classifications(df, column_name="Amelia_AI_classification"):
    """
    Standardize the classification column based on certain keywords.

    :param df: DataFrame containing the data.
    :param column_name: The name of the classification column.
    :return: DataFrame with standardized classification values.
    """
    # Define the standardization rules
    rules = {
        "business": "Business Expense",
        "needs": "Needs Review",
        "personal": "Personal Expense",
    }

    # Apply the rules to the classification column
    for keyword, new_value in rules.items():
        df[column_name] = df[column_name].apply(
            lambda x: new_value if keyword in x.lower() else x
        )

    return df


# Example usage:
# df = pd.read_csv(CONSOLIDATED_BATCH_PATH)  # Load your DataFrame
# df_standardized = standardize_classifications(df)
# df_standardized.to_csv(CONSOLIDATED_BATCH_PATH, index=False)
