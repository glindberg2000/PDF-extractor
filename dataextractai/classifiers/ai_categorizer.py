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


def categorize_transaction(ASSISTANT_CONFIG, desc):
    """
    Classify the specified description using the AI assistant.
    """

    # Format the categories for inclusion in the prompt
    formatted_categories = ", ".join([f'"{category}"' for category in CATEGORIES])

    # Now you can use the format method to insert the categories into the prompt.
    # classify_prompt = PROMPTS["categorize_one"].format(categories=formatted_categories)
    # classify_prompt = PROMPTS["categorize_classify"].format(
    #     categories=formatted_categories
    # )
    classify_prompt = PROMPTS["categorize_classify_comment"].format(
        categories=formatted_categories
    )

    classify_prompt = classify_prompt + desc + client_files(CLIENT_DIR)

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
            {"role": "user", "content": classify_prompt},
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
