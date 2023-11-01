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
    >>> python pdf_amazon_extract.py
"""

import re
import os
import pdfplumber
import pprint
import pandas as pd
import csv

SOURCE_DIR = "SourceStatements/Amazon"
OUTPUT_PATH_CSV = "ConsolidatedReports/Amazon_all.csv"
OUTPUT_PATH_XLSX = "ConsolidatedReports/Amazon_all.xlsx"


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
    amazon_invoice_text_pdfplumber = []
    extracted_data = {}
    try:
        # Open the PDF file using pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            # Loop through each page in the PDF
            for page in pdf.pages:
                # Extract text from the page
                text = page.extract_text()
                # Append the text to the list
                amazon_invoice_text_pdfplumber.append(text)

        # Extract general fields
        extracted_data = extract_amazon_fields(amazon_invoice_text_pdfplumber[0])

        all_pages_text = " ".join(amazon_invoice_text_pdfplumber)
        all_under_items_ordered = extract_all_under_items_ordered(all_pages_text)

        extracted_data["Items"] = isolate_and_structure_item_descriptions(
            all_under_items_ordered
        )
        extracted_data["Items Quantity"] = len(extracted_data["Items"])

        last_page_text = amazon_invoice_text_pdfplumber[
            -1
        ]  # Get the text from the last page
        extracted_data["Gift Card Amount:"] = extract_gift_card_amount(last_page_text)

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
pprint.pprint(cleaned_list)
print(f"MasterList Quantity: {len(cleaned_list)}")

# Save the cleaned master list to CSV and XLSX files
save_to_files(cleaned_list)
