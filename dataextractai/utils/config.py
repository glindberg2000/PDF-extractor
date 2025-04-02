# dataextractai/utils/config.py
import os
import yaml
from typing import Dict, Any
import pandas as pd
from pathlib import Path

# Define the base directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get model configurations from environment
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
OPENAI_MODEL_PRECISE = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")


# Client configuration
def get_client_config(client_name):
    """
    Get the client configuration from the client_config.yaml file

    Args:
        client_name (str): The name of the client

    Returns:
        dict: The client configuration
    """
    # Handle names with spaces for file paths
    if " " in client_name:
        first_name = client_name.split(" ")[0]
        # Check if client_name is first name + last name
        if len(client_name.split(" ")) > 1:
            path_client_name = client_name  # Keep as is for looking in directories
        else:
            path_client_name = client_name
    else:
        first_name = client_name
        path_client_name = client_name

    # Try different possible file locations
    possible_paths = [
        os.path.join("data", "clients", path_client_name, "client_config.yaml"),
        os.path.join(
            "data",
            "clients",
            path_client_name,
            f"{path_client_name.lower()}_config.yaml",
        ),
        os.path.join(
            "data", "clients", path_client_name, f"{first_name.lower()}_config.yaml"
        ),
        os.path.join("clients", path_client_name, "client_config.yaml"),
    ]

    # Check if any of the paths exist
    config_path = None
    for path in possible_paths:
        if os.path.exists(path):
            config_path = path
            break

    if not config_path:
        # If the config file doesn't exist, show what paths were checked
        print(f"Tried to find config in these locations:")
        for path in possible_paths:
            print(f"  - {path}")
        raise FileNotFoundError(
            f"Configuration file not found for client: {client_name}"
        )

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


