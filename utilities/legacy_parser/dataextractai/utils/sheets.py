"""Google Sheets utility functions."""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()

load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# Get the project root directory (where setup.py is located)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SHEETS_CONFIG_PATH = os.path.join(PROJECT_ROOT, "sheets_config.yaml")


def load_sheets_config() -> Dict[str, Any]:
    """Load the sheets configuration file."""
    if os.path.exists(SHEETS_CONFIG_PATH):
        with open(SHEETS_CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {"sheets": {}}


def save_sheets_config(config: Dict[str, Any]) -> None:
    """Save the sheets configuration file."""
    with open(SHEETS_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def create_new_spreadsheet(service, title: str) -> Optional[str]:
    """Create a new Google Spreadsheet and return its ID."""
    try:
        spreadsheet = {"properties": {"title": title}}
        spreadsheet = (
            service.spreadsheets()
            .create(body=spreadsheet, fields="spreadsheetId")
            .execute()
        )
        return spreadsheet.get("spreadsheetId")
    except Exception as e:
        console.print(f"[red]Error creating new spreadsheet: {str(e)}[/red]")
        return None


def list_spreadsheets(service) -> List[Dict[str, str]]:
    """List available Google Spreadsheets."""
    try:
        # Get all spreadsheets
        results = (
            service.files()
            .list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                spaces="drive",
                fields="files(id, name, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        files = results.get("files", [])
        config = load_sheets_config()
        authorized_sheets = config.get("sheets", {})

        if not files:
            console.print("[yellow]No spreadsheets found.[/yellow]")
            return []

        # Sort files by last modified date
        files.sort(key=lambda x: x["modifiedTime"], reverse=True)

        # Separate authorized and unauthorized sheets
        authorized_files = []
        unauthorized_files = []
        for file in files:
            if file["id"] in authorized_sheets:
                authorized_files.append(file)
            else:
                unauthorized_files.append(file)

        # Create tables for both sections with continuous numbering
        if authorized_files:
            authorized_table = Table(title="Authorized Expense Sheets")
            authorized_table.add_column("#", style="cyan", justify="right")
            authorized_table.add_column("Name", style="cyan")
            authorized_table.add_column("Last Modified", style="yellow")
            authorized_table.add_column("Authorized At", style="green")

            for idx, file in enumerate(authorized_files, 1):
                modified = datetime.fromisoformat(
                    file["modifiedTime"].replace("Z", "+00:00")
                ).strftime("%Y-%m-%d %H:%M")
                authorized_at = datetime.fromisoformat(
                    authorized_sheets[file["id"]]["authorized_at"]
                ).strftime("%Y-%m-%d %H:%M")
                authorized_table.add_row(
                    str(idx), file["name"], modified, authorized_at
                )

            console.print(authorized_table)
            console.print()  # Add spacing between tables

        if unauthorized_files:
            unauthorized_table = Table(title="Other Available Sheets")
            unauthorized_table.add_column("#", style="cyan", justify="right")
            unauthorized_table.add_column("Name", style="cyan")
            unauthorized_table.add_column("Last Modified", style="yellow")

            for idx, file in enumerate(unauthorized_files, len(authorized_files) + 1):
                modified = datetime.fromisoformat(
                    file["modifiedTime"].replace("Z", "+00:00")
                ).strftime("%Y-%m-%d %H:%M")
                unauthorized_table.add_row(str(idx), file["name"], modified)

            console.print(unauthorized_table)

        # Return all files for selection
        return files

    except Exception as e:
        console.print(f"[red]Error listing spreadsheets: {str(e)}[/red]")
        return []


def authorize_spreadsheet(sheet_id: str, sheet_name: str) -> bool:
    """Authorize a spreadsheet for use with the application."""
    config = load_sheets_config()
    config["sheets"][sheet_id] = {
        "name": sheet_name,
        "authorized_at": datetime.now().isoformat(),
    }
    save_sheets_config(config)
    return True


def setup_sheets() -> bool:
    """Interactive setup for Google Sheets integration."""
    console.print("\n[bold blue]Google Sheets Setup Guide[/bold blue]")
    console.print(
        "This will help you set up Google Sheets integration for PDF-extractor.\n"
    )

    # Check for credentials.json
    credentials_path = os.path.join(PROJECT_ROOT, "credentials.json")
    if not os.path.exists(credentials_path):
        console.print(
            Panel(
                "[red]credentials.json not found![/red]\n\n"
                "To get credentials.json:\n"
                "1. Go to [link=https://console.cloud.google.com/]Google Cloud Console[/link]\n"
                "2. Create a new project or select an existing one\n"
                "3. Enable the Google Sheets API\n"
                "4. Create OAuth 2.0 credentials (Desktop app)\n"
                "5. Download the credentials and save as 'credentials.json'\n"
                "6. Place credentials.json in the project root directory:\n"
                f"   [yellow]{PROJECT_ROOT}[/yellow]",
                title="Missing Credentials",
            )
        )
        return False

    # Get or refresh credentials
    creds = get_credentials()
    if not creds:
        return False

    service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    sheet = service.spreadsheets()

    # Always prompt for sheet selection
    console.print(
        Panel(
            "[yellow]Would you like to:[/yellow]\n"
            "1. Create a new spreadsheet\n"
            "2. Choose from existing spreadsheets",
            title="Sheet Selection",
        )
    )

    choice = Prompt.ask("Enter your choice", choices=["1", "2"])
    sheet_id = None

    if choice == "1":
        # Create new spreadsheet
        title = Prompt.ask("Enter a name for the new spreadsheet")
        sheet_id = create_new_spreadsheet(service, title)
        if not sheet_id:
            return False
        console.print(f"[green]✓ Created new spreadsheet: {title}[/green]")
        authorize_spreadsheet(sheet_id, title)
    else:
        # List and choose from existing spreadsheets
        files = list_spreadsheets(drive_service)
        if not files:
            console.print(
                "[red]No spreadsheets available. Please create a new one.[/red]"
            )
            return False

        # Let user choose a spreadsheet by number
        while True:
            try:
                sheet_num = int(
                    Prompt.ask("Enter the number of the spreadsheet to use")
                )
                if 1 <= sheet_num <= len(files):
                    selected_file = files[sheet_num - 1]
                    sheet_id = selected_file["id"]
                    sheet_name = selected_file["name"]

                    # Authorize the selected spreadsheet
                    authorize_spreadsheet(sheet_id, sheet_name)
                    console.print(
                        f"[green]✓ Selected and authorized spreadsheet: {sheet_name}[/green]"
                    )
                    break
                else:
                    console.print("[red]Invalid number. Please try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")

    if not sheet_id:
        console.print("[red]Error: No valid sheet ID obtained[/red]")
        return False

    # Update .env file
    env_path = os.path.join(PROJECT_ROOT, ".env")
    with open(env_path, "a") as f:
        f.write(f"\nGOOGLE_SHEETS_ID={sheet_id}")
    os.environ["GOOGLE_SHEETS_ID"] = sheet_id

    # Test the connection
    try:
        sheet.get(spreadsheetId=sheet_id).execute()
        console.print("[green]✓ Successfully connected to Google Sheets![/green]")
        return True
    except Exception as e:
        console.print(f"[red]Error connecting to Google Sheets: {str(e)}[/red]")
        return False


def get_credentials() -> Optional[Credentials]:
    """Get or refresh Google Sheets credentials."""
    creds = None
    token_path = os.path.join(PROJECT_ROOT, "token.json")

    # Load existing token if it exists
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            console.print(f"[yellow]Error loading existing token: {str(e)}[/yellow]")

    # If credentials are invalid or don't exist, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.path.join(PROJECT_ROOT, "credentials.json"), SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as e:
                console.print(f"[red]Error during authentication: {str(e)}[/red]")
                return None

        # Save the credentials for future use
        try:
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save token: {str(e)}[/yellow]")

    return creds


def create_sheet(service, spreadsheet_id: str, sheet_name: str) -> bool:
    """Create a new sheet in the spreadsheet."""
    try:
        body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": sheet_name,
                            "gridProperties": {
                                "frozenRowCount": 1,
                                "frozenColumnCount": 1,
                            },
                        }
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body
        ).execute()
        return True
    except Exception as e:
        console.print(f"[red]Error creating sheet: {str(e)}[/red]")
        return False


def upload_to_sheets(client_name: str) -> bool:
    """Upload categorized transactions to Google Sheets."""
    try:
        # Get credentials and create service
        creds = get_credentials()
        if not creds:
            return False

        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        # Get spreadsheet ID from environment
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID")
        if not spreadsheet_id:
            console.print("[red]Error: GOOGLE_SHEETS_ID not set[/red]")
            return False

        # Read CSV file
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "clients",
            client_name,
            "output",
            "categorized_transactions.csv",
        )
        if not os.path.exists(csv_path):
            console.print(f"[red]Error: CSV file not found at {csv_path}[/red]")
            return False

        with open(csv_path, "r") as f:
            lines = f.readlines()

        # Parse CSV data
        headers = [h.strip() for h in lines[0].split(",")]
        data = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split(",")]
            if len(values) == len(headers):
                data.append(values)

        # Create new sheet with client name and date
        sheet_name = f"{client_name}_{datetime.now().strftime('%Y%m%d')}"
        if not create_sheet(service, spreadsheet_id, sheet_name):
            return False

        # Prepare data for upload
        values = [headers] + data

        # Upload data
        body = {"values": values}
        result = (
            sheet.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body=body,
            )
            .execute()
        )

        # Format the sheet
        requests = [
            # Format header row
            {
                "repeatCell": {
                    "range": {
                        "sheetId": 0,  # New sheet will have ID 0
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8},
                            "textFormat": {"bold": True},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            # Auto-resize columns
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": 0,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": len(headers),
                    }
                }
            },
        ]

        sheet.batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

        console.print(
            f"[green]✓ Successfully uploaded {len(data)} transactions to Google Sheets![/green]"
        )
        return True

    except Exception as e:
        console.print(f"[red]Error uploading to Google Sheets: {str(e)}[/red]")
        return False


def create_sheets_for_client(
    service, spreadsheet_id: str, client_name: str
) -> Dict[str, int]:
    """Create and set up sheets for a client's data."""
    sheets_to_create = [
        {
            "name": f"{client_name}_{datetime.now().strftime('%Y%m%d')}",
            "description": "Main transaction sheet with all transactions",
        },
        {
            "name": "Categories",
            "description": "Category definitions and usage statistics",
        },
        {"name": "Summary", "description": "Monthly and category summaries"},
    ]

    sheet_ids = {}
    for sheet_info in sheets_to_create:
        if not create_sheet(service, spreadsheet_id, sheet_info["name"]):
            return {}
        # Get the sheet ID
        sheet_metadata = (
            service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        )
        for s in sheet_metadata.get("sheets", ""):
            if s["properties"]["title"] == sheet_info["name"]:
                sheet_ids[sheet_info["name"]] = s["properties"]["sheetId"]
                break

    return sheet_ids
