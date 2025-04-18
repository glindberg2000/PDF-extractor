# Technical Context

## Technologies Used
1. Backend:
   - Django
   - PostgreSQL
   - OpenAI API
   - Brave Search API

2. Agent System:
   - GPT-4 for transaction analysis
   - Custom prompt engineering
   - Tool integration
   - Response validation

## Development Setup
1. Environment:
   - Python virtual environment
   - Django development server
   - PostgreSQL database
   - Environment variables for API keys

2. Configuration:
   - Agent configurations in database
   - Tool definitions
   - Prompt templates
   - Logging settings

## Technical Constraints
1. Agent Isolation:
   - Separate prompts for each agent
   - Independent field updates
   - No shared state between agents
   - Clear separation of concerns

2. Data Integrity:
   - Transaction field validation
   - Response schema validation
   - Database constraint enforcement
   - Backup system

3. Performance:
   - Efficient tool calls
   - Optimized database updates
   - Proper error handling
   - Logging overhead management

## Critical Components
1. Agent System:
   - Payee Lookup Agent
   - Classification Agent
   - Tool Integration
   - Response Processing

2. Database:
   - Transaction Model
   - Business Profile
   - Agent Configurations
   - Tool Definitions

3. Logging:
   - Request/Response logging
   - Tool call tracking
   - Error logging
   - Performance monitoring

## Current Technologies

### Core Technologies
- Python 3.8+
- **SQLite**: Primary database for storing client data, transactions, classifications, and profiles.
- **pandas**: Core library for data manipulation and processing.
- **OpenAI API (GPT-4o-mini, etc.)**: Used for AI-driven classification tasks (Payee ID, Category Assignment, Tax Classification).
- **PyPDF2 / pdfplumber / PyMuPDF**: Used by various parsers for PDF text extraction.
- **Typer / Click**: Framework for the command-line interface (`menu.py`).
- **openpyxl**: Used for generating `.xlsx` Excel reports.
- **thefuzz**: Used for fuzzy string matching (potentially in `_find_matching_transaction`).
- **Questionary**: Used for interactive prompts in the CLI.
- **Colorama**: Used for colored terminal output.
- **python-dotenv**: For managing environment variables (API keys, model names).

### CLI Frameworks
1. Legacy System (grok.py):
   - Typer for CLI interface
   - Rich for terminal UI
   - Click for command handling

2. New System (main.py):
   - Typer for CLI interface
   - Rich for enhanced UI
   - Click for advanced command handling

### Data Processing
- pandas for DataFrame operations
- numpy for numerical operations
- PyPDF2 for PDF parsing
- csv for CSV file handling

### AI Integration
- OpenAI API
- GPT-3.5/4 models
- Prompt engineering
- Response parsing

### Google Integration
- Google Sheets API v4
- Google OAuth2
- Service Account authentication

## Development Setup

### Environment
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Configuration Files
1. `.env`:
   - API keys
   - Credentials paths
   - Environment settings

2. `client_config.yaml`:
   - Client information
   - Parser settings
   - Sheet configuration

3. `sheets_config.yaml`:
   - Sheet IDs
   - Format settings
   - Column mappings

## Technical Constraints

### Parser Limitations
- PDF format compatibility
- Statement format changes
- OCR reliability
- CSV format variations

### AI Processing
- API rate limits
- Token limits
- Cost considerations
- Response validation

### Google Sheets
- Row limits
- API quotas
- Format restrictions
- Update frequency

## Planned Improvements

### Architecture
1. Class-based Pipeline:
   ```python
   class DataPipeline:
       def __init__(self, client):
           self.client = client
           self.state = ClientState(client)
           self.processor = AIProcessor(client)
           self.sheets = SheetsManager(client)
   ```

2. Enhanced Error Handling:
   ```python
   class ErrorHandler:
       def handle_parser_error(self, error):
           log_error(error)
           notify_admin(error)
           suggest_fix(error)
   ```

3. Progress Tracking:
   ```python
   class ProgressTracker:
       def update(self, stage, progress):
           self.state.update(stage, progress)
           self.notify_observers(stage, progress)
   ```

### Testing
1. Unit Tests:
   - Parser tests
   - AI processing tests
   - Sheet integration tests

2. Integration Tests:
   - End-to-end pipeline tests
   - Client configuration tests
   - Error handling tests

