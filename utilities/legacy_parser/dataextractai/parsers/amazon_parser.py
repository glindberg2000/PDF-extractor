"""
This module is designed to extract specific data points from Amazon invoices in PDF format.
It saves the extracted data into CSV and XLSX files.

Functions:
    - clean_currency_string: Cleans and converts a currency string to a float.
    - isolate_and_structure_item_descriptions: Extracts and structures item descriptions.
    - extract_amazon_fields: Extracts basic order fields like date, number, and total.
    - extract_all_under_items_ordered: Captures all text under 'Items Ordered'.
    - extract_gift_card_amount: Extracts gift card amount if applicable.
    - extract_amazon_invoice_data: Main function to compile all data.
    - save_to_files: Saves extracted data to CSV and XLSX files.
    - clean_keys: Cleans dictionary keys.

Usage:
    >>>python3 -m dataextractai.parsers.amazon_parser
"""

import re
import os
import pdfplumber
import pprint
import pandas as pd
import ast  # Add this at the top of your script
from ast import literal_eval

import csv
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names, get_parent_dir_and_file

SOURCE_DIR = PARSER_INPUT_DIRS["amazon"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["amazon"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["amazon"]["xlsx"]


def clean_currency_string(currency_str):
    """
    Cleans and converts a currency string to a float.

    Parameters:
        currency_str (str): The currency string to clean. E.g., "$1,000.50"

    Returns:
        float: The cleaned currency as a float. E.g., 1000.50
    """
    return float(currency_str.replace("$", "").replace(",", ""))


# Modifying the function to remove residual text 'Other Condition: New' from the 'Description'
def isolate_and_structure_item_descriptions(captured_string):
    """
    Extracts and structures item descriptions from the text captured under "Items Ordered".

    Parameters:
        captured_string (str): The string containing item descriptions.

    Returns:
        list: A list of dictionaries containing structured item descriptions.
    """
    item_list = []
    item_data = {}
    # Split the captured string by item quantity to separate individual items
    items = re.split(r"(\d+ of:)", captured_string)

    # Remove the leading empty string if it exists
    if items and not items[0].strip():
        items = items[1:]

    # Then proceed with forming full_items
    full_items = [
        f"{items[i]}{items[i + 1].strip()}"
        for i in range(0, len(items) - 1, 2)
        if items[i + 1].strip()
    ]
    # print(f"full_items: {full_items}")
    for item in full_items:
        # Use regular expression to extract values
        price_match = re.search(r"\$([\d,]+\.\d+)", item)
        quantity_match = re.search(r"(\d+) of:", item)
        sold_by_match = re.search(r"Sold by: (.*?)(?:Supplied by:|$)", item)
        supplied_by_match = re.search(r"Supplied by: (.*?)(?:Condition:|$)", item)
        condition_match = re.search(r"Condition: (.*)", item)

        if price_match and quantity_match:
            # Remove commas and $ from the price
            cleaned_price = clean_currency_string(price_match.group(1))
            item_data["Price"] = f"{cleaned_price}"
            item_data["Quantity"] = quantity_match.group(1)

            # Remove price from the item string
            description = re.sub(r"\$(\d+\.\d+)", "", item)

            # Remove leading and trailing whitespaces and newlines
            description = description.strip()

            # Remove 'of:' and quantity from the description
            description = re.sub(f"{quantity_match.group(1)} of:", "", description)

            # Remove other fields to clean up the description
            if sold_by_match:
                description = description.replace(sold_by_match.group(0), "")
            if supplied_by_match:
                description = description.replace(supplied_by_match.group(0), "")
            if condition_match:
                description = description.replace(condition_match.group(0), "")

            # Remove any residual text like 'Other Condition: New'
            residual_texts = ["Other Condition: New", "Condition: New"]
            for residual_text in residual_texts:
                description = description.replace(residual_text, "")

            # Concatenate the description into one string
            item_data["Description"] = " ".join(description.split())

            # Add the varying fields if they exist
            if sold_by_match:
                item_data["Sold by"] = sold_by_match.group(1).strip()
            if supplied_by_match:
                item_data["Supplied by"] = supplied_by_match.group(1).strip()
            if condition_match:
                item_data["Condition"] = (
                    condition_match.group(1)
                    .replace(f"{quantity_match.group(1)} of:", "")
                    .strip()
                )

            # Append the item data to the item list
            item_list.append(
                item_data.copy()
            )  # copy the dict to append it as a new object

    return item_list


def extract_amazon_fields(pdf_text):
    """
    Extracts basic order information like order placed date, order number, and order total.

    Parameters:
        pdf_text (str): Text extracted from the Amazon invoice PDF.

    Returns:
        dict: Dictionary containing basic order information.
    """
    extracted_data = {}
    fields_to_extract = ["Order Placed:", "order number:", "Order Total:"]

    for field in fields_to_extract:
        match = re.search(f"(?i){field} (.*?)\n", pdf_text)
        if match:
            # Remove commas if the field is 'Order Total:'
            if field == "Order Total:":
                order_total = clean_currency_string(match.group(1))
                extracted_data[field] = order_total
            else:
                extracted_data[field] = match.group(1).strip()

    return extracted_data


# Function to extract all text under 'Items Ordered' into a single string for post-processing
def extract_all_under_items_ordered(pdf_text):
    """
    Captures all the text under the "Items Ordered" section in the Amazon invoice PDF.

    Parameters:
        pdf_text (str): Text extracted from the Amazon invoice PDF.

    Returns:
        str: Text captured under "Items Ordered".
    """
    lines = pdf_text.split("\n")
    all_text = []
    capture_mode = False

    for line in lines:
        if "Items Ordered" in line:
            capture_mode = True
            continue
        if "Shipping Address:" in line:
            capture_mode = False
        if capture_mode:
            all_text.append(line.strip())

    return " ".join(all_text)


def extract_gift_card_amount(last_page_text):
    """
    Extracts the gift card amount used in the transaction, if applicable.

    Parameters:
        pdf_text (str): Text extracted from the Amazon invoice PDF.

    Returns:
        float: Gift card amount used in the transaction, or None if not applicable.
    """
    gift_card_amount = "0"  # Initialize with a default value of 0
    gift_card_match = re.search(r"Gift Card Amount:-\$(\d+\.\d+)", last_page_text)
    if gift_card_match:
        gift_card_amount = gift_card_match.group(1)
    return gift_card_amount


# Main function to extract all desired data from an Amazon invoice PDF
def extract_amazon_invoice_data(pdf_path):
    """
    Main function to invoke other functions and compile all extracted data.

    Parameters:
        pdf_path (str): File path of the Amazon invoice PDF.

    Returns:
        dict: Dictionary containing all extracted data points.
    """
    # Initialize an empty list to store the text from each page
    amazon_invoice_text = []
    extracted_data = {}
    try:
        # Open the PDF file using pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            # Loop through each page in the PDF
            for page in pdf.pages:
                # Extract text from the page
                text = page.extract_text()
                # Append the text to the list
                amazon_invoice_text.append(text)

        # Extract general fields
        extracted_data = extract_amazon_fields(amazon_invoice_text[0])

        all_pages_text = " ".join(amazon_invoice_text)
        all_under_items_ordered = extract_all_under_items_ordered(all_pages_text)

        extracted_data["Items"] = isolate_and_structure_item_descriptions(
            all_under_items_ordered
        )
        extracted_data["Items Quantity"] = len(extracted_data["Items"])

        last_page_text = amazon_invoice_text[-1]  # Get the text from the last page
        extracted_data["Gift Card Amount:"] = extract_gift_card_amount(last_page_text)
        extracted_data["File Path"] = pdf_path
        return extracted_data
    except Exception as e:
        return {"error": str(e)}


# Function to save the master list to CSV and XLSX files
def save_to_files(master_list):
    """
    Saves the extracted data to CSV and XLSX files.

    Parameters:
        extracted_data (dict): Dictionary containing all extracted data points.
        csv_path (str): File path for saving the CSV file.
        xlsx_path (str): File path for saving the XLSX file.

    Returns:
        None
    """
    # Determine all possible keys from all dictionaries
    all_keys = set()
    for item in master_list:
        all_keys.update(item.keys())

    # Saving to CSV
    with open(OUTPUT_PATH_CSV, "w", newline="") as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=all_keys)
        dict_writer.writeheader()

        # Handle dictionaries with missing keys
        for item in master_list:
            dict_writer.writerow({key: item.get(key, None) for key in all_keys})

    # Saving to XLSX using pandas
    df = pd.DataFrame(master_list)
    df.to_excel(OUTPUT_PATH_XLSX, index=False)


def clean_keys(input_dict):
    """
    Cleans the keys in the dictionaries by removing colons and capitalizing.

    Parameters:
        data_dict (dict): Dictionary with keys to be cleaned.

    Returns:
        dict: Dictionary with cleaned keys.
    """
    return {key.replace(":", "").title(): value for key, value in input_dict.items()}


def safe_literal_eval(s):
    # Check if `s` is already a list, which means no need to parse it as a string
    if isinstance(s, list):
        return s
    try:
        # If `s` is a string, strip it of whitespace and evaluate it as a Python literal
        return ast.literal_eval(s.strip())
    except (ValueError, SyntaxError):
        # If there is an error in the literal evaluation, return an empty list
        return []


def flattened(df):
    # Assuming `df` is your DataFrame loaded with Amazon data

    # The items column should be a list of dictionaries. If it's a string representation, convert it
    df["items"] = df["items"].apply(safe_literal_eval)

    # Explode the items into separate rows
    exploded_items = df.explode("items")

    # Now, we normalize the items column which contains dictionaries
    items_normalized = pd.json_normalize(exploded_items["items"])

    # We drop the 'items' column as we're going to replace it with our normalized data
    exploded_items = exploded_items.drop("items", axis=1)

    # We now concatenate the normalized items with the exploded_items DataFrame
    # Reset index to ensure a proper join
    df_flattened = pd.concat(
        [
            exploded_items.reset_index(drop=True),
            items_normalized.reset_index(drop=True),
        ],
        axis=1,
    )

    # Calculate the 'amount' column as Price times Quantity
    # Ensure that 'Price' and 'Quantity' are in the correct numerical data type
    df_flattened["Price"] = pd.to_numeric(df_flattened["Price"], errors="coerce")
    df_flattened["Quantity"] = pd.to_numeric(df_flattened["Quantity"], errors="coerce")

    # Calculate the 'amount' column
    df_flattened["amount"] = df_flattened["Price"] * df_flattened["Quantity"]

    return df_flattened


def main(write_to_file=True):
    # Main Processor Loop
    # Initialize a master list to store all item details from all PDFs
    master_list = []

    # Loop through each file in the source directory
    for file_name in os.listdir(SOURCE_DIR):
        if file_name.endswith(".pdf"):
            file_path = os.path.join(SOURCE_DIR, file_name)

            print(f"Currently processing file: {file_name}")

            # Use the existing function to process this PDF's content and get the item details
            item_details = extract_amazon_invoice_data(file_path)

            # Append these item details to the master list
            master_list.append(item_details)

    cleaned_list = [clean_keys(item) for item in master_list]

    # pprint.pprint(cleaned_list)
    print(f"Total Orders: {len(cleaned_list)}")

    # Convert parsed data into a DataFrame

    df = pd.DataFrame(cleaned_list)
    df = standardize_column_names(df)
    df = flattened(df)
    df = standardize_column_names(df)
    df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)
    df["order_placed"] = pd.to_datetime(df["order_placed"]).dt.strftime("%m/%d/%Y")

    if write_to_file:
        print("writing files...")
        df.to_csv(OUTPUT_PATH_CSV, index=False)
        df.to_excel(OUTPUT_PATH_XLSX, index=False)

    return df


def run(write_to_file=True):
    """
    Executes the main function to process PDF files and extract data.

    Parameters:
    write_to_file (bool): A flag to determine whether the output DataFrame should be
    written to CSV and XLSX files. Defaults to True.

    Returns:
    DataFrame: A pandas DataFrame generated by the main function.
    """
    return main(write_to_file=write_to_file)


if __name__ == "__main__":
    # When running as a script, write to file by default
    run()
