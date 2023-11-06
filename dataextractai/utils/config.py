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
    "wellfargo_bank": os.path.join(COMMON_CONFIG["input_dir"], "wellsfargo_bank"),
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
# Ensure that all directories exist or create them
for path in PARSER_INPUT_DIRS.values():
    os.makedirs(path, exist_ok=True)
