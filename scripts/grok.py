import typer
from typer import Typer, echo
import os
import pandas as pd
from typing import Optional
from io import StringIO
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dataextractai.utils.utils import create_directory_if_not_exists
from dataextractai.utils.config import (
    PARSER_OUTPUT_PATHS,
    ASSISTANTS_CONFIG,
    COMMON_CONFIG,
)
from dataextractai.classifiers.ai_categorizer import categorize_transaction
from rich.console import Console
from rich.theme import Theme

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

app = typer.Typer(
    help="AI CSV Processor CLI. Use this tool to process CSV files with AI and manage the output data."
)


def main(name: str):
    print(f"Hello {name}")


import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd


def upload_to_google_sheets(csv_file_path, sheet_name, credentials_json):
    """
    Upload data from a CSV file to a Google Sheet.

    :param csv_file_path: Path to the CSV file.
    :param sheet_name: Name of the Google Sheet to upload data to.
    :param credentials_json: Path to the Google Service Account Credentials JSON file.
    """
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
def upload_to_sheet():
    """
    Upload data to a specified Google Sheet.
    """
    csv_file_path = CONSOLIDATED_BATCH_PATH
    sheet_name = "ExpenseReport"
    credentials_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
    if not credentials_json:
        typer.echo("Google Sheets credentials path not set.")
        raise typer.Exit()

    upload_to_google_sheets(csv_file_path, sheet_name, credentials_json)
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


# Replace process_next_batch with your actual batch processing function
# Add additional logic as needed


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


def set_last_processed_row(state_file_path: str, last_row: int):
    """
    Update the state file with the index of the last processed row.
    """
    state = {"last_processed_row": last_row}
    with open(state_file_path, "w") as f:
        json.dump(state, f)


# def process_data(df: pd.DataFrame, ai_config: dict) -> pd.DataFrame:
#     """
#     Process the given dataframe using the AI categorizer.

#     :param df: DataFrame to be processed.
#     :param ai_config: Configuration object for the selected AI assistant.
#     :return: Processed DataFrame with new columns added.
#     """
#     # Initialize new columns for the entire dataframe if they don't exist
#     new_columns = {
#         column: ""
#         for column in ["category", "classification", "comments"]
#         if column not in df.columns
#     }
#     df = df.assign(**new_columns)

#     for index, row in df.iterrows():
#         # Get the description from the row
#         description = row["description"]

#         # Process the description using the AI categorizer
#         processed_json = categorize_transaction(ai_config, description)

#         # If the returned data is a stringified JSON, parse it
#         if isinstance(processed_json, str):
#             processed_data = json.loads(processed_json)
#         else:
#             processed_data = processed_json

#         # Update the row in the dataframe with new data
#         df.at[index, "category"] = processed_data.get("category", "")
#         df.at[index, "classification"] = processed_data.get("classification", "")
#         df.at[index, "comments"] = processed_data.get("comments", "")
#         typer.echo(
#             f"Row {index} processed: Category - {df.at[index, 'category']}, Classification - {df.at[index, 'classification']}"
#         )

#     return df


def process_data(df: pd.DataFrame, ai_config: dict) -> pd.DataFrame:
    # Make a copy of the DataFrame to avoid SettingWithCopyWarning
    df = df.copy()

    # Extract AI name from config and create dynamic column names
    ai_name = ai_config.get("name", "UnknownAI")
    category_col = f"{ai_name}_category"
    classification_col = f"{ai_name}_classification"
    comments_col = f"{ai_name}_comments"

    # Initialize new columns for the entire dataframe if they don't exist
    for column in [category_col, classification_col, comments_col]:
        if column not in df.columns:
            df.loc[:, column] = ""  # Use .loc for safe column addition

    for index, row in df.iterrows():
        description = row["description"]

        # Process the description using the AI categorizer
        processed_json = categorize_transaction(ai_config, description)

        # If the returned data is a stringified JSON, parse it
        if isinstance(processed_json, str):
            processed_data = json.loads(processed_json)
        else:
            processed_data = processed_json

        # Update the row in the dataframe with new data
        df.at[index, category_col] = processed_data.get("category", "")
        df.at[index, classification_col] = processed_data.get("classification", "")
        df.at[index, comments_col] = processed_data.get("comments", "")
        console.print(
            f"[fieldname]Row[/fieldname] [value]{index}[/value] [fieldname]processed[/fieldname]: "
            f"[fieldname]Category[/fieldname] - [value]{df.at[index, category_col]}[/value], "
            f"[fieldname]Classification[/fieldname] - [value]{df.at[index, classification_col]}[/value]",
            style="normal",
        )
        console.print(
            f"[fieldname]Comments[/fieldname]: [comment]{df.at[index, comments_col]}[/comment]\n\n",
            style="normal",
        )

    return df


@app.command()
def merge_reviewed(
    input_file_path: str = typer.Option(
        OUTPUT_PATH_CSV, help="Path for the input CSV file to be updated."
    ),
    batch_file_path: str = typer.Option(
        BATCH_PATH_CSV,
        help="Path for the reviewed batch CSV file that is to be merged.",
    ),
):
    """
    Merge a reviewed batch CSV file with the main input CSV file.
    """
    merge_batch_output_with_main_file(input_file_path, batch_file_path)
    typer.echo(
        f"Reviewed batch file at {batch_file_path} merged into {input_file_path}."
    )


def merge_batch_output_with_main_file(input_file_path: str, output_file_path: str):
    input_df = pd.read_csv(input_file_path)
    output_df = pd.read_csv(output_file_path)
    merged_df = pd.merge(
        input_df, output_df, on="id", how="left", suffixes=("", "_output")
    )
    for col in output_df.columns:
        if col + "_output" in merged_df.columns:
            merged_df[col] = merged_df[col + "_output"]
            merged_df.drop(columns=[col + "_output"], inplace=True)
    merged_df.to_csv(input_file_path, index=False)


import os
import pandas as pd


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


@app.command(help="Process data in batches and save for review.")
def process(
    batch_size: int = typer.Option(3, help="Number of rows to process in a batch."),
    ai_name: str = typer.Option(
        "AmeliaAI",
        help="Select the AI assistant to use for processing. Options: AmeliaAI, DaveAI.",
    ),
    continue_from_last: bool = typer.Option(
        False, help="Continue processing from the last processed row."
    ),
    start_row: Optional[int] = typer.Option(None, help="The starting row to process."),
    end_row: Optional[int] = typer.Option(
        None,
        help="The ending row to process. If not provided, process until the batch size is reached.",
    ),
    reset: bool = typer.Option(
        False, help="Reset the processed file and start from scratch."
    ),
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
):
    # Load the CSV data
    df = pd.read_csv(OUTPUT_PATH_CSV)

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
                processed_df.to_csv(
                    output_file_path, mode="a", header=False, index=False
                )
                typer.echo(f"Processed batch merged directly into {output_file_path}.")
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


# Rest of the script remains the same...


if __name__ == "__main__":
    app()