3. Performance Tests:
   - Large file processing
   - Batch processing
   - API rate limiting

### Documentation
1. Code Documentation:
   - Type hints
   - Docstrings
   - Example usage

2. User Documentation:
   - Setup guides
   - Usage examples
   - Troubleshooting

3. API Documentation:
   - Endpoint descriptions
   - Request/response formats
   - Error codes

## Technologies Used
- Python 3.11+
- PyPDF2 for PDF processing
- pandas for data manipulation
- PyYAML for configuration management
- Typer for CLI interface
- pytest for testing

## Development Setup
1. **Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Directory Structure**
   ```
   PDF-extractor/
   ├── clients/              # Client-specific data
   ├── data/                 # Default data directory
   ├── dataextractai/        # Main package
   │   ├── parsers/         # Statement parsers
   │   ├── utils/           # Shared utilities
   │   └── tests/           # Test suite
   └── scripts/             # CLI scripts
   ```

3. **Configuration**
   - Client config: `clients/<client_name>/client_config.yaml`
   - Global config: `dataextractai/utils/config.py`
   - Parser configs: `dataextractai/parsers/*.py`

## Technical Constraints
1. **File Formats**
   - PDF files must be text-based (not scanned)
   - CSV files must follow institution-specific formats
   - Maximum file size: 100MB per file

2. **Directory Structure**
   - Client directories must be created before use
   - Input directories must contain valid files
   - Output directories are created automatically

3. **Processing Limits**
   - Maximum 1000 transactions per file
   - Maximum 100 files per directory
   - Maximum 10 concurrent processes

4. **Memory Usage**
   - Maximum 2GB RAM per process
   - Maximum 10GB total memory usage
   - Automatic cleanup of temporary files

## Dependencies
```
pandas>=2.0.0
PyPDF2>=3.0.0
PyYAML>=6.0.0
typer>=0.9.0
pytest>=7.0.0
openpyxl>=3.0.0
python-dateutil>=2.8.0
```

## Technology Stack

### Core System (Command-Line)
1. Python Environment
   - Python 3.8+
   - Virtual environment management
   - Key packages:
     - pandas: Data processing
     - pdfplumber/PyMuPDF: PDF parsing
     - typer: CLI interface
     - gspread: Google Sheets API

2. External Services
   - OpenAI API (GPT-3.5/4)
   - Google Sheets API
   - Google Drive API

3. Data Storage
   - File system for PDFs/CSVs
   - CSV/Excel for processed data
   - Google Sheets for final output

### Web Interface (In Development)
1. Frontend
   - React
   - TypeScript
   - Mantine UI
   - WebSocket client

2. Backend
   - FastAPI
   - SQLite database
   - SQLAlchemy ORM
   - WebSocket server

## Development Setup

### Environment Setup
```bash
# Core system
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# API keys
export OPENAI_API_KEY=xxx
export GOOGLE_SHEETS_CREDENTIALS_PATH=xxx
export GOOGLE_SHEETS_ID=xxx
```

### Directory Structure
```
project_root/
├── data/
│   ├── input/          # Raw statements
│   └── output/         # Processed data
├── dataextractai/      # Core package
├── scripts/            # CLI tools
├── web/               # Web interface
│   ├── frontend/
│   └── backend/
└── tests/             # Test suite
```

### Configuration Files
1. Parser Config
   - Input/output paths
   - File patterns
   - Parser mappings

2. AI Config
   - Model selection
   - System prompts
   - Batch settings

3. Google Sheets Config
   - Credentials
   - Sheet mappings
   - Column configurations

## Development Workflow

### Command-Line Version
1. Place files in input directories
2. Run parsers: `python scripts/grok.py run-parsers`
3. Process with AI: `python scripts/grok.py process`
4. Upload to sheets: `python scripts/grok.py upload-to-sheet`

### Web Version (Future)
1. Start backend: `uvicorn main:app`
2. Start frontend: `npm start`
3. Access UI: `http://localhost:3000`

## Testing

### Test Structure
```
tests/
├── parsers/           # Parser tests
├── classifiers/       # AI tests
├── utils/             # Utility tests
└── integration/       # End-to-end tests
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test
pytest tests/parsers/test_wellsfargo.py
```

## Deployment

### Command-Line Version
1. Clone repository
2. Set up Python environment
3. Configure API keys
4. Create input directories
5. Run parsers

