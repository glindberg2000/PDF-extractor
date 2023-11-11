import os
import pandas as pd
import json
import pprint
import time
from time import sleep
import re
from typing import Optional
import openai
from openai import OpenAI
from dataextractai.utils.config import (
    ASSISTANTS_CONFIG,
    CATEGORIES,
    PARSER_INPUT_DIRS,
    PARSER_OUTPUT_PATHS,
    PROMPTS,
)


CLIENT_DIR = PARSER_INPUT_DIRS["client_info"]
AMELIA_AI = ASSISTANTS_CONFIG["AmeliaAI"]
DAVE_AI = ASSISTANTS_CONFIG["DaveAI"]
GREG_AI = ASSISTANTS_CONFIG["GregAI"]
UPDATED_PATH = PARSER_OUTPUT_PATHS["consolidated_updated"]


# Format the categories for inclusion in the prompt
formatted_categories = ", ".join([f'"{category}"' for category in CATEGORIES])
# Now you can use the format method to insert the categories into the prompt.
classify_csv_prompt = PROMPTS["classify_csv"].format(categories=formatted_categories)
classify_json_prompt = PROMPTS["classify_json"].format(categories=formatted_categories)
classify_download_prompt = PROMPTS["classify_download"].format(
    categories=formatted_categories
)


client = OpenAI()


def json_to_dataframe(json_data):
    """
    Converts a JSON object into a pandas DataFrame.

    Parameters:
    json_data (str or dict): A JSON object string or dictionary containing the data.

    Returns:
    DataFrame: A pandas DataFrame constructed from the JSON data.
    """
    # If the input is a string, parse it into a dictionary
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    # If the input is a list of dictionaries, it can be directly converted to a DataFrame
    if isinstance(json_data, list):
        return pd.DataFrame(json_data)
    # If the input is a dictionary, we convert it to a DataFrame considering it might be nested
    else:
        return pd.json_normalize(json_data)


def concatenate_json_contents(directory):
    """
    Reads all .json files in the given directory, converts their contents to strings,
    and concatenates them into a single string.

    Args:
    directory (str): The path to the directory containing JSON files.

    Returns:
    str: A single string containing all the JSON contents concatenated together.
    """
    concatenated_contents = ""  # Initialize an empty string to hold the contents

    # Loop through each file in the directory
    for file_name in os.listdir(directory):
        if file_name.endswith(".json"):
            file_path = os.path.join(directory, file_name)

            # Open and read the JSON file
            with open(file_path, "r") as json_file:
                json_content = json.load(json_file)

                # Convert the JSON object to a string and concatenate
                concatenated_contents += json.dumps(json_content)

    return concatenated_contents


def concatenate_text_files(directory):
    """
    Reads all .txt files in the given directory and concatenates their contents into a single string.

    Args:
    directory (str): The path to the directory containing text files.

    Returns:
    str: A single string containing all the text contents concatenated together.
    """
    concatenated_contents = ""  # Initialize an empty string to hold the contents

    # Loop through each file in the directory
    for file_name in os.listdir(directory):
        if file_name.endswith(".txt"):
            file_path = os.path.join(directory, file_name)

            # Open and read the text file
            with open(file_path, "r") as text_file:
                file_content = text_file.read()

                # Concatenate the file content to the accumulated string
                concatenated_contents += (
                    file_content + "\n"
                )  # Adding a newline for separation

    return concatenated_contents


