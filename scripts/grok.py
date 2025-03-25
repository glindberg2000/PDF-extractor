"""
grok.py

This script serves as the main entry point for the AI CSV Processor CLI, a versatile tool designed to streamline the processing of financial documents. Utilizing advanced AI assistants, it offers a range of functionalities:

1. Parser Execution: Run a series of parsers to extract data from various financial documents and convert them into a structured format.

2. AI-Assisted Processing: Leverage OpenAI assistants to categorize, classify, and provide justifications for each transaction, enhancing data with insightful AI-generated content.

3. Google Sheets Integration: Seamlessly upload the final processed output to Google Sheets for easy access and review.

The script is highly configurable, with a `config.py` file that contains various settings including categories, classifications, AI assistant configurations, system prompts, models, etc. It also allows the use of keywords as hints to guide the AI in processing data more effectively.

Also, you can add personal info for OpenAI to use by creating a Client text file in the client_info folder. Include all your relevant personal and business information for OpenAI to use during classification.

Usage:
    python grok.py [COMMAND] [OPTIONS]

Example:
    python grok.py run-parsers
    python grok.py process --batch-size 25
    python grok.py upload-to-sheet

For detailed command usage, run:
    python grok.py --help
"""

import typer
from typer import Typer, echo
import os
import shutil
import pandas as pd
from typing import Optional
from io import StringIO
import json

from rich.console import Console
from rich.theme import Theme

from dataextractai.utils.utils import (
    create_directory_if_not_exists,
    filter_by_amount,
    filter_by_keywords,
    standardize_classifications,
)
from dataextractai.utils.config import (
    PARSER_OUTPUT_PATHS,
    ASSISTANTS_CONFIG,
    COMMON_CONFIG,
    PERSONAL_EXPENSES,
    EXPENSE_THRESHOLD,
    CATEGORIES,
    CLASSIFICATIONS,
    REPORTS,
    update_config_for_client,
    get_client_sheets_config,
)
from dataextractai.classifiers.ai_categorizer import categorize_transaction
from dataextractai.parsers.run_parsers import run_all_parsers

# Define a theme with a specific color for comments
custom_theme = Theme(
    {
        "fieldname": "cyan",
        "value": "magenta",
        "comment": "green",  # Color for comments
        "normal": "white",
    }
)
console = Console(theme=custom_theme)

# Define the path to the CSV file
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["consolidated_core"]["csv"]
CONSOLIDATED_BATCH_PATH = PARSER_OUTPUT_PATHS["consolidated_batched"]["csv"]
BATCH_PATH_CSV = PARSER_OUTPUT_PATHS["batch"]["csv"]
STATE_FILE = PARSER_OUTPUT_PATHS["state"]
AMELIA_AI = ASSISTANTS_CONFIG["AmeliaAI"]
DAVE_AI = ASSISTANTS_CONFIG["DaveAI"]
BATCH_DIR = COMMON_CONFIG["batch_output_dir"]

app = typer.Typer(
    help="AI CSV Processor CLI. Use this tool to process CSV files with AI and manage the output data."
)


def get_client_option():
    """Get the client option for commands."""
    return typer.Option(
        None,
        "--client",
        "-c",
        help="Client name to use for processing. If not specified, uses legacy data directory.",
    )


@app.command()
def run_parsers(client: str = get_client_option()):
    """
    Run all pdf parsers and normalize and export data for further processing and reporting

    This command executes all configured parsers to process financial documents.
    It outputs the total number of lines processed across all files.
    """
    if client:
        console.print(
            f"[fieldname]Using client directory[/fieldname]: [value]{client}[/value]"
        )

    total_lines = run_all_parsers(client)
    console.print(
        f"[fieldname]Total Lines Processed[/fieldname]: [value]{total_lines}[/value]",
        style="normal",
    )