### Web Version (Future)
1. Build frontend
2. Configure backend
3. Set up database
4. Deploy services

## Technical Constraints

1. API Limitations
   - Image size limit: 20MB
   - Base64 encoding required
   - Rate limiting considerations
   - Token usage monitoring

2. PDF Processing
   - Image quality requirements
   - Memory usage for large PDFs
   - Processing time per page
   - Multi-page handling

3. Data Management
   - CSV file size limits
   - Database growth control
   - Disk space management
   - Backup considerations

## Security Considerations

1. API Key Management
   - Environment variables
   - .env file usage
   - Key rotation policy
   - Access control

2. Data Protection
   - Local storage only
   - No cloud transmission
   - File permissions
   - Secure deletion

3. Error Handling
   - No sensitive data in logs
   - Secure error reporting
   - Failed transaction handling
   - Recovery procedures

## Performance Optimization

1. Image Processing
   - Automatic resizing
   - Format optimization
   - Memory management
   - Batch processing

2. API Usage
   - Request batching
   - Response caching
   - Error retries
   - Rate limiting

3. Data Storage
   - Efficient CSV writing
   - Database indexing
   - File organization
   - Cleanup procedures

## Database Schema

### Core Tables

1. `clients`
   - Primary key: id
   - Name, created_at, updated_at
   - Business profile association

2. `normalized_transactions`
   - Primary key: (client_id, transaction_id)
   - Core transaction data
   - Foreign key to clients

3. `transaction_classifications`
   - Primary key: id
   - Foreign key: (client_id, transaction_id)
   - Payee, category, classification data
   - Confidence levels and reasoning
   - Timestamps

4. `transaction_status`
   - Primary key: id
   - Foreign key: (client_id, transaction_id)
   - Status per pass (pending, processing, completed, error, skipped, force_required)
   - Error messages
   - Processing timestamps

5. `transaction_cache`
   - Primary key: id
   - Foreign key: client_id
   - Cache key and pass type
   - JSON result storage
   - Timestamps

## Technologies Used

### Core Stack
- Python 3.8+
- SQLite3 for database
- OpenAI API for AI processing
- Brave Search API for enrichment

### Key Libraries
- pandas: Data processing
- click: CLI interface
- questionary: Interactive menus
- sqlite3: Database operations
- openai: AI integration
- requests: API calls

### Development Tools
- Git for version control
- GitHub for repository
- VS Code for development
- SQLite Browser for DB inspection

## Technical Constraints

### Database
- SQLite limitations
- Transaction isolation
- Concurrent access
- Cache size management

### API Integration
- Rate limiting
- Token usage
- Error handling
- Response parsing

### Processing
- Memory usage
- Processing time
- Cache effectiveness
- Status tracking overhead

## Development Setup

### Environment
1. Python virtual environment
2. Required packages
3. Database initialization
4. API key configuration

### Configuration
1. OpenAI API settings
2. Brave Search API settings
3. Database path
4. Cache settings

### Development Flow
1. Feature branches
2. Local testing
3. Status verification
4. Pull requests 

## Key Technical Implementation Details

1.  **Database (`client_db.py`)**:
    *   Uses SQLite via Python's built-in `sqlite3` module.
    *   Defines tables for `clients`, `business_profiles`, `normalized_transactions`, `transaction_classifications`, `transaction_status`, `client_expense_categories`, `tax_categories`, etc.
    *   `transaction_classifications` stores results from all 3 passes.
    *   `tax_categories` stores the predefined list of tax categories (currently loaded with '6A' as the worksheet for standard items).
    *   Worksheet column constraints exist on `tax_categories` and `transaction_classifications` (allow '6A', 'Vehicle', 'HomeOffice').

2.  **Transaction Classifier (`transaction_classifier.py`)**:
    *   Orchestrates the 3-pass process row-by-row.
    *   Uses `ClientProfileManager` to load business profile context.
    *   Uses `ClientDB` for database interactions (lookups, updates).
    *   Constructs prompts for OpenAI API calls (`_build_..._prompt` methods).
    *   Parses JSON responses from OpenAI using Pydantic models (`PayeeResponse`, `CategoryResponse`, `ClassificationResponse`).
    *   Contains matching logic (`_find_matching_transaction`) which likely uses `thefuzz` on raw descriptions.
    *   Handles fallback logic (match -> map -> AI).

