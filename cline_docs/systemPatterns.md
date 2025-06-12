# System Patterns

## Architecture Overview

### Current Structure
1. Client-Based Organization:
   ```
   data/clients/
   ├── _template/              # Template for new clients
   ├── _examples/             # Example configurations
   └── [client_name]/         # Client-specific data
       ├── client_config.yaml # Client configuration
       ├── input/            # Parser-specific input directories
       └── output/           # Processed output files
   ```

2. Parser System:
   - Directory-based parsers (Wells Fargo, First Republic)
   - File-based parsers (Chase, BoA)
   - CSV parsers (Wells Fargo Bank)

3. Configuration Management:
   - Global settings in config.py
   - Client-specific overrides in client_config.yaml
   - Parser-specific configurations

### Planned Enhancements

1. Data Processing Pipeline:
   ```python
   class Pipeline:
       def __init__(self, client: str):
           self.client = client
           self.config = load_client_config(client)
           
       def process(self):
           # 1. Parse Documents
           parsed_data = self.run_parsers()
           
           # 2. Consolidate Data
           consolidated = self.consolidate(parsed_data)
           
           # 3. AI Processing
           processed = self.process_with_ai(consolidated)
           
           # 4. Upload to Sheets
           self.upload_to_sheets(processed)
   ```

2. State Management:
   ```python
   class ClientState:
       def __init__(self, client: str):
           self.client = client
           self.state_file = f"data/clients/{client}/state.json"
           
       def get_progress(self) -> dict:
           return load_json(self.state_file)
           
       def update_progress(self, status: dict):
           save_json(self.state_file, status)
   ```

3. AI Processing:
   ```python
   class AIProcessor:
       def __init__(self, client: str):
           self.config = load_client_config(client)
           self.ai = self.config.ai_settings
           
       def process_batch(self, batch: pd.DataFrame):
           for row in batch.iterrows():
               result = self.categorize(row)
               self.validate(result)
               yield result
   ```

4. Google Sheets Integration:
   ```python
   class SheetsManager:
       def __init__(self, client: str):
           self.sheets_config = get_client_sheets_config(client)
           
       def upload(self, data: pd.DataFrame):
           sheet = self.get_or_create_sheet()
           self.format_sheet(sheet)
           self.upload_data(data)
           self.setup_validations()
   ```

## Core Architecture

### 1. Parser System
- Modular parser architecture
- Each parser handles specific document format
- Standardized output format
- Transaction normalization

### 2. AI Classifier System
- Two-pass classification approach:
  1. Payee Identification
     - Uses AI to identify merchant/payee
     - Provides context for categorization
  2. Category Assignment
     - Uses payee + description to determine category
     - Predefined category list
  3. Classification
     - Uses category + description to classify
     - Business vs personal classification
- Client Profile Integration
  - Uses client business info for context
  - Custom categories per client
  - Business type and description

### 3. Data Flow
1. Document Processing
   - PDF/CSV input files
   - Parser extraction
   - Transaction normalization
2. AI Classification
   - Batch processing
   - Review workflow
   - Classification storage
3. Output Generation
   - CSV/Excel export
   - Google Sheets integration

## Design Patterns

1. Factory Pattern:
   - Parser factory for different statement types
   - AI processor factory for different assistants
   - Sheet manager factory for different formats

2. Strategy Pattern:
   - Different parsing strategies per bank
   - Different AI processing strategies
   - Different sheet formatting strategies

3. Observer Pattern:
   - Progress tracking
   - State updates
   - Error logging

4. Command Pattern:
   - CLI commands
   - Batch processing
   - Sheet operations

## Error Handling

1. Parser Errors:
   - PDF reading errors
   - Format validation
   - Data extraction failures

2. AI Processing Errors:
   - API failures
   - Rate limiting
   - Invalid responses

3. Sheets Errors:
   - Authentication
   - Permission issues
   - API limits

## Logging

1. System Logs:
   - Parser operations
   - AI processing
   - Sheet operations

2. Client Logs:
   - Progress tracking
   - Error reporting
   - State changes

3. Audit Logs:
   - Data modifications
   - Configuration changes
   - User actions

## Key Technical Decisions

1. **Client Isolation**
   - Separate directories for each client
   - Independent configuration per client
   - Isolated data processing

