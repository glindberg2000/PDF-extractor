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
}

DATA_MANIFESTS = {
    "wellsfargo_mastercard_manifest": {
        "transaction_date": "date",
        "post_date": "date",
        "reference_number": "string",
        "description": "string",
        "credits": "float",
        "charges": "float",
        "statement_date": "date",
        "file_path": "string",
        "Amount": "float",  # calculated column
    },
    "amazon_manifest": {
        "order_placed": "date",
        "order_number": "string",
        "order_total": "float",
        "items_quantity": "integer",
        "gift_card_amount": "float",
        "file_path": "string",
        "Price": "float",
        "Quantity": "integer",
        "Description": "string",
        "Sold by": "string",
        "Supplied by": "string",
        "Condition": "string",
    },
    "bofa_bank_manifest": {
        "date": "date",
        "description": "string",
        "amount": "float",  # Positive for deposits, negative for withdrawals
        "transaction_type": "string",  # This could be 'deposit' or 'withdrawal'
        "statement_date": "date",
        "file_path": "string",
    },
    "bofa_visa_manifest": {
        "transaction_date": "date",
        "posting_date": "date",
        "description": "string",
        "reference_number": "string",
        "account_number": "string",
        "amount": "float",  # This will capture monetary values, positive is a withdraw/spend
        "statement_date": "date",
        "file_path": "string",
    },
    "chase_visa_manifest": {
        "date_of_transaction": "date",
        "merchant_name_or_transaction_description": "string",
        "amount": "float",  # This will capture monetary values, assuming spendings are positive
        "statement_date": "date",
        "statement_year": "int",  # Afull year number
        "statement_month": "int",  # numerical representation of the month
        "file_path": "string",
        "date": "date",  # This is the calculated proper date including the year
    },
    "wellsfargo_bank_manifest": {
        "date": "date",
        "description": "string",
        "deposits": "float",  # Assuming this column contains numerical values for deposits
        "withdrawals": "float",  # Assuming this column contains numerical values for withdrawals
        "ending_daily_balance": "float",  # Assuming this column contains numerical values for the balance
        "statement_date": "date",
        "file_path": "string",
        "amount": "float",  # The new calculated column
    },
    "wellsfargo_mastercard": {
        "transaction_date": "date",
        "post_date": "date",
        "reference_number": "string",
        "description": "string",
        "credits": "float",  # If this field is cleaned up to be numerical
        "charges": "float",  # If this field is cleaned up to be numerical
        "statement_date": "date",
        "file_path": "string",
        "Amount": "float",  # This column already contains the correct signed values
    },
}


# Ensure that all directories exist or create them
for path in PARSER_INPUT_DIRS.values():
    os.makedirs(path, exist_ok=True)