def decode_simulated_json_to_dataframe(simulated_json_with_text):
    """
    Decodes a simulated JSON string with non-JSON text before and after the JSON data, where asterisks are used
    in place of quotes, hyphens in place of colons, and integers as markers for new lines, into a pandas DataFrame.

    Parameters:
    simulated_json_with_text (str): A string representing the simulated JSON data with non-JSON text surrounding
                                    the JSON-like portions and with asterisks, hyphens, and integers.

    Returns:
    DataFrame: A pandas DataFrame containing the extracted data.
    """

    # Split the string on the numeric bullet points and take the part after the colon
    transactions = simulated_json_with_text.split("\n\n")
    transactions_dicts = []

    for transaction in transactions:
        if transaction.strip():  # Check if the line is not empty
            # Find the dot followed by a space and split there, then strip leading/trailing whitespace
            json_like_parts = transaction.split(". ", 1)
            if len(json_like_parts) > 1:
                json_like = json_like_parts[1].strip()
                # We only want to evaluate lines that start with a '{'
                if json_like.startswith("{"):
                    # Convert the JSON-like string to a dictionary
                    transaction_dict = eval(json_like)
                    transactions_dicts.append(transaction_dict)

    # Filter out any non-dictionary items that may have been accidentally added
    transactions_dicts = [t for t in transactions_dicts if isinstance(t, dict)]

    # Extract the transaction details from each dictionary
    transactions_data = [list(t.values())[0] for t in transactions_dicts]

    # Check if we have any transaction data collected
    if transactions_data:
        # Convert the list of dictionaries to a DataFrame
        df = pd.DataFrame(transactions_data)
    else:
        df = pd.DataFrame()  # Return an empty DataFrame if no data was found

    return df


def extract_json(text):
    try:
        # Extract the JSON string from the message content
        json_str = text.split("```json\n")[1].split("\n```")[0]
        # Convert the JSON string to a JSON object
        json_data = json.loads(json_str)
        print("JSON data extracted")
        return json_data
    except (IndexError, json.JSONDecodeError) as e:
        print(f"No JSON found: {e}")
        return None


def parse_json_response(message_content):
    # Use regular expressions to find the JSON block
    match = re.search(r"```json\n(.+?)\n```", message_content, re.DOTALL)
    if match:
        json_string = match.group(1).strip()
        try:
            # Parse the JSON string
            json_data = json.loads(json_string)
            return json_data
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return None
    else:
        print("JSON block not found")
        return None


def parse_json_claude(input_message):
    # Extract JSON data between ```json and ```
    match = re.search(r"```json\n(.*)\n```", input_message, re.DOTALL)
    json_str = match.group(1)

    # Load JSON string into Python dict
    data = json.loads(json_str)
    return data


def create_thread(assistant_id, task_message):
    """
    Starts a conversation with the assistant.
    """
    thread = client.beta.threads.create(
        assistant_id=assistant_id, messages=[{"role": "user", "content": task_message}]
    )
    return thread["data"]["id"]


def submit_run(thread_id, message):
    """
    Submits a run (query) to the assistant within the thread.
    """
    run = client.beta.threads.runs.create(
        thread_id=thread_id, tool_inputs=[{"type": "text", "content": message}]
    )
    return run["data"]["id"]


def poll_for_result(thread_id, run_id):
    """
    Polls the thread for a completed result.
    """
    POLLING_INTERVAL = 5  # Poll every 5 seconds
    while True:
        thread_state = get_run_status(thread_id, run_id)
        print(f"Poll status check: {thread_state}")
        if thread_state == "completed":
            print("Completed.")
            message = get_latest_thread_message(thread_id)
            return message
        time.sleep(POLLING_INTERVAL)


