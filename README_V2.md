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

### Data Organization

1. **Client Data**
   - Each client has their own directory under `/data/clients/{client_name}/`
   - Input files are organized by bank in `input/{bank_name}/`
   - Business profile is stored as `business_profile.json` in the client root

2. **Transaction Processing**
   - Raw parsed transactions go in `transactions/raw/`
   - Classified transactions go in `transactions/classified/`
   - Final processed transactions go in `transactions/processed/`
   - Aggregated output files go directly in `output/`

3. **File Naming Conventions**
   - Raw transactions: `{bank_name}_raw.csv`
   - Classified transactions: `{bank_name}_classified.csv`
   - Processed transactions: `{bank_name}_processed.csv`
   - Final outputs: `{bank_name}_final.csv`

### Setting Up New Clients

1. **Using Template Directory**:
   ```bash
   # Copy the template directory structure
   cp -r /data/clients/_template /data/clients/{new_client_name}
   
   # Or use the example as a starting point
   cp -r /data/clients/_examples/example_client /data/clients/{new_client_name}
   ```

2. **Manual Setup** (if needed):
   ```bash
   mkdir -p /data/clients/{client_name}/{input/{bank1,bank2},transactions/{raw,classified,processed},output}
   ```

### Migration Notes

If you have data in legacy locations:
1. Move client data to `/data/clients/{client_name}/`
2. Create the new directory structure (preferably using the template)
3. Move transaction files to appropriate subdirectories
4. Move business profiles to client root
5. Archive or delete legacy directories

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