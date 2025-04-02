"""Google Sheets manager for AMELIA AI Bookkeeping."""

import os
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from typing import Optional, Dict, List
import numpy as np
import tempfile
from .excel_formatter import ExcelReportFormatter


class GoogleSheetManager:
    """Manages Google Sheets operations for AMELIA AI."""

    def __init__(self, credentials_path: str):
        """Initialize the sheet manager with credentials."""
        self.credentials_path = credentials_path
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        self._setup_credentials()

    def _setup_credentials(self):
        """Set up Google Sheets credentials."""
        try:
            # Create credentials using oauth2client (more reliable)
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_path, scopes=self.scope
            )
            self.client = gspread.authorize(self.creds)
        except Exception as e:
            raise Exception(f"Failed to set up Google Sheets credentials: {e}")

    def update_client_sheet(
        self,
        client_name: str,
        data_file: str,
        sheet_id: Optional[str] = None,
        categories: Optional[List[str]] = None,
        classifications: Optional[List[str]] = None,
    ):
        """
        Update or create a sheet for a client with the new data.

        Args:
            client_name: Name of the client
            data_file: Path to the CSV file to upload
            sheet_id: Optional existing sheet ID to update
            categories: List of valid categories for dropdown
            classifications: List of valid classifications for dropdown
        """
        try:
            print(f"Starting sheet update for client: {client_name}")
            print(f"Using credentials from: {self.credentials_path}")

            # Read the CSV file
            df = pd.read_csv(data_file)
            print(f"Read CSV file with {len(df)} rows")

            # Clean the data for Google Sheets
            # Replace inf/-inf with None
            df = df.replace([np.inf, -np.inf], None)
            # Replace NaN with None
            df = df.where(pd.notnull(df), None)

            # Convert any remaining float values to strings to ensure JSON compliance
            for col in df.select_dtypes(include=["float64"]).columns:
                df[col] = df[col].astype(str)

            # Create a rich Excel file with validation and charts
            formatter = ExcelReportFormatter()
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                excel_path = tmp.name
                formatter.create_report(
                    data=df,
                    output_path=excel_path,
                    categories=categories or df["category"].unique().tolist(),
                    classifications=classifications
                    or df["classification"].unique().tolist(),
                )

            # Create or open the sheet
            try:
                if sheet_id:
                    print(f"Opening existing sheet with ID: {sheet_id}")
                    sheet = self.client.open_by_key(sheet_id)
                else:
                    print(f"Creating new sheet for {client_name}")
                    sheet = self.client.create(f"{client_name} Transactions")
                    sheet_id = sheet.id
                    print(f"Created new sheet with ID: {sheet_id}")

                    # Share the sheet with the user's email
                    user_email = "greglindberg@gmail.com"  # Your email
                    print(f"Sharing sheet with: {user_email}")
                    sheet.share(user_email, role="writer")
                    print(f"Successfully shared sheet with {user_email}")

                # Import the Excel file
                print("Uploading Excel file to Google Sheets...")
                content = open(excel_path, "rb").read()
                self.client.import_csv(sheet_id, content)
                print("Excel file uploaded successfully")

                # Clean up the temporary file
                os.unlink(excel_path)

                # Get the sheet URL
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
                print(f"Sheet URL: {sheet_url}")

                return sheet_id

            except Exception as e:
                print(f"Error with sheet operations: {str(e)}")
                if os.path.exists(excel_path):
                    os.unlink(excel_path)
                raise

        except Exception as e:
            print(f"Error in update_client_sheet: {str(e)}")
            raise Exception(f"Failed to update sheet: {e}")