def update_config_for_client(client_name: str, config: Dict) -> None:
    """Update client configuration in YAML file."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


# Common configuration for all clients
COMMON_CONFIG = {
    "data_dir": os.path.join("data", "clients"),
    "input_dir": os.path.join("data", "clients"),
    "output_dir": os.path.join("data", "clients"),
    "batch_output_dir": os.path.join("data", "clients"),
    "business_rules": {
        "min_amount": 0.00,
        "max_amount": 1000000.00,
    },
    "custom_categories": [],
}

# Parser input directories
PARSER_INPUT_DIRS = {
    "amazon": os.path.join("data", "clients", "input", "amazon"),
    "bofa_bank": os.path.join("data", "clients", "input", "bofa_bank"),
    "bofa_visa": os.path.join("data", "clients", "input", "bofa_visa"),
    "chase_visa": os.path.join("data", "clients", "input", "chase_visa"),
    "wellsfargo_bank": os.path.join("data", "clients", "input", "wellsfargo_bank"),
    "wellsfargo_mastercard": os.path.join(
        "data", "clients", "input", "wellsfargo_mastercard"
    ),
    "wellsfargo_visa": os.path.join("data", "clients", "input", "wellsfargo_visa"),
    "wellsfargo_bank_csv": os.path.join(
        "data", "clients", "input", "wellsfargo_bank_csv"
    ),
    "client_info": os.path.join("data", "clients", "input", "client_info"),
    "first_republic_bank": os.path.join(
        "data", "clients", "input", "first_republic_bank"
    ),
}

# Parser output paths
PARSER_OUTPUT_PATHS = {
    "amazon": {
        "csv": os.path.join("data", "clients", "output", "amazon_output.csv"),
        "xlsx": os.path.join("data", "clients", "output", "amazon_output.xlsx"),
    },
    "bofa_bank": {
        "csv": os.path.join("data", "clients", "output", "bofa_bank_output.csv"),
        "xlsx": os.path.join("data", "clients", "output", "bofa_bank_output.xlsx"),
    },
    "bofa_visa": {
        "csv": os.path.join("data", "clients", "output", "bofa_visa_output.csv"),
        "xlsx": os.path.join("data", "clients", "output", "bofa_visa_output.xlsx"),
    },
    "chase_visa": {
        "csv": os.path.join("data", "clients", "output", "chase_visa_output.csv"),
        "xlsx": os.path.join("data", "clients", "output", "chase_visa_output.xlsx"),
    },
    "wellsfargo_bank": {
        "csv": os.path.join("data", "clients", "output", "wellsfargo_bank_output.csv"),
        "xlsx": os.path.join(
            "data", "clients", "output", "wellsfargo_bank_output.xlsx"
        ),
    },
    "wellsfargo_mastercard": {
        "csv": os.path.join(
            "data", "clients", "output", "wellsfargo_mastercard_output.csv"
        ),
        "xlsx": os.path.join(
            "data", "clients", "output", "wellsfargo_mastercard_output.xlsx"
        ),
        "filtered": os.path.join(
            "data", "clients", "output", "wellsfargo_mastercard_filtered.csv"
        ),
    },
    "wellsfargo_visa": {
        "csv": os.path.join("data", "clients", "output", "wellsfargo_visa_output.csv"),
        "xlsx": os.path.join(
            "data", "clients", "output", "wellsfargo_visa_output.xlsx"
        ),
    },
    "wellsfargo_bank_csv": {
        "csv": os.path.join(
            "data", "clients", "output", "wellsfargo_bank_csv_output.csv"
        ),
        "xlsx": os.path.join(
            "data", "clients", "output", "wellsfargo_bank_csv_output.xlsx"
        ),
    },
    "first_republic_bank": {
        "csv": os.path.join(
            "data", "clients", "output", "first_republic_bank_output.csv"
        ),
        "xlsx": os.path.join(
            "data", "clients", "output", "first_republic_bank_output.xlsx"
        ),
    },
    "consolidated_core": {
        "csv": os.path.join(
            "data", "clients", "output", "consolidated_core_output.csv"
        ),
        "xlsx": os.path.join(
            "data", "clients", "output", "consolidated_core_output.xlsx"
        ),
    },
    "consolidated_updated": {
        "csv": os.path.join(
            "data", "clients", "output", "consolidated_updated_output.csv"
        ),
        "xlsx": os.path.join(
            "data", "clients", "output", "consolidated_updated_output.xlsx"
        ),
    },
    "batch": {
        "csv": os.path.join("data", "clients", "output", "batch_output.csv"),
        "xlsx": os.path.join("data", "clients", "output", "batch_output.xlsx"),
    },
    "consolidated_batched": {
        "csv": os.path.join(
            "data", "clients", "output", "consolidated_batched_output.csv"
        ),
        "xlsx": os.path.join(
            "data", "clients", "output", "consolidated_batched_output.xlsx"
        ),
    },
    "state": os.path.join("data", "clients", "output", "state.json"),
}

DATA_MANIFESTS = {
    "wellsfargo_mastercard": {
        "transaction_date": "date",
        "post_date": "date",
        "reference_number": "string",
        "description": "string",
        "credits": "float",
        "charges": "float",
        "statement_date": "date",
        "file_path": "string",
        "Amount": "float",
    },
    "bofa_bank": {
        "date": "date",
        "description": "string",
        "amount": "float",
        "transaction_type": "string",
        "statement_date": "date",
        "file_path": "string",
    },
    "amazon": {
        "order_placed": "date",
        "order_number": "string",
        "order_total": "float",
        "items_quantity": "integer",
        "gift_card_amount": "float",
        "file_path": "string",
        "price": "float",
        "quantity": "integer",
        "description": "string",
        "sold_by": "string",
        "supplied_by": "string",
        "condition": "string",
        "amount": "float",
    },
    "wellsfargo_bank": {
        "date": "date",
        "description": "string",
        "deposits": "float",
        "withdrawals": "float",
        "ending_daily_balance": "float",
        "statement_date": "date",
        "file_path": "string",
        "amount": "float",
    },
    "chase_visa": {
        "date_of_transaction": "date",
        "merchant_name_or_transaction_description": "string",
        "amount": "float",
        "statement_date": "date",
        "statement_year": "integer",
        "statement_month": "integer",
        "file_path": "string",
        "date": "date",
    },
    "bofa_visa": {
        "transaction_date": "date",
        "posting_date": "date",
        "description": "string",
        "reference_number": "string",
        "account_number": "string",
        "amount": "float",
        "statement_date": "date",
        "file_path": "string",
    },
    "first_republic_bank": {
        "date": "date",
        "description": "string",
        "amount": "float",
        "transaction_type": "string",
        "statement_date": "date",
        "file_path": "string",
        "balance": "float",
    },
    "core_data_structure": {
        "transaction_date": None,
        "description": None,
        "amount": None,
        "transaction_type": None,
        "file_path": None,
        "source": None,
    },
    "wellsfargo_visa": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_visa",
        "transaction_type": lambda x: "Credit Card",
        "post_date": "post_date",
        "reference_number": "reference_number",
        "credits": "credits",
        "charges": "charges",
        "statement_date": "statement_date",
        "card_ending": "card_ending",
    },
}

TRANSFORMATION_MAPS = {
    "wellsfargo_mastercard": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",  # Assuming 'Amount' is the source column with the correct sign
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_mastercard",
        "transaction_type": lambda x: "Credit Card",
    },
    "amazon": {
        "transaction_date": "order_placed",
        "description": "description",
        "amount": "amount",  # This is the calculated amount per item
        "file_path": "file_path",
        "source": lambda x: "amazon",
        "transaction_type": lambda x: "Credit Card",
    },
    "bofa_bank": {
        "transaction_date": "date",
        "description": "description",
        "amount": "amount",  # Assuming 'amount' is the source column, and the sign may need normalization
        "file_path": "file_path",
        "source": lambda x: "bofa_bank",
        "transaction_type": lambda x: "Debit/Check",
    },
    "bofa_visa": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "bofa_visa",
        "transaction_type": lambda x: "Credit Card",
    },
    "chase_visa": {
        "transaction_date": "date",
        "description": "merchant_name_or_transaction_description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "chase_visa",
        "transaction_type": lambda x: "Credit Card",
    },
    "wellsfargo_bank": {
        "transaction_date": "date",
        "description": "description",
        "amount": "amount",  # Assuming 'amount' is the calculated source column with normalized sign
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_bank",
        "transaction_type": lambda x: "Debit/Check",
    },
    "wellsfargo_visa": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_visa",
        "transaction_type": lambda x: "Credit Card",
    },
    "wellsfargo_bank_csv": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",
        "file_path": "source_file",
        "source": lambda x: "wellsfargo_bank_csv",
        "transaction_type": "transaction_type",
    },
    "first_republic_bank": {
        "transaction_date": lambda row: (
            row["statement_end_date"]
            if "INTEREST CREDIT" in str(row["description"])
            and (pd.isna(row["transaction_date"]) or row["transaction_date"] == "")
            else row["transaction_date"]
        ),
        "description": lambda x: x["description"],
        "amount": lambda x: x["amount"],
        "transaction_type": lambda x: x["transaction_type"],
        "statement_start_date": lambda x: x["statement_start_date"],
        "statement_end_date": lambda x: x["statement_end_date"],
        "account_number": lambda x: x["account_number"],
        "file_path": lambda x: x["file_path"],
        "source": lambda x: "first_republic_bank",
    },
}

# AI Assistant Configurations
ASSISTANTS_CONFIG = {
    "AmeliaAI": {
        "model": os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18"),
        "instructions": """You are Amelia, an expert financial transaction analyzer. Your task is to analyze transactions and provide structured responses in JSON format.