def get_run_status(thread_id, run_id):
    """
    Retrieves the status of a run within a thread.
    """
    try:
        run_response = client.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run_id
        )
        return run_response.status
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_latest_thread_message(thread_id):
    """
    Retrieves the CSV file from a given thread.
    """
    try:
        thread_messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=1,
            order="desc",  # This will ensure that the most recent message is returned
        )
        if thread_messages.data:
            latest_message = thread_messages.data[0]
            message_content = latest_message.content[0]
            message_text = message_content.text
            message_value = message_text.value
            print(message_value)

            # message_annotations = message_text.annotations
            # message_file_annotation_file_path = message_annotations[0].file_path
            # file_id = latest_message.file_ids[0]
            # print(f"Latest message: {message_value},{file_id}")
            # print("Retreiving File...")
            # csv_file = client.files.retrieve_content(file_id)

            # print("Content from FILE_ID:", content)
            # print("ANNOTATIONS:", message_annotations)
            # print("Retreiving File Annoation List ID...")
            # content = client.files.retrieve_content(
            #     message_file_annotation_file_path.file_id
            # )
            # print("Content from Annotation List:", content)
            csv_file = "1,2,3,4,5"
            return csv_file
        else:
            print("No files found in the thread.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def create_and_run_thread(assistant_id, user_message):
    """
    Function to create a thread and submit an initial run.
    """
    response = client.beta.threads.create_and_run(
        assistant_id=assistant_id,
        thread={
            "messages": [
                {"role": "user", "content": user_message},
            ],
        },
    )
    return response


def classify_rows(assistant_id: str, start_row: int, end_row: Optional[int] = None):
    """
    Classify the specified rows using the AI assistant.
    """

    # If end_row is not specified, we process only the start_row
    if end_row is None:
        end_row = start_row

    rows_to_classify_json = f"Return a JSON object using the CSV file you already have access to. You will only examine rows(s) starting with ID {start_row} and ending with ID {end_row}"
    rows_to_classify_csv = f"Return the date in CSV file you already have access to in a simulated CSV format which I can decode. You will only need to extract rows(s) starting with ID {start_row} and ending with ID {end_row}"

    # Format the categories for inclusion in the prompt
    formatted_categories = ", ".join([f'"{category}"' for category in CATEGORIES])

    # Now you can use the format method to insert the categories into the prompt.
    classify_prompt = PROMPTS["classify_json"].format(categories=formatted_categories)
    classify_prompt = classify_download_prompt + concatenate_text_files(CLIENT_DIR)
    classify_prompt = "What is the the curren weather in San Francisco? use your built in function called 'get_weather' to get the answer"
    print(classify_prompt)
    # exit()
    # Create thread and submit the initial run
    # classify_prompt = "Return the first 2 rows of the CSV file you have access to. Use a simulated CSV format in your response which I can decode back in to CSV easily on my end."
    # classify_prompt = "Read the CSV file you have access to and extract the first 10 rows and provide to a downloadable CSV of the output"
    # print(classify_prompt)
    # exit()
    thread_response = create_and_run_thread(assistant_id, classify_prompt)
    thread_id = thread_response.thread_id
    run_id = thread_response.id
    run_status = thread_response.status
    print(
        f"Thread created and initial run submitted with ID: {run_id} and status: {run_status}"
    )

    # Poll for response and handle the output
    try:
        classification_output = poll_for_result(thread_id, run_id)
        parsed_data = extract_json(classification_output)
        if not parsed_data:
            parsed_data = decode_simulated_json_to_dataframe(classification_output)
        if parsed_data:
            print(parsed_data)
            return "1,2,3"
        # print("RESPONSE:", classification_output)
        return classification_output
    except Exception as e:
        print(f"Classification error: {e}")
        return None


def main():
    """
    Main function to orchestrate the creation of a thread and polling for response.
    """
    assistant_id = AMELIA_AI["id"]  # Replace with Amelia AI's actual assistant ID
    # user_message = "which classification is a TV if the category choices are computer or electronics? please resopnd in JSON with keys 'classification' and 'reasoning'."
    # ser_task = "Read the CSV file you have access to and examine the row contents one by one and ad"
    user_message = classify_prompt + concatenate_text_files(CLIENT_DIR)
    # Step 1: Create thread and submit the initial run
    thread_response = create_and_run_thread(assistant_id, user_message)
    thread_id = thread_response.thread_id  # Accessing the thread_id property
    run_id = thread_response.id
    run_status = thread_response.status
    print(
        f"Thread created and initial run submitted with ID: {run_id} and status: {run_status}"
    )

    # Step 2: Poll for response
    try:
        classification_output = poll_for_result(thread_id, run_id)
        parsed_data = extract_json(classification_output)
        if not parsed_data:
            parsed_data = decode_simulated_json_to_dataframe(classification_output)

        pprint.pprint(parsed_data3)

    except Exception as e:
        print(f"Main error: {e}")


# Add any additional necessary functions or logic, then call main
# if __name__ == "__main__":
#     main()
def decode_simulated_json_to_dataframe2(simulated_json_with_text):
    transactions = simulated_json_with_text.split("\n\n")
    transactions_dicts = []

    for transaction in transactions:
        if transaction.strip():  # Check if the line is not empty
            # Split on bullet point and colon, then take the part after the colon
            parts = transaction.split(":", 1)
            if len(parts) > 1:
                json_like = parts[1].strip().replace("\n   - ", ", ").replace("\n", "")
                # Convert the JSON-like string to a dictionary
                # For simplicity, we assume each line after splitting is a key-value pair
                transaction_dict = dict(
                    item.split(": ") for item in json_like.split(", ")
                )
                transactions_dicts.append(transaction_dict)

    if transactions_dicts:
        df = pd.DataFrame(transactions_dicts)
    else:
        df = pd.DataFrame()

    return df


testtext = """ The transactions have been classified with the following details:

1. **Transaction ID 5**:
   - Transaction Date: 01/06/2022
   - Description: Yubico - YubiKey 5C NFC - Two Factor Authentic...
   - Amount: $110.00
   - Source: Amazon
   - File Path: amazon/Amazon.com - Order 112-6628003-6829863.pdf
   - Classification: Computer Equipment
   - Category: Business
   - Status: Cleared
   - Comments: The purchase of a YubiKey for authentication purposes falls under the 'Computer Equipment' category as a business expense.

2. **Transaction ID 6**:
   - Transaction Date: 01/06/2022
   - Description: De'Longhi Livenza 9-in-1 Digital Air Fry Conve...
   - Amount: $237.99
   - Source: Amazon
   - File Path: amazon/Amazon.com - Order 112-6628003-6829863.pdf
   - Classification: Office Supplies
   - Category: Business
   - Status: Cleared
   - Comments: The purchase of a digital air fry convection oven may be categorized as an 'Office Supplies' expense if it is used for business purposes, such as company events or employee perks.

3. **Transaction ID 7**:
   - Transaction Date: 01/06/2022
   - Description: Winsome Halifax Storage/Organization, 5 drawer...
   - Amount: $78.21
   - Source: Amazon
   - File Path: amazon/Amazon.com - Order 112-6628003-6829863.pdf
   - Classification: Office Furniture
   - Category: Business
   - Status: Cleared
   - Comments: The purchase of office storage/organization furniture falls under the 'Office Furniture' category as a business expense.

4. **Transaction ID 8**:
   - Transaction Date: 01/06/2022
   - Description: Small Fireproof Bag (5 x 8 inches), Non-itchy ...
   - Amount: $14.75
   - Source: Amazon
   - File Path: amazon/Amazon.com - Order 112-6628003-6829863.pdf
   - Classification: Office Supplies
   - Category: Business
   - Status: Cleared
   - Comments: The purchase of a small fireproof bag may be categorized as an 'Office Supplies' expense if it is used for business-related document storage or protection.

5. **Transaction ID 9**:
   - Transaction Date: 01/06/2022
   - Description: Fireproof Document Bag (13.4 x 9.8 inches), Fi...
   - Amount: $17.32
   - Source: Amazon
   - File Path: amazon/Amazon.com - Order 112-6628003-6829863.pdf
   - Classification: Office Supplies
   - Category: Business
   - Status: Cleared
   - Comments: The purchase of a fireproof document bag may be categorized as an 'Office Supplies' expense if it is used for business-related document storage or protection.

6. **Transaction ID 10**:
   - Transaction Date: 06/17/2022
   - Description: ALPHA BIDET UX Pearl Bidet Toilet Seat in Elon...
   - Amount: $599.00
   - Source: Amazon
   - File Path: amazon/Amazon.com - Order 112-4651684-0959425.pdf
   - Classification: Needs clarification
   - Category: Unknown
   - Status: Review
   - Comments: The purchase of a bidet toilet seat requires further clarification to determine if it is a personal or business-related expense.

You can now review the classified transactions. If there are any additional transactions or further review is needed, please let me know!
"""


# parsed_data = decode_simulated_json_to_dataframe2(testtext)
# print(parsed_data)
