"""
Print the first 5 lines of every parsed output CSV file in the data/output directory
"""

import os
import pandas as pd

# Define the base directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Replace this with the path to your output directory
output_directory_path = os.path.join(BASE_DIR, "data", "output")

# Get all CSV files in the output directory
csv_files = [f for f in os.listdir(output_directory_path) if f.endswith(".csv")]

# Read and print the first few lines of each CSV file
for csv_file in csv_files:
    file_path = os.path.join(output_directory_path, csv_file)
    print(f"Contents of {csv_file}:")
    df = pd.read_csv(file_path, nrows=0)  # Change nrows to read more lines if needed
    print(df)
    print("\n\n")  # Add extra newline for better separation between files
