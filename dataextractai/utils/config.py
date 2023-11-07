# dataextractai/utils/config.py
import os

# Define the base directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Common configuration paths
COMMON_CONFIG = {
    "data_dir": os.path.join(BASE_DIR, "data"),
    "input_dir": os.path.join(BASE_DIR, "data", "input"),
    "output_dir": os.path.join(BASE_DIR, "data", "output"),
}

# Parser-specific input directories
PARSER_INPUT_DIRS = {
    "amazon": os.path.join(COMMON_CONFIG["input_dir"], "amazon"),
    "bofa_bank": os.path.join(COMMON_CONFIG["input_dir"], "bofa_bank"),
    "bofa_visa": os.path.join(COMMON_CONFIG["input_dir"], "bofa_visa"),
    "chase_visa": os.path.join(COMMON_CONFIG["input_dir"], "chase_visa"),
    "wellsfargo_bank": os.path.join(COMMON_CONFIG["input_dir"], "wellsfargo_bank"),
    "wellsfargo_mastercard": os.path.join(
        COMMON_CONFIG["input_dir"], "wellsfargo_mastercard"
    ),
}

# Parser-specific output paths
PARSER_OUTPUT_PATHS = {
    "amazon": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "amazon_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "amazon_output.xlsx"),
    },
    "bofa_bank": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "bofa_bank_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "bofa_bank_output.xlsx"),
    },
    "bofa_visa": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "bofa_visa_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "bofa_visa_output.xlsx"),
    },
    "chase_visa": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "chase_visa_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "chase_visa_output.xlsx"),
    },
    "wellsfargo_bank": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "wellsfargo_bank_output.csv"),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_bank_output.xlsx"
        ),
    },
    "wellsfargo_mastercard": {
        "csv": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_mastercard_output.csv"
        ),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_mastercard_output.xlsx"
        ),
    },
    "consolidated_core": {
        "csv": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_core_output.csv"
        ),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_core_output.xlsx"
        ),
    },
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
    "core_data_structure": {
        "transaction_date": None,
        "description": None,
        "amount": None,
        "transaction_type": None,
        "file_path": None,
        "source": None,
    },
}

TRANSFORMATION_MAPS = {
    "wellsfargo_mastercard": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",  # Use 'Amount' as it's already calculated with the correct sign
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_mastercard",
        "transaction_type": lambda x: "Credit Card",
    },
    "amazon": {
        "order_placed": "transaction_date",
        "description": "description",
        "amount": "amount",  # This is the calculated amount per item
        "file_path": "file_path",
        "source": lambda x: "amazon",
        "transaction_type": lambda x: "Credit Card",
    },
    "bofa_bank": {
        "date": "transaction_date",
        "description": "description",
        "amount": "amount",  # Sign might need to be normalized
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
        "date_of_transaction": "transaction_date",
        "merchant_name_or_transaction_description": "description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "chase_visa",
        "transaction_type": lambda x: "Credit Card",
    },
    "wellsfargo_bank": {
        "date": "transaction_date",
        "description": "description",
        "amount": "amount",  # Calculated 'amount' column with normalized sign
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_bank",
        "transaction_type": lambda x: "Debit/Check",
    },
}

# Ensure that all directories exist or create them
for path in PARSER_INPUT_DIRS.values():
    os.makedirs(path, exist_ok=True)
