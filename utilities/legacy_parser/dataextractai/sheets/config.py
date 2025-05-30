"""Configuration for Google Sheets integration."""

import os
import json
from typing import Dict, Optional


def get_sheets_config(client_name: str) -> Dict:
    """
    Get Google Sheets configuration for a client.

    Args:
        client_name: Name of the client

    Returns:
        Dictionary containing sheet configuration
    """
    config_path = os.path.join("data", "clients", client_name, "sheets_config.json")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)

    # Default configuration
    return {
        "sheet_name": f"{client_name} Transactions",
        "sheet_id": None,  # Will be set after first creation
        "tabs": {
            "transactions": {"name": "Transactions", "sort_column": "transaction_date"}
        },
    }


def save_sheets_config(client_name: str, config: Dict):
    """
    Save Google Sheets configuration for a client.

    Args:
        client_name: Name of the client
        config: Configuration dictionary to save
    """
    config_path = os.path.join("data", "clients", client_name, "sheets_config.json")

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