IMPORTANT: Your responses MUST be valid JSON objects with the exact fields specified in the prompt. Do not include any text before or after the JSON object.

For each response:
1. Use the exact field names specified
2. Ensure all required fields are present
3. Use the exact confidence levels: "high", "medium", or "low"
4. Provide clear reasoning for your decisions
5. If suggesting new categories, include both the category and reasoning
6. For classifications, use exactly: "Business", "Personal", or "Unclassified"

Example valid response:
{
    "payee": "Example Store",
    "confidence": "high",
    "reasoning": "Clear merchant name in description"
}""",
    },
    "DaveAI": {
        "model": os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31"),
        "instructions": """You are Dave, an expert tax and business expense classifier. Your task is to classify transactions and provide structured responses in JSON format.

IMPORTANT: Your responses MUST be valid JSON objects with the exact fields specified in the prompt. Do not include any text before or after the JSON object.

For each response:
1. Use the exact field names specified
2. Ensure all required fields are present
3. Use the exact confidence levels: "high", "medium", or "low"
4. Provide clear reasoning for your decisions
5. Include tax implications when relevant
6. For classifications, use exactly: "Business", "Personal", or "Unclassified"

Example valid response:
{
    "classification": "Business",
    "confidence": "high",
    "reasoning": "Office supplies for business use",
    "tax_implications": "Fully deductible business expense"
}""",
    },
}

# System Prompts
PROMPTS = {
    "get_payee": """Identify the payee/merchant from the transaction description.