3.  **Excel Formatter (`excel_formatter.py`)**:
    *   Uses `openpyxl` to create Excel files.
    *   Currently creates only "Transactions" and "Summary" sheets.
    *   Reads data directly from the database for formatting.
    *   Needs modification to read the assigned `worksheet` from the DB and create separate sheets.

4.  **Payee Normalization (Planned)**:
    *   This logic is currently missing. It would likely involve regex or string manipulation to clean payee names before Pass 1 and before matching.
    *   Could potentially be added to `TransactionNormalizer` or within the parsing stage.

## Technical Constraints & Considerations
- **Worksheet Handling**: The current database schema and classification logic strictly enforce '6A', 'Vehicle', 'HomeOffice'. Handling 'Personal' expenses requires changes (either add 'Personal' to CHECK constraint, use a separate flag/table, or handle purely in export logic).
- **Matching Robustness**: `_find_matching_transaction` needs review/enhancement to be reliable, especially concerning the use of raw vs normalized payee/description and the fields being copied.
- **AI Costs/Rate Limits**: Multiple AI calls per transaction (potentially up to 3 if no matches occur) can impact cost and speed. Rate limits need handling.
- **Scalability**: SQLite performance might become a bottleneck with very large numbers of clients or transactions.
- **Parser Maintenance**: PDF formats change, requiring parser updates.

## Dependencies (Key Ones)
```
pandas>=2.0.0
openai>=1.0.0
PyPDF2>=3.0.0 # (or other PDF libs depending on parser)
typer>=0.9.0
openpyxl>=3.0.0
python-dotenv>=0.19.0
questionary>=1.10.0
thefuzz>=0.19.0
colorama>=0.4.4
```

## Development Setup

### Instance Structure
- Main Instance (Port 8001)
  - Database: mydatabase
  - User: newuser
  - Path: /test_django/pdf_extractor_web
  - Status: Live/Production

- Test Instance (Port 8000)
  - Database: test_database
  - User: newuser
  - Path: /pdf_extractor_web
  - Status: Backup/Development

### Database Configuration
- PostgreSQL
- Main database: mydatabase
- Test database: test_database
- User: newuser
- Port: 5432

### Search Tool Configuration
- SearXNG search implementation
- Located in: /tools/search_tool/search_standalone.py
- Environment variables:
  - SEARXNG_HOST: http://localhost:8080

### Backup Strategy
- Automated backups via backup.sh
- Backs up both main and test instances
- Includes:
  - Database dumps
  - Migrations
  - Memory bank
  - Git state
- Creates restore script for emergency recovery

### Port Configuration
- Main instance: 8001
- Test instance: 8000
- Database: 5432
- SearXNG: 8080

## Development Tools
- Django Admin interface
- PostgreSQL management tools
- Docker Compose for container orchestration
- Git for version control
- Backup scripts for data preservation 

## Safety Infrastructure

### Backup Systems
1. **Database Backups**
   - Automated backup script: `backup.sh`
   - Selective database restoration
   - Pre-restore validation checks
   - Temporary backup creation

2. **Code Backups**
   - Timestamped code snapshots
   - Git commits for version control
   - Manual code backups before changes

3. **Rollback System**
   - Comprehensive rollback script: `rollback.sh`
   - Handles both code and database
   - Validates backup integrity
   - Step-by-step restoration

### Development Safety
1. **Feature Management**
   - Additive feature development
   - No removal of working code
   - Parallel feature testing
   - Clear upgrade paths

2. **Database Safety**
   - Transaction management
   - Data validation
   - Migration testing
   - Rollback capabilities

3. **Testing Infrastructure**
   - Isolated test environments
   - Feature-specific test endpoints
   - Validation procedures
   - Documentation requirements

## Development Setup

### Environment
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Configuration Files
1. `.env`:
   - API keys
   - Credentials paths
   - Environment settings

2. `client_config.yaml`:
   - Client information
   - Parser settings
   - Sheet configuration

3. `sheets_config.yaml`:
   - Sheet IDs
   - Format settings
   - Column mappings

## Technical Constraints

### Parser Limitations
- PDF format compatibility
- Statement format changes
- OCR reliability
- CSV format variations

### AI Processing
- API rate limits
- Token limits
- Cost considerations
- Response validation

### Google Sheets
- Row limits
- API quotas
- Format restrictions
- Update frequency

