# utils/utils.py

import re
import os


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