IMPORTANT: Return a JSON object with EXACTLY these field names:
{
    "payee": "string - The identified payee/merchant name",
    "confidence": "string - Must be exactly 'high', 'medium', or 'low'",
    "reasoning": "string - Explanation of the identification"
}

Example:
{
    "payee": "Walmart",
    "confidence": "high",
    "reasoning": "Clear merchant name in description"
}""",
    "get_category": """Categorize the transaction based on the description and payee.

Available categories: {categories}

IMPORTANT: Return a JSON object with EXACTLY these field names:
{
    "category": "string - The assigned category from the list",
    "confidence": "string - Must be exactly 'high', 'medium', or 'low'",
    "reasoning": "string - Explanation of the categorization",
    "suggested_new_category": "string or null - New category if needed",
    "new_category_reasoning": "string or null - Explanation for suggested new category"
}

Example:
{
    "category": "Office Supplies",
    "confidence": "high",
    "reasoning": "Purchase of office supplies from Staples",
    "suggested_new_category": null,
    "new_category_reasoning": null
}""",
    "get_classification": """Classify the transaction as business or personal.

IMPORTANT: Return a JSON object with EXACTLY these field names:
{
    "classification": "string - Must be exactly 'Business', 'Personal', or 'Unclassified'",
    "confidence": "string - Must be exactly 'high', 'medium', or 'low'",
    "reasoning": "string - Explanation of the classification",
    "tax_implications": "string or null - Tax implications if relevant"
}

