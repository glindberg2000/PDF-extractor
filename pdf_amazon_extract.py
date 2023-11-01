import re
import os
import pdfplumber
import pprint
import pandas as pd
import csv

SOURCE_DIR = "SourceStatements/AmazonTests"
OUTPUT_PATH_CSV = "ConsolidatedReports/Amazon_all.csv"
OUTPUT_PATH_XLSX = "ConsolidatedReports/Amazon_all.xlsx"


def clean_currency_string(currency_str):
    return float(currency_str.replace("$", "").replace(",", ""))


# Modifying the function to remove residual text 'Other Condition: New' from the 'Description'
def isolate_and_structure_item_descriptions(captured_string):
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
    extracted_data = {}
    fields_to_extract = ["Order Placed:", "order number:", "Order Total:"]

    for field in fields_to_extract:
        match = re.search(f"{field} (.*?)\n", pdf_text)
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
    gift_card_amount = "0"  # Initialize with a default value of 0
    gift_card_match = re.search(r"Gift Card Amount:-\$(\d+\.\d+)", last_page_text)
    if gift_card_match:
        gift_card_amount = gift_card_match.group(1)
    return gift_card_amount


# Main function to extract all desired data from an Amazon invoice PDF
def extract_amazon_invoice_data(pdf_path):
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


pprint.pprint(master_list)
print(f"MasterList Quantity: {len(master_list)}")
# Save the master list to CSV and XLSX files
save_to_files(master_list)


# Example usage
# pdf_path = "SourceStatements/Amazon/Amazon.com - Order 112-1503364-8255416.pdf"
# extracted_data = extract_amazon_invoice_data(pdf_path)

# pprint.pprint(extracted_data, indent=4)
# print(extracted_data)
