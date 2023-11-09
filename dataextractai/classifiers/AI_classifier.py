import os
import pandas as pd
import json
import pprint
import time
from time import sleep
import re
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
classify_prompt = PROMPTS["classify"].format(categories=formatted_categories)

from openai import OpenAI

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
    Retrieves the latest message from a given thread.
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
            print(f"Latest message: {message_value}")
            return message_value
        else:
            print("No messages found in the thread.")
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
        # try:
        #     parsed_data = parse_json_response(classification_output)
        # except Exception as e:
        #     print(f"JSON parse error: {e}")

        # try:
        #     parsed_data2 = parse_json_claude(classification_output)
        # except Exception as e:
        #     print(f"CLAUDE parse error: {e}")

        parsed_data = extract_json(classification_output)
        parsed_data = decode_simulated_json_to_dataframe(classification_output)

        # print("PARSE output:", parsed_data)
        # print("CLAUDE output:", parsed_data2)
        pprint.pprint(parsed_data3)
        # if parsed_data:
        #     transaction_date = parsed_data[0].get("transaction_date")
        #     description = parsed_data[0].get("description")
        #     print(f"transaction_date: {transaction_date}")
        #     print(f"description: {description}")
        # Here, add code to process the output and update your dataframe
    except Exception as e:
        print(f"Main error: {e}")


# Add any additional necessary functions or logic, then call main
if __name__ == "__main__":
    main()