Example:
{
    "classification": "Business",
    "confidence": "high",
    "reasoning": "Office supplies for business use",
    "tax_implications": "Fully deductible business expense"
}""",
}

# Standard Categories and Classifications
STANDARD_CATEGORIES = [
    "Advertising",
    "Bank Fees",
    "Business Insurance",
    "Business Travel",
    "Contract Labor",
    "Depreciation",
    "Employee Benefits",
    "Equipment",
    "Interest",
    "Legal & Professional",
    "Office Expenses",
    "Other",
    "Payroll",
    "Rent",
    "Repairs & Maintenance",
    "Supplies",
    "Taxes",
    "Training",
    "Unclassified",
    "Utilities",
    "Vehicle Expenses",
]

CLASSIFICATIONS = ["Business", "Personal", "Unclassified"]

# Ensure that all directories exist or create them
for path in PARSER_INPUT_DIRS.values():
    os.makedirs(path, exist_ok=True)


#
# You will then create a new CSV file which include the original data from your CSV file (only rows with 'ID' 1 to 9) with the new columns: category, classification, status, notes. Provide a downloadable link to the new enhanced CSV file.


FUNCTIONS = [
    {
        "name": "categorize_transaction",
        "description": "Categorizes a transaction based on its description using a specific list of business-related categories",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "The description of the transaction to categorize",
                },
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Office Supplies",
                            "Internet Expenses",
                            "Equipment Maintenance",
                            "Automobile",
                            "Service Fee",
                            "Parking and Tolls",
                            "Computer Expenses",
                            "Travel Expenses",
                            "Business Gifts",
                            "Advertising",
                            "Computer Equipment",
                            "Telecom",
                            "Office Rent",
                            "Utilities",
                            "Office Furniture",
                            "Electronics",
                            "Marketing and Promotion",
                            "Professional Fees (Legal, Accounting)",
                            "Software",
                            "Employee Benefits and Perks",
                            "Meals and Entertainment",
                            "Shipping and Postage",
                            "Personal Items",
                        ],
                    },
                    "description": "A list of predefined categories to choose from",
                },
            },
            "required": ["description", "categories"],
        },
        "response": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The category assigned to the transaction by the model from the provided list",
                }
            },
        },
    }
]


PERSONAL_EXPENSES = [
    "MUSEUMS",
    "WALMART.COM",
    "aliexpress",
    "cosmetics",
    "tok tok",
    "sephora",
    "brandy melville",
    "choicelunch",
    "forisus",
    "klarna",
    "locanda",
    "dollskill",
    "blue bottle",
    "doordash",
    "mobile purchase",
    "monaco",
    "cubik media",
    "uniqlo",
    "roblox",
    "safeway",
    "dollar tree",
    "banking payment",
    "transamerica",
    "pharmacy",
    "expert pay",
    "amazon prime",
    "apple cash",
    "Target",
    "SAKS",
    "Zelle",
    "wyre",
    "paypal",
    "Nintendo",
    "Subway",
    "fast food restaurnats",
    "Hongmall",
    "pretzels",
    "coffee",
    "clothing",
    "Venmo",
    "mexican",
    "cashreward",
    "deposit",
    "T4",
    "Zara",
    "coach",
    "quickly",
    "marina foods",
    "hollister",
    "FANTUAN",
    "TJ Max",
    "Ross",
    "BOBA",
    "HALE",
    "bristle",
    "bakery",
    "AUTO PAY",
    "ATM",
    "CVS",
    "Lovisa",
    "Marshalls",
    "shein",
    "macy",
    "starbucks",
    "AMZN Mktp",
    "Pay as you go",
    "woodlands",
    "Chegg",
    "Forever 21",
    "Gift",
    "uber eats",
    "health",
    "Checkcard",
    "laundry",
    "Maxx",
    "peet",
    "yamibuy",
    "Expertpay",
    "EATS",
    "BATH & BODY",
    "save As You Go",
    "Transfer",
    "STORIES",
    "FOREIGN TRANSACTION FEE",
    "HM.COM",
    "BAKEUSA_1",
    "GROCERY",
    "WALGREENS",
    "DOLLAR TR",
    "H&M0144",
    "POPEYES",
    "NIJIYA MARKET",
    "Autopay",
    "WESTFIELD",
    "HELLOJUNIPER.COM",
    "INFINITEA.",
    "ADRIATIC",
    "7-ELEVEN",
    "CALIFORNIA ACADEMY",
    "WWW.BOXLUNCHGIVES.COM",
    "MATCHA",
    "YESSTYLE",
    "URBANOUTFITTERS.COM",
    "PURCHASE INTEREST CHARGE",
    "CITY OF SAUSALITO SAUSALITO",
    "RUSHBOWLS_22",
    "KALOUST",
    "APPLEBEES",
    "Kate Spade",
    "Snack",
    "Hello Stranger",
]


BUSINESS_EXPENSES = [
    "Lincoln University",
    "LegalZoom",
    "printwithme",
    "fedex",
    "corporate kit",
    "LLC kit",
    "TIERRANET",
    "google",
    "apple.com",
    "shack15",
    "Anker",
    "samsung",
    "mint",
    "coinbase",
    "office rent",
]

EXPENSE_THRESHOLD = 2


def get_current_paths(config: Dict) -> Dict:
    """Get current paths based on configuration."""
    # Get base directories from config
    data_dir = config.get("data_dir", "data/clients")
    input_dir = config.get("input_dir", "data/clients")
    output_dir = config.get("output_dir", "data/clients")
    batch_output_dir = config.get("batch_output_dir", "data/clients")
    client_name = config.get("client_name")

    if not client_name:
        raise ValueError("Client name is required in configuration")

    # Handle spaces in client name for file paths
    path_client_name = client_name.replace(" ", "_")

    # Construct input directories for each parser
    input_dirs = {
        "amazon": os.path.join(input_dir, path_client_name, "input", "amazon"),
        "bofa_bank": os.path.join(input_dir, path_client_name, "input", "bofa_bank"),
        "bofa_visa": os.path.join(input_dir, path_client_name, "input", "bofa_visa"),
        "chase_visa": os.path.join(input_dir, path_client_name, "input", "chase_visa"),
        "wellsfargo_bank": os.path.join(
            input_dir, path_client_name, "input", "wellsfargo_bank"
        ),
        "wellsfargo_mastercard": os.path.join(
            input_dir, path_client_name, "input", "wellsfargo_mastercard"
        ),
        "wellsfargo_visa": os.path.join(
            input_dir, path_client_name, "input", "wellsfargo_visa"
        ),
        "wellsfargo_bank_csv": os.path.join(
            input_dir, path_client_name, "input", "wellsfargo_bank_csv"
        ),
        "client_info": os.path.join(
            input_dir, path_client_name, "input", "client_info"
        ),
        "first_republic_bank": os.path.join(
            input_dir, path_client_name, "input", "first_republic_bank"
        ),
    }

    # Construct output paths for each parser
    output_paths = {
        "amazon": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "amazon_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "amazon_output.xlsx"
            ),
        },
        "bofa_bank": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "bofa_bank_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "bofa_bank_output.xlsx"
            ),
        },
        "bofa_visa": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "bofa_visa_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "bofa_visa_output.xlsx"
            ),
        },
        "chase_visa": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "chase_visa_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "chase_visa_output.xlsx"
            ),
        },
        "wellsfargo_bank": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "wellsfargo_bank_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "wellsfargo_bank_output.xlsx"
            ),
        },
        "wellsfargo_mastercard": {
            "csv": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "wellsfargo_mastercard_output.csv",
            ),
            "xlsx": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "wellsfargo_mastercard_output.xlsx",
            ),
            "filtered": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "wellsfargo_mastercard_filtered.csv",
            ),
        },
        "wellsfargo_visa": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "wellsfargo_visa_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "wellsfargo_visa_output.xlsx"
            ),
        },
        "wellsfargo_bank_csv": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "wellsfargo_bank_csv_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "wellsfargo_bank_csv_output.xlsx",
            ),
        },
        "first_republic_bank": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "first_republic_bank_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "first_republic_bank_output.xlsx",
            ),
        },
        "consolidated_core": {
            "csv": os.path.join(
                output_dir, path_client_name, "output", "consolidated_core_output.csv"
            ),
            "xlsx": os.path.join(
                output_dir, path_client_name, "output", "consolidated_core_output.xlsx"
            ),
        },
        "consolidated_updated": {
            "csv": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "consolidated_updated_output.csv",
            ),
            "xlsx": os.path.join(
                output_dir,
                path_client_name,
                "output",
                "consolidated_updated_output.xlsx",
            ),
        },
        "batch": {
            "csv": os.path.join(
                batch_output_dir, path_client_name, "output", "batch_output.csv"
            ),
            "xlsx": os.path.join(
                batch_output_dir, path_client_name, "output", "batch_output.xlsx"
            ),
        },
        "consolidated_batched": {
            "csv": os.path.join(
                batch_output_dir,
                path_client_name,
                "output",
                "consolidated_batched_output.csv",
            ),
            "xlsx": os.path.join(
                batch_output_dir,
                path_client_name,
                "output",
                "consolidated_batched_output.xlsx",
            ),
        },
        "state": os.path.join(output_dir, path_client_name, "output", "state.json"),
    }

    return {
        "input_dirs": input_dirs,
        "output_paths": output_paths,
    }