## Planned Improvements

### Architecture
1. Class-based Pipeline:
   ```python
   class DataPipeline:
       def __init__(self, client):
           self.client = client
           self.state = ClientState(client)
           self.processor = AIProcessor(client)
           self.sheets = SheetsManager(client)
   ```

2. Enhanced Error Handling:
   ```python
   class ErrorHandler:
       def handle_parser_error(self, error):
           log_error(error)
           notify_admin(error)
           suggest_fix(error)
   ```

3. Progress Tracking:
   ```python
   class ProgressTracker:
       def update(self, stage, progress):
           self.state.update(stage, progress)
           self.notify_observers(stage, progress)
   ```

### Testing
1. Unit Tests:
   - Parser tests
   - AI processing tests
   - Sheet integration tests

2. Integration Tests:
   - End-to-end pipeline tests
   - Client configuration tests
   - Error handling tests

3. Performance Tests:
   - Large file processing
   - Batch processing
   - API rate limiting

### Documentation
1. Code Documentation:
   - Type hints
   - Docstrings
   - Example usage

2. User Documentation:
   - Setup guides
   - Usage examples
   - Troubleshooting

3. API Documentation:
   - Endpoint descriptions
   - Request/response formats
   - Error codes

## Technologies Used
- Python 3.11+
- PyPDF2 for PDF processing
- pandas for data manipulation
- PyYAML for configuration management
- Typer for CLI interface
- pytest for testing

## Development Setup
1. **Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Directory Structure**
   ```
   PDF-extractor/
   ├── clients/              # Client-specific data
   ├── data/                 # Default data directory
   ├── dataextractai/        # Main package
   │   ├── parsers/         # Statement parsers
   │   ├── utils/           # Shared utilities
   │   └── tests/           # Test suite
   └── scripts/             # CLI scripts
   ```

3. **Configuration**
   - Client config: `clients/<client_name>/client_config.yaml`
   - Global config: `dataextractai/utils/config.py`
   - Parser configs: `dataextractai/parsers/*.py`

## Technical Constraints
1. **File Formats**
   - PDF files must be text-based (not scanned)
   - CSV files must follow institution-specific formats
   - Maximum file size: 100MB per file

2. **Directory Structure**
   - Client directories must be created before use
   - Input directories must contain valid files
   - Output directories are created automatically

3. **Processing Limits**
   - Maximum 1000 transactions per file
   - Maximum 100 files per directory
   - Maximum 10 concurrent processes

4. **Memory Usage**
   - Maximum 2GB RAM per process
   - Maximum 10GB total memory usage
   - Automatic cleanup of temporary files

## Dependencies
```
pandas>=2.0.0
PyPDF2>=3.0.0
PyYAML>=6.0.0
typer>=0.9.0
pytest>=7.0.0
openpyxl>=3.0.0
python-dateutil>=2.8.0
```

## Technology Stack

### Core System (Command-Line)
1. Python Environment
   - Python 3.8+
   - Virtual environment management
   - Key packages:
     - pandas: Data processing
     - pdfplumber/PyMuPDF: PDF parsing
     - typer: CLI interface
     - gspread: Google Sheets API

2. External Services
   - OpenAI API (GPT-3.5/4)
   - Google Sheets API
   - Google Drive API

3. Data Storage
   - File system for PDFs/CSVs
   - CSV/Excel for processed data
   - Google Sheets for final output

### Web Interface (In Development)
1. Frontend
   - React
   - TypeScript
   - Mantine UI
   - WebSocket client

2. Backend
   - FastAPI
   - SQLite database
   - SQLAlchemy ORM
   - WebSocket server

## Development Setup

### Environment Setup
```bash
# Core system
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# API keys
export OPENAI_API_KEY=xxx
export GOOGLE_SHEETS_CREDENTIALS_PATH=xxx
export GOOGLE_SHEETS_ID=xxx
```

### Directory Structure
```
project_root/
├── data/
│   ├── input/          # Raw statements
│   └── output/         # Processed data
├── dataextractai/      # Core package
├── scripts/            # CLI tools
├── web/               # Web interface
│   ├── frontend/
│   └── backend/
└── tests/             # Test suite
```

### Configuration Files
1. Parser Config
   - Input/output paths
   - File patterns
   - Parser mappings

2. AI Config
   - Model selection
   - System prompts
   - Batch settings