def upload_and_set_dropdown(csv_file_path, sheet_name, credentials_json, categories):
    """
    Uploads data to a Google Sheet and sets a dropdown in column H using provided categories.

    :param csv_file_path: Path to the CSV file.
    :param sheet_name: Name of the Google Sheet to upload data to.
    :param credentials_json: Path to the Google Service Account Credentials JSON file.
    :param categories: List of category names for the dropdown.
    """
    # Import Google Sheets dependencies only when needed
    import gspread
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
    from oauth2client.service_account import ServiceAccountCredentials
    from google.oauth2 import service_account

    classification_categories = CLASSIFICATIONS

    # Read the CSV file with pandas
    try:
        data = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print("Output File not found. Please verify the data files is ready for upload")

    # Standardize the 'Amelia_AI_classification' column to match fixed list in the config
    standardize_classifications(data)

    # Save the updated DataFrame back to CSV
    data.to_csv(csv_file_path, index=False)

    # Upload the CSV to Google Sheets first
    upload_to_google_sheets(csv_file_path, sheet_name, credentials_json)

    # Initialize Google Sheets API client
    creds = service_account.Credentials.from_service_account_file(credentials_json)
    service = build("sheets", "v4", credentials=creds)

    # Column index for 'Amelia_AI_category' (Column H is index 8)
    category_column_index = 8

    # Set the column index for 'Amelia_AI_classification' (assuming it's Column I)
    classification_column_index = 9

    # Add requests to clear existing validations (if needed)
    remove_validation_request = {
        "setDataValidation": {
            "range": {
                "sheetId": 0,
                "startRowIndex": 1,
                "endRowIndex": 1000,
                "startColumnIndex": 7,  # The column index to clear
                "endColumnIndex": 10,  # Adjust this as needed
            },
            "rule": {
                "condition": {
                    "type": "TEXT_CONTAINS",
                    "values": [{"userEnteredValue": ""}],
                },
                "showCustomUi": False,
            },
        }
    }

    # Prepare the request body for batchUpdate to create the dropdowns
    requests_body = {
        "requests": [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": 0,  # Update with the actual sheet ID if necessary
                        "startRowIndex": 1,  # Assuming you want to skip the header row
                        "endRowIndex": 1000,  # Adjust the range as needed
                        "startColumnIndex": category_column_index,
                        "endColumnIndex": category_column_index + 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [{"userEnteredValue": cat} for cat in categories],
                        },
                        "showCustomUi": True,
                        "strict": True,
                    },
                }
            },
            # Now, create the dropdown for 'Amelia_AI_classification'
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": 0,  # Assuming the first sheet
                        "startRowIndex": 1,  # Assuming you want to skip the header row
                        "endRowIndex": 1000,  # Adjust the range as needed
                        "startColumnIndex": classification_column_index,
                        "endColumnIndex": classification_column_index + 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": cat}
                                for cat in classification_categories
                            ],
                        },
                        "showCustomUi": True,
                        "strict": True,
                    },
                }
            },
        ]
    }

    # Add these requests to the existing requests_body['requests']
    requests_body["requests"].insert(0, remove_validation_request)

    # Execute the batchUpdate to create both dropdowns
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=requests_body
    ).execute()

    print(
        f"Data from {csv_file_path} uploaded to Google Sheet: {sheet_name} and dropdowns set."
    )


def upload_to_google_sheets(csv_file_path, sheet_name, credentials_json):
    """
    Upload data from a CSV file to a Google Sheet.

    :param csv_file_path: Path to the CSV file.
    :param sheet_name: Name of the Google Sheet to upload data to.
    :param credentials_json: Path to the Google Service Account Credentials JSON file.
    """
    # Import Google Sheets dependencies only when needed
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    # Define the scope for the Google Sheets API
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Add credentials to the account
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_json, scope)

    # Connect to Google Sheets
    client = gspread.authorize(creds)

    try:
        # Open the Google Spreadsheet
        sheet = client.open(sheet_name).sheet1

        # Read the CSV file with pandas
        data = pd.read_csv(csv_file_path)

        # Clear existing data in the sheet and upload new data
        sheet.clear()
        sheet.update([data.columns.values.tolist()] + data.values.tolist())
        print(f"Data uploaded successfully to Google Sheet: {sheet_name}")
    except Exception as e:
        print(f"An error occurred: {e}")


@app.command(help="Upload consoldated batch file to google sheets")
def upload_to_sheet(client: str = get_client_option()):
    """
    Upload data to a specified Google Sheet.
    """
    # Get Google Sheets credentials from environment
    credentials_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID")

    if client:
        update_config_for_client(client)
        sheets_config = get_client_sheets_config(client)
        sheet_name = sheets_config["sheetname"]
        if sheets_config.get("sheet_id"):
            spreadsheet_id = sheets_config["sheet_id"]
        console.print(f"[fieldname]Using client[/fieldname]: [value]{client}[/value]")
    else:
        sheet_name = REPORTS["sheetname"]

    csv_file_path = CONSOLIDATED_BATCH_PATH
    if not credentials_json:
        typer.echo("Google Sheets credentials path not set.")
        raise typer.Exit()

    upload_and_set_dropdown(csv_file_path, sheet_name, credentials_json, CATEGORIES)
    typer.echo(f"Data from {csv_file_path} uploaded to Google Sheet: {sheet_name}")


