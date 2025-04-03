# AMELIA AI Bookkeeping

## Data Structure

### Primary Data Locations

The application uses a standardized data structure located in the root `/data` directory:

```
/data
├── clients/                    # Primary client data directory
│   ├── _template/            # Template directory structure
│   ├── _examples/            # Example client data
│   └── {client_name}/        # Individual client folders
│       ├── input/            # Client input files (PDFs, CSVs)
│       │   ├── bank1/       # Bank-specific input files
│       │   └── bank2/       # Bank-specific input files
│       ├── transactions/     # Intermediary transaction files
│       │   ├── raw/         # Raw parsed transactions
│       │   ├── classified/  # After classification
│       │   └── processed/   # Final processed transactions
│       ├── output/          # Final aggregated output files
│       └── business_profile.json  # Client business information
├── input/                    # Legacy single-client input
└── output/                   # Legacy single-client output
```

### Important Notes

1. **Primary Data Location**: All client data should be stored in `/data/clients/{client_name}/`
2. **Template Directories**:
   - `_template/` contains the standard directory structure for new clients
   - `_examples/` contains example client data for reference
3. **Legacy Locations**: 
   - `/dataextractai/data/clients/` contains symlinks and should not be used
   - `/data/input/` and `/data/output/` are from the single-client version
   - `/data/profiles/` is no longer used (moved to client folders)
   - `/data/transactions/` is legacy (moved to client folders)

## Usage Instructions

### 1. Initial Setup

1. **Create Client Profile**:
   ```bash
   # Start the interactive menu
   python main.py
   
   # Select "Create/Update Business Profile"
   # Follow prompts to enter client information
   ```

2. **Add Input Files**:
   - Place bank statements in appropriate input directories:
     - `/data/clients/{client_name}/input/{bank_name}/`
   - Supported formats:
     - Wells Fargo: PDF or CSV
     - First Republic Bank: PDF
     - Bank of America: PDF
     - Chase: PDF

### 2. Processing Workflow

1. **Run Parsers**:
   ```bash
   # From the interactive menu:
   # Select "Run Parsers"
   # Choose the client
   # Select banks to parse
   ```
   - This extracts transactions from bank statements
   - Results saved to `transactions/raw/`

2. **Normalize Transactions**:
   ```bash
   # From the menu:
   # Select "Normalize Transactions"
   # Choose the client
   ```
   - Standardizes transaction formats
   - Combines transactions from different banks
   - Removes duplicates
   - Results saved to `transactions/normalized/`

3. **Sync to Database**:
   ```bash
   # From the menu:
   # Select "Sync Transactions to Database"
   # Choose the client
   ```
   - **Important**: This operation:
     - Preserves existing classification data
     - Only updates/adds new transactions
     - Never deletes existing classifications
     - Uses transaction_id for matching

### 3. Transaction Classification

The system uses a three-pass approach for classification:

1. **Pass 1: Identify Payees**
   ```bash
   # From the menu:
   # Select "Pass 1: Identify Payees"
   # Choose Fast or Precise mode
   ```
   - Identifies merchant/payee from transaction
   - Uses AI and Brave Search for enrichment
   - Required before Pass 2

2. **Pass 2: Assign Categories**
   ```bash
   # From the menu:
   # Select "Pass 2: Assign Categories"
   # Choose Fast or Precise mode
   ```
   - Requires Pass 1 completion
   - Assigns transaction categories
   - Uses business context for better accuracy

3. **Pass 3: Classify Transactions**
   ```bash
   # From the menu:
   # Select "Pass 3: Classify Transactions"
   # Choose Fast or Precise mode
   ```
   - Requires Pass 2 completion
   - Determines business vs personal
   - Adds tax implications

4. **Process All Passes**
   ```bash
   # From the menu:
   # Select "Process All Passes"
   # Choose Fast or Precise mode
   ```
   - Runs all three passes in sequence
   - Respects dependencies between passes
   - Most efficient for full processing

### 4. Transaction Management

The new transaction management system provides detailed tracking and control:

1. **View Transaction Status**:
   ```bash
   # From the menu:
   # Select "View Transaction Status"
   ```
   - Shows progress of each pass
   - Color-coded status display:
     - Green: Completed
     - Yellow: Processing
     - Blue: Pending
     - Red: Error
     - Magenta: Skipped
     - Bright Red: Force Required

2. **Force Process Transaction**:
   ```bash
   # From the menu:
   # Select "Force Process Transaction"
   # Enter transaction ID
   # Select pass to force
   ```
   - Bypasses normal dependencies
   - Useful for fixing specific transactions
   - Can force any pass individually

3. **Reset Transaction Status**:
   ```bash
   # From the menu:
   # Select "Reset Transaction Status"
   # Enter transaction ID
   # Select passes to reset
   ```
   - Resets selected passes to 'pending'
   - Allows reprocessing specific passes
   - Preserves existing classification data

### 5. Data Export

1. **Export to Excel**:
   ```bash
   # From the menu:
   # Select "Export to Excel Report"
   ```
   - Creates formatted Excel report
   - Includes all classification data
   - Saves to client's output directory

2. **Upload to Google Sheets**:
   ```bash
   # From the menu:
   # Select "Upload to Google Sheets"
   ```
   - Uploads to configured Google Sheet
   - Adds data validation
   - Creates category dropdowns

## Development Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your environment variables
5. Run the application:
   ```bash
   python main.py
   ```

## Directory Structure

```
/
├── data/              # Primary data directory
├── dataextractai/     # Main application package
│   ├── agents/       # AI agents and classifiers
│   ├── models/       # Data models and schemas
│   ├── parsers/      # File parsers
│   └── utils/        # Utility functions
├── logs/             # Application logs
├── tests/            # Test files
└── scripts/          # Utility scripts
```

## Contributing

1. Follow the data structure guidelines above
2. Place all client data in the appropriate directories
3. Use the standardized file naming conventions
4. Keep the legacy directories clean and organized

## License

[Your license information here] 