3. Google Sheets Config
   - Credentials
   - Sheet mappings
   - Column configurations

## Development Workflow

### Command-Line Version
1. Place files in input directories
2. Run parsers: `python scripts/grok.py run-parsers`
3. Process with AI: `python scripts/grok.py process`
4. Upload to sheets: `python scripts/grok.py upload-to-sheet`

### Web Version (Future)
1. Start backend: `uvicorn main:app`
2. Start frontend: `npm start`
3. Access UI: `http://localhost:3000`

## Testing

### Test Structure
```
tests/
├── parsers/           # Parser tests
├── classifiers/       # AI tests
├── utils/             # Utility tests
└── integration/       # End-to-end tests
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test
pytest tests/parsers/test_wellsfargo.py
```

## Deployment

### Command-Line Version
1. Clone repository
2. Set up Python environment
3. Configure API keys
4. Create input directories
5. Run parsers

### Web Version (Future)
1. Build frontend
2. Configure backend
3. Set up database
4. Deploy services

## Technical Constraints

1. API Limitations
   - Image size limit: 20MB
   - Base64 encoding required
   - Rate limiting considerations
   - Token usage monitoring

2. PDF Processing
   - Image quality requirements
   - Memory usage for large PDFs
   - Processing time per page
   - Multi-page handling

3. Data Management
   - CSV file size limits
   - Database growth control
   - Disk space management
   - Backup considerations

## Security Considerations

1. API Key Management
   - Environment variables
   - .env file usage
   - Key rotation policy
   - Access control

2. Data Protection
   - Local storage only
   - No cloud transmission
   - File permissions
   - Secure deletion

3. Error Handling
   - No sensitive data in logs
   - Secure error reporting
   - Failed transaction handling
   - Recovery procedures

## Performance Optimization

1. Image Processing
   - Automatic resizing
   - Format optimization
   - Memory management
   - Batch processing

2. API Usage
   - Request batching
   - Response caching
   - Error retries
   - Rate limiting

3. Data Storage
   - Efficient CSV writing
   - Database indexing
   - File organization
   - Cleanup procedures

## Database Schema

### Core Tables

1. `clients`
   - Primary key: id
   - Name, created_at, updated_at
   - Business profile association

2. `normalized_transactions`
   - Primary key: (client_id, transaction_id)
   - Core transaction data
   - Foreign key to clients

3. `transaction_classifications`
   - Primary key: id
   - Foreign key: (client_id, transaction_id)
   - Payee, category, classification data
   - Confidence levels and reasoning
   - Timestamps

4. `transaction_status`
   - Primary key: id
   - Foreign key: (client_id, transaction_id)
   - Status per pass (pending, processing, completed, error, skipped, force_required)
   - Error messages
   - Processing timestamps

5. `transaction_cache`
   - Primary key: id
   - Foreign key: client_id
   - Cache key and pass type
   - JSON result storage
   - Timestamps

## Technologies Used

### Core Stack
- Python 3.8+
- SQLite3 for database
- OpenAI API for AI processing
- Brave Search API for enrichment

### Key Libraries
- pandas: Data processing
- click: CLI interface
- questionary: Interactive menus
- sqlite3: Database operations
- openai: AI integration
- requests: API calls

### Development Tools
- Git for version control
- GitHub for repository
- VS Code for development
- SQLite Browser for DB inspection

## Technical Constraints

### Database
- SQLite limitations
- Transaction isolation
- Concurrent access
- Cache size management

### API Integration
- Rate limiting
- Token usage
- Error handling
- Response parsing

### Processing
- Memory usage
- Processing time
- Cache effectiveness
- Status tracking overhead

## Development Setup

### Environment
1. Python virtual environment
2. Required packages
3. Database initialization
4. API key configuration

### Configuration
1. OpenAI API settings
2. Brave Search API settings
3. Database path
4. Cache settings

### Development Flow
1. Feature branches
2. Local testing
3. Status verification
4. Pull requests 

## Key Technical Implementation Details

1.  **Database (`client_db.py`)**:
    *   Uses SQLite via Python's built-in `sqlite3` module.
    *   Defines tables for `clients`, `business_profiles`, `normalized_transactions`, `transaction_classifications`, `transaction_status`, `client_expense_categories`, `tax_categories`, etc.
    *   `transaction_classifications` stores results from all 3 passes.
    *   `tax_categories` stores the predefined list of tax categories (currently loaded with '6A' as the worksheet for standard items).
    *   Worksheet column constraints exist on `tax_categories` and `transaction_classifications` (allow '6A', 'Vehicle', 'HomeOffice').