app.command()


def process_batches_continuously():
    """
    Process data in continuous batches with the ability to pause or stop.
    """
    try:
        while True:  # Continuous loop
            # Logic to check if there are more batches to process
            # If no more batches, break the loop
            if no_more_batches:
                typer.echo("No more batches to process.")
                break

            # Process the next batch
            process_next_batch()

            # Optional: Prompt for continuation
            cont = typer.confirm("Continue with the next batch?")
            if not cont:
                break

    except KeyboardInterrupt:
        # Handle the keyboard interrupt for graceful termination
        typer.echo("Batch processing interrupted. Exiting...")


def get_last_processed_row(state_file_path: str) -> int:
    """
    Get the index of the last processed row from the state file.
    If the state file does not exist or is empty, return 0.
    """
    try:
        with open(state_file_path, "r") as f:
            state = json.load(f)
        return state.get("last_processed_row", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0  # If file does not exist or is empty, start from the beginning


def reset_state(state_file_path: str):
    initial_state = {
        "last_processed_row": 0
    }  # Adjust according to your state structure
    with open(state_file_path, "w") as f:
        json.dump(initial_state, f)


def wipe_batches_directory(directory_path: str):
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")


def set_last_processed_row(state_file_path: str, last_row: int):
    """
    Update the state file with the index of the last processed row.
    """
    state = {"last_processed_row": last_row}
    with open(state_file_path, "w") as f:
        json.dump(state, f)


def process_data(df: pd.DataFrame, ai_config: dict) -> pd.DataFrame:
    # Make a copy of the DataFrame to avoid SettingWithCopyWarning
    df = df.copy()

    # Extract AI name from config and create dynamic column names
    ai_name = ai_config.get("name", "UnknownAI")
    payee_col = f"{ai_name}_payee"
    category_col = f"{ai_name}_category"
    classification_col = f"{ai_name}_classification"
    comments_col = f"{ai_name}_comments"

    # Initialize new columns for the entire dataframe if they don't exist
    for column in [payee_col, category_col, classification_col, comments_col]:
        if column not in df.columns:
            df.loc[:, column] = ""  # Use .loc for safe column addition

    for index, row in df.iterrows():
        description = (
            row["description"] + " $" + str(row["amount"]) + " " + row["source"]
        )

        # Process the description using the AI categorizer
        processed_json = categorize_transaction(ai_config, description)

        # If the returned data is a stringified JSON, parse it
        if isinstance(processed_json, str):
            processed_data = json.loads(processed_json)
        else:
            processed_data = processed_json
        # print("FULL JSON:", processed_data)
        # Update the row in the dataframe with new data
        df.at[index, payee_col] = processed_data.get("payee", "")
        df.at[index, category_col] = processed_data.get("category", "")
        df.at[index, classification_col] = processed_data.get("classification", "")
        df.at[index, comments_col] = processed_data.get("comments", "")
        console.print(
            f"[fieldname]Row[/fieldname] [value]{index}[/value] [fieldname]processed[/fieldname]: "
            f"[fieldname]Payee[/fieldname] - [value]{df.at[index, payee_col]}[/value], "
            f"[fieldname]Category[/fieldname] - [value]{df.at[index, category_col]}[/value], "
            f"[fieldname]Classification[/fieldname] - [value]{df.at[index, classification_col]}[/value]",
            style="normal",
        )
        console.print(
            f"[fieldname]Comments[/fieldname]: [comment]{df.at[index, comments_col]}[/comment]\n\n",
            style="normal",
        )

    return df


def merge_batches(batch_folder_path, final_output_path, sort_column):
    """
    Merge all batch files in the given folder into a final output file and sort it.

    :param batch_folder_path: Path to the folder containing batch files.
    :param final_output_path: Path where the final merged output should be saved.
    :param sort_column: Column name to sort the final DataFrame.
    """
    # List all batch files
    batch_files = [f for f in os.listdir(batch_folder_path) if f.endswith(".csv")]

    # Read and concatenate all batch DataFrames
    all_batches_df = pd.concat(
        [pd.read_csv(os.path.join(batch_folder_path, f)) for f in batch_files]
    )

    # Sort the DataFrame
    all_batches_df = all_batches_df.sort_values(by=sort_column)

    # Save the final output
    all_batches_df.to_csv(final_output_path, index=False)
    print(
        f"Final output file created and sorted by {sort_column} at {final_output_path}"
    )


@app.command()
def merge_batch_files():
    """
    Merge processed batch files from the common batch output directory
    into a final output file at the consolidated batch path.
    """
    typer.echo("Merging batch files...")
    batch_folder = COMMON_CONFIG["batch_output_dir"]
    final_output = CONSOLIDATED_BATCH_PATH
    sort_column = "ID"  # Replace with the column you want to sort by

    merge_batches(batch_folder, final_output, sort_column)
    typer.echo(f"Merged batches saved to {final_output}")


@app.command(help="Process data wiht AI Assistant in batches and save for review.")
def process(
    batch_size: int = typer.Option(25, help="Number of rows to process in a batch."),
    ai_name: str = typer.Option(
        "AmeliaAI",
        help="Select the AI assistant to use for processing. Options: AmeliaAI, DaveAI.",
    ),
    start_row: Optional[int] = typer.Option(None, help="The starting row to process."),
    end_row: Optional[int] = typer.Option(
        None,
        help="The ending row to process. If not provided, process until the batch size is reached.",
    ),
    reset: bool = typer.Option(False, help="Wipe batches and start from scratch."),
    merge_directly: bool = typer.Option(
        False,
        help="Merge the processed output directly into the input file, skipping review.",
    ),
    output_file_path: Optional[str] = typer.Option(
        OUTPUT_PATH_CSV, help="Path for the output CSV file."
    ),
    batch_file_path: Optional[str] = typer.Option(
        BATCH_PATH_CSV, help="Path for the batch CSV file to save for review."
    ),
    year: int = typer.Option(2022, help="The year of the transactions to process."),
):
    if reset:
        reset_state(STATE_FILE)
        wipe_batches_directory(BATCH_DIR)
        typer.echo("State reset and batches directory wiped.")

    # Load the CSV data
    df = pd.read_csv(OUTPUT_PATH_CSV)

    # Filter the DataFrame by the specified year
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df = df[df["transaction_date"].dt.year == year]

    # Apply the function to filter the DataFrame for included keywords and above the expense threshold
    df = filter_by_keywords(df, PERSONAL_EXPENSES)
    df = filter_by_amount(df, EXPENSE_THRESHOLD)

    # Select the AI configuration based on user input
    if ai_name in ASSISTANTS_CONFIG:
        ai_config = ASSISTANTS_CONFIG[ai_name]
    else:
        typer.echo(
            f"AI assistant '{ai_name}' not found. Please choose from AmeliaAI, DaveAI."
        )
        raise typer.Exit()

    """
    Continuously process data in batches with the ability to pause or stop.
    """
    total_rows = len(df)
    typer.echo(f"Total rows in the file: {total_rows}")

    start_index = (
        start_row if start_row is not None else get_last_processed_row(STATE_FILE)
    )
    end_limit = end_row if end_row is not None else total_rows

    try:
        while start_index < end_limit:
            end_index = min(start_index + batch_size, end_limit)
            typer.echo(f"Processing batch: Rows {start_index} to {end_index - 1}\n")

            df_to_process = df.iloc[start_index:end_index]
            processed_df = process_data(df_to_process, ai_config)

            create_directory_if_not_exists(COMMON_CONFIG["batch_output_dir"])

            # Save the processed batch
            if merge_directly:
                batch_file = (
                    f"{batch_file_path}_batch_{start_index}_to_{end_index - 1}.csv"
                )
                processed_df.to_csv(batch_file, index=False)
                merge_batch_files()
            else:
                batch_file = (
                    f"{batch_file_path}_batch_{start_index}_to_{end_index - 1}.csv"
                )
                processed_df.to_csv(batch_file, index=False)
                typer.echo(f"Processed batch saved for review at {batch_file}.\n")

            # Update the start index for the next batch
            set_last_processed_row(STATE_FILE, end_index)
            start_index = end_index

            typer.echo("Batch processing complete. Press Ctrl+C to stop.")

    except KeyboardInterrupt:
        typer.echo("Batch processing interrupted by user. Exiting...")

    typer.echo("All batches processed or operation stopped by user.")


if __name__ == "__main__":
    app()