2. **Path Management**
   - Dynamic path generation
   - Configuration-based paths
   - Directory validation
   - Automatic directory creation

3. **Data Transformation**
   - Standardized data structure
   - Institution-specific transformations
   - Configurable transformation maps
   - Validation at each step

4. **Error Handling**
   - Graceful error recovery
   - Detailed error logging
   - Directory validation
   - File format validation

## Design Patterns

### 1. Parser Pattern
- Factory pattern for parser creation
- Strategy pattern for parsing logic
- Template pattern for common operations
- Observer pattern for logging

### 2. AI Classification Pattern
- Chain of Responsibility for classification passes
- Strategy pattern for AI models
- Factory pattern for client profiles
- Observer pattern for batch processing

### 3. Data Management Pattern
- Repository pattern for data access
- Factory pattern for data transformation
- Strategy pattern for normalization
- Observer pattern for updates

## Key Technical Patterns

### 1. Parser Pattern
- Standard interface: `run()` method
- Returns pandas DataFrame
- Handles file reading and parsing
- Standardizes column names

### 2. Data Transformation
- Source-specific transformation maps
- Standard core data structure
- Consistent date/amount handling
- File path tracking

### 3. AI Processing
- Batch processing with state management
- Multiple AI assistant options
- Client context integration
- Error handling and recovery

### 4. Google Sheets Integration
- OAuth2 authentication
- Automated column setup
- Dropdown validations
- Batch upload support

## Configuration Patterns

### 1. Path Configuration
```python
PARSER_INPUT_DIRS = {
    "amazon": "data/input/amazon",
    "bofa_bank": "data/input/bofa_bank",
    ...
}
```

### 2. Transformation Maps
```python
TRANSFORMATION_MAPS = {
    "source_name": {
        "target_col": "source_col",
        ...
    }
}
```

### 3. AI Configuration
```python
ASSISTANTS_CONFIG = {
    "AmeliaAI": {...},
    "DaveAI": {...}
}
```

## Extension Points
1. New Parser Addition
   - Add parser file
   - Update config paths
   - Add transformation map

2. New AI Assistant
   - Add to ASSISTANTS_CONFIG
   - Define system prompt
   - Set model parameters

3. New Export Format
   - Add export function
   - Update config paths
   - Implement transformation 

## Transaction Processing System

### Three-Pass Approach
1. Payee Identification
   - Normalizes transaction descriptions
   - Identifies unique payees
   - Assigns confidence levels
   - Provides reasoning for decisions

2. Category Assignment
   - Uses payee information
   - Considers transaction context
   - Suggests new categories when needed
   - Maintains category consistency

3. Classification
   - Determines business vs personal nature
   - Considers tax implications
   - Provides detailed reasoning
   - Ensures proper capitalization

### Caching System
1. Cache Storage
   - JSON file in client output directory
   - Persistent between program runs
   - Separate entries for each pass
   - Normalized cache keys

2. Cache Key Structure
   - Description (normalized)
   - Payee (for category/classification)
   - Category (for classification)
   - Pipe-separated format

3. Cache Operations
   - Load on startup
   - Save after each new result
   - Clear logging of hits/misses
   - Error handling for file operations

### Error Handling
1. Transaction Level
   - Individual transaction failures
   - Default values for errors
   - Detailed error messages
   - Progress preservation

2. System Level
   - Cache file operations
   - API call failures
   - Data validation
   - Progress tracking

### Progress Management
1. Save Points
   - After each pass
   - After each transaction
   - After cache updates
   - Before program exit

2. Resume Capability
   - Start from any pass
   - Skip cached transactions
   - Maintain consistency
   - Clear progress logging 

## Parser Registration and Detection (NEW)
- All modularized parsers (CSV and PDF) must inherit from BaseParser and implement a strict can_parse method.
- The autodiscover_parsers() utility recursively imports all parser modules, ensuring every parser is registered in the ParserRegistry.
- The detection utility uses the registry to select the correct parser for any file, or returns None if no match is found.
- Detection logic is strict: CSV parsers require exact header and column order matches; PDF parsers use robust, account-type-specific phrase detection.
- This system is robust, extensible, and eliminates manual import/registration errors.

