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
    CLASSIFICATIONS,
    PARSER_INPUT_DIRS,
    PARSER_OUTPUT_PATHS,
    PROMPTS,
)

CLIENT_DIR = PARSER_INPUT_DIRS["client_info"]
AMELIA_AI = ASSISTANTS_CONFIG["AmeliaAI"]
DAVE_AI = ASSISTANTS_CONFIG["DaveAI"]
GREG_AI = ASSISTANTS_CONFIG["GregAI"]

client = OpenAI()


def client_files(directory):
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


# def categorize_transaction(ASSISTANT_CONFIG, desc):
#     """
#     Classify the specified description using the AI assistant.
#     """

#     # Format the categories for inclusion in the prompt
#     formatted_categories = ", ".join([f'"{category}"' for category in CATEGORIES])

#     classify_prompt = PROMPTS["categorize_classify_comment"].format(
#         categories=formatted_categories
#     )

#     classify_prompt = classify_prompt + desc + client_files(CLIENT_DIR)

#     # print(classify_prompt)
#     #

#     response = client.chat.completions.create(
#         model=ASSISTANT_CONFIG["model"],
#         response_format={"type": "json_object"},
#         messages=[
#             {
#                 "role": "system",
#                 "content": ASSISTANT_CONFIG["instructions"] + " return json only",
#             },
#             {"role": "user", "content": classify_prompt},
#         ],
#     )

#     category = response.choices[0].message.content
#     return category


def categorize_transaction(ASSISTANT_CONFIG, desc):
    """
    Classify the specified description using the AI assistant.
    """

    # Sample JSON responses (replace these with your actual function calls)
    payee_str = get_payee(ASSISTANT_CONFIG, desc)
    category_str = get_category(ASSISTANT_CONFIG, desc + payee_str)
    classification_str = get_classification(ASSISTANT_CONFIG, desc + category_str)

    # Initialize an empty JSON object
    final_json = {}

    # Parse the payee JSON string into a dictionary
    try:
        payee = json.loads(payee_str)
        # Check if payee is a dictionary before updating
        if isinstance(payee, dict):
            final_json.update(payee)
    except json.JSONDecodeError:
        print("Error parsing payee JSON")

    # Parse the category JSON string into a dictionary
    try:
        category = json.loads(category_str)
        # Check if category is a dictionary before updating
        if isinstance(category, dict):
            final_json.update(category)
    except json.JSONDecodeError:
        print("Error parsing category JSON")

    # Parse the classification JSON string into a dictionary
    try:
        classification = json.loads(classification_str)
        # Merge the classification data with handling for multiple keys
        if isinstance(classification, dict):
            for key, value in classification.items():
                if key in final_json:
                    # If the key already exists in final_json, append the values as a list
                    if isinstance(final_json[key], list):
                        final_json[key].append(value)
                    else:
                        final_json[key] = [final_json[key], value]
                else:
                    # If the key doesn't exist in final_json, add it with the value
                    final_json[key] = value
    except json.JSONDecodeError:
        print("Error parsing classification JSON")

    # Serialize the final JSON object to a JSON string
    final_json_str = json.dumps(final_json)

    print(final_json_str)

    return final_json_str


def get_payee(ASSISTANT_CONFIG, desc):
    """
    Get the payee of the transaction.
    """

    prompt = PROMPTS["get_payee"] + desc

    response = client.chat.completions.create(
        model=ASSISTANT_CONFIG["model"],
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": ASSISTANT_CONFIG["instructions"] + " return json only",
            },
            {"role": "user", "content": prompt},
        ],
    )

    payee = response.choices[0].message.content
    return payee


def get_category(ASSISTANT_CONFIG, desc):
    """
    Categorize the specified description using the AI assistant.
    """

    # Format the categories for inclusion in the prompt
    formatted_categories = ", ".join([f'"{category}"' for category in CATEGORIES])

    prompt = PROMPTS["get_category"].format(categories=formatted_categories)

    prompt = prompt + desc

    response = client.chat.completions.create(
        model=ASSISTANT_CONFIG["model"],
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": ASSISTANT_CONFIG["instructions"] + " return json only",
            },
            {"role": "user", "content": prompt},
        ],
    )

    category = response.choices[0].message.content
    return category


def get_classification(ASSISTANT_CONFIG, desc):
    """
    Classify the specified description using the AI assistant.
    """

    # Format the categories for inclusion in the prompt
    formatted_classifications = ", ".join(
        [f'"{classification}"' for classification in CLASSIFICATIONS]
    )

    prompt = PROMPTS["get_classification"].format(
        classifications=formatted_classifications
    )

    prompt = prompt + desc + client_files(CLIENT_DIR)

    # print(classify_prompt)
    #

    response = client.chat.completions.create(
        model=ASSISTANT_CONFIG["model"],
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": ASSISTANT_CONFIG["instructions"] + " return json only",
            },
            {"role": "user", "content": prompt},
        ],
    )

    category = response.choices[0].message.content
    return category


# Item = "Auto repair"
# AMELIA_AI_response = categorize_transaction(AMELIA_AI, Item)
# print("Amelia:")

# pprint.pprint(AMELIA_AI_response)
# print(AMELIA_AI_response)

# DAVE_AI_response = categorize_transaction(DAVE_AI, Item)
# print("Dave:")
# pprint.pprint(DAVE_AI_response)

# GREG_AI_response = categorize_transaction(GREG_AI, Item)