2.  **Transaction Classifier (`transaction_classifier.py`)**:
    *   Orchestrates the 3-pass process row-by-row.
    *   Uses `ClientProfileManager` to load business profile context.
    *   Uses `ClientDB` for database interactions (lookups, updates).
    *   Constructs prompts for OpenAI API calls (`_build_..._prompt` methods).
    *   Parses JSON responses from OpenAI using Pydantic models (`PayeeResponse`, `CategoryResponse`, `ClassificationResponse`).
    *   Contains matching logic (`_find_matching_transaction`) which likely uses `thefuzz` on raw descriptions.
    *   Handles fallback logic (match -> map -> AI).

3.  **Excel Formatter (`excel_formatter.py`)**:
    *   Uses `openpyxl` to create Excel files.
    *   Currently creates only "Transactions" and "Summary" sheets.
    *   Reads data directly from the database for formatting.
    *   Needs modification to read the assigned `worksheet` from the DB and create separate sheets.

4.  **Payee Normalization (Planned)**:
    *   This logic is currently missing. It would likely involve regex or string manipulation to clean payee names before Pass 1 and before matching.
    *   Could potentially be added to `TransactionNormalizer` or within the parsing stage.

## Technical Constraints & Considerations
- **Worksheet Handling**: The current database schema and classification logic strictly enforce '6A', 'Vehicle', 'HomeOffice'. Handling 'Personal' expenses requires changes (either add 'Personal' to CHECK constraint, use a separate flag/table, or handle purely in export logic).
- **Matching Robustness**: `_find_matching_transaction` needs review/enhancement to be reliable, especially concerning the use of raw vs normalized payee/description and the fields being copied.
- **AI Costs/Rate Limits**: Multiple AI calls per transaction (potentially up to 3 if no matches occur) can impact cost and speed. Rate limits need handling.
- **Scalability**: SQLite performance might become a bottleneck with very large numbers of clients or transactions.
- **Parser Maintenance**: PDF formats change, requiring parser updates.

## Dependencies (Key Ones)
```
pandas>=2.0.0
openai>=1.0.0
PyPDF2>=3.0.0 # (or other PDF libs depending on parser)
typer>=0.9.0
openpyxl>=3.0.0
python-dotenv>=0.19.0
questionary>=1.10.0
thefuzz>=0.19.0
colorama>=0.4.4
```

## Development Setup

### Instance Structure
- Main Instance (Port 8001)
  - Database: mydatabase
  - User: newuser
  - Path: /test_django/pdf_extractor_web
  - Status: Live/Production

- Test Instance (Port 8000)
  - Database: test_database
  - User: newuser
  - Path: /pdf_extractor_web
  - Status: Backup/Development

### Database Configuration
- PostgreSQL
- Main database: mydatabase
- Test database: test_database
- User: newuser
- Port: 5432

### Search Tool Configuration
- SearXNG search implementation
- Located in: /tools/search_tool/search_standalone.py
- Environment variables:
  - SEARXNG_HOST: http://localhost:8080

### Backup Strategy
- Automated backups via backup.sh
- Backs up both main and test instances
- Includes:
  - Database dumps
  - Migrations
  - Memory bank
  - Git state
- Creates restore script for emergency recovery

### Port Configuration
- Main instance: 8001
- Test instance: 8000
- Database: 5432
- SearXNG: 8080

## Development Tools
- Django Admin interface
- PostgreSQL management tools
- Docker Compose for container orchestration
- Git for version control
- Backup scripts for data preservation 

## Development Environment
- Python 3.11
- Django 5.0.4
- PostgreSQL 16
- Docker for containerization
- Ports:
  - Main instance: 8001
  - Test instance: 8000
  - PostgreSQL main: 5432
  - PostgreSQL test: 5433

## Search Tools
- Current tool: brave_search
- Discrepancy: Database configuration points to searxng
- Tool paths:
  - brave_search: tools.search_tool.brave_search
  - searxng: tools.search_tool.search_standalone

## Logging System
- Detailed operation logging
- Progress indicators
- Transaction processing monitoring
- Terminal log integration