## Metadata Extraction Pattern (NEW)
- Modular parsers can expose an `extract_metadata(input_path)` method to return all key metadata fields for a statement file.
- Example: `ChaseCheckingParser.extract_metadata(path)` returns a dict with bank_name, account_type, parser_name, file_type, account_number, statement_date, account_holder_name, address, statement_period_start, statement_period_end.
- This method is robust to PDF quirks, works across all tested files, and is callable on demand by downstream consumers (e.g., LedgerDev, CLI, Django, etc.).
- Pattern: Keep all extraction logic self-contained and robust to formatting variations. Test across all available statement files before release.

# System Patterns: Iterative Extraction and Debugging

- When standard extraction (regex, line search) fails, escalate to:
  - Aggressive normalization (remove whitespace, unicode normalization)
  - Alternate extraction libraries (e.g., pdfplumber)
  - Brute-force substring or character search
- Always print debug output for each attempt to aid in diagnosis.
- Document each step and result in the memory bank for future reference.
- This pattern ensures that even edge cases are eventually handled or at least diagnosed for future improvement. 

## Canonical Parser Output Contract (2025-06)

### Canonical Pydantic Models (Finalized)
```python
from typing import Optional, List, Dict
from pydantic import BaseModel

class TransactionRecord(BaseModel):
    transaction_date: str  # ISO 8601, e.g. "2024-12-13"
    amount: float  # Transaction amount
    description: str  # Raw transaction description from statement
    posted_date: Optional[str] = None  # Date transaction was posted, if available
    transaction_type: Optional[str] = None  # e.g. "debit", "credit", only if present in source
    extra: Optional[Dict] = None  # For parser/bank-specific fields

class StatementMetadata(BaseModel):
    statement_date: Optional[str] = None  # Statement end date (ISO 8601)
    statement_period_start: Optional[str] = None  # Statement period start date
    statement_period_end: Optional[str] = None  # Statement period end date
    statement_date_source: Optional[str] = None  # Where the date was extracted from
    original_filename: Optional[str] = None  # Original uploaded filename
    account_number: Optional[str] = None  # Account number for the statement
    bank_name: Optional[str] = None  # e.g., "Chase", "Capital One"
    account_type: Optional[str] = None  # e.g., "checking", "savings", "VISA"
    parser_name: Optional[str] = None  # Name of the parser used
    parser_version: Optional[str] = None  # Version of the parser used
    currency: Optional[str] = "USD"  # Currency, default "USD"
    extra: Optional[Dict] = None  # For parser/bank-specific metadata

class ParserOutput(BaseModel):
    transactions: List[TransactionRecord]  # List of transactions
    metadata: Optional[StatementMetadata] = None  # Statement-level metadata
    schema_version: Optional[str] = "1.0"  # Output schema version
    errors: Optional[List[str]] = None  # List of error messages
    warnings: Optional[List[str]] = None  # List of warning messages
```

### Enforcement Policy
- All modularized parsers must validate output with these models before returning.
- Only fields in TransactionRecord are allowed in the transaction list; all context/statement-level info goes in StatementMetadata.
- Use `extra` for parser/bank-specific or experimental fields.

### Transformation/Normalization Rules
- Each parser/source uses a transformation map (see TRANSFORMATION_MAPS in dataextractai/utils/config.py) to map legacy/variant fields to canonical fields.
- Required fields: `transaction_date`, `description`, `amount`.
- Dates must be ISO 8601 (YYYY-MM-DD), amounts must be floats, and all required fields must be present or set to None.
- Lambda functions are used for computed/static fields.

### Schema Validation Requirement
- A dedicated test/validation script must run each parser on sample data and validate the output using the canonical Pydantic models.
- The test fails if any required field is missing or the schema is not strictly followed.

### Migration Notes
- Remove all context fields (e.g., statement_file, client, file_path) from per-transaction output.
- Only include fields present in TransactionRecord in the transaction list.
- All statement-level/contextual info goes in StatementMetadata.
- Use the `extra` field for any parser/bank-specific or experimental fields.
- Ingestion pipeline will attach metadata to transactions as needed.

### Status
- All modularized parsers can be refactored to this contract with moderate effort. Most already separate transaction and metadata fields, so migration is straightforward.
- This contract is now the standard for all new parser development and ingestion integration. 