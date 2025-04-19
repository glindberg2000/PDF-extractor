# System Patterns

## Architecture Overview

The application processes financial documents (PDF, CSV) for multiple clients, extracts transactions, classifies them using AI and business rules, and outputs structured data suitable for tax preparation.

### Core Components
1.  **Client Manager**: Handles client-specific configurations (`client_config.yaml`) and business profiles (`business_profile.json`).
2.  **Document Parsers**: Extract raw transaction data (Date, Description, Amount) from various bank statement formats.
3.  **Transaction Normalizer**: Cleans transaction data, specifically aiming to normalize payee names (e.g., remove store numbers, locations) for consistent matching. (**Note: Payee normalization is planned but not yet implemented.**)
4.  **Database (`client_db.py`)**: Stores client info, business profiles, normalized transactions (`normalized_transactions` table), and classification results (`transaction_classifications` table).
5.  **Transaction Classifier (`transaction_classifier.py`)**: Orchestrates the multi-pass classification process.
    *   **Pass 1 (Payee ID)**: Uses AI to identify payee from description. Stores result.
    *   **Pass 2 (Category Assignment)**: Uses AI (+ payee, desc, business profile) to assign a general expense category. Stores result.
    *   **Pass 3 (Tax/Worksheet Classification)**: Attempts to determine the final tax category and worksheet.
        *   **Matching Logic**: Attempts to find previous transactions with similar descriptions (`_find_matching_transaction`). (**Note: Currently uses raw description, needs update for normalized payee. Needs to ensure all relevant fields are copied.**).
        *   **Direct Mapping**: If no match, attempts to map Pass 2 category name directly to a `tax_categories` entry.
        *   **AI Fallback**: If no match or direct map, uses AI (+ context) to determine `tax_category_id`, `business_percentage`, and `worksheet`. (**Note: Current AI prompt requests worksheet, but DB constraint limits it to '6A', 'Vehicle', 'HomeOffice'. Logic for 'Personal' assignment and using business profile rules for Auto/HomeOffice is missing.**)
6.  **Output Formatter (`excel_formatter.py`)**: Generates output files.
    *   **Excel**: Creates an Excel report. (**Note: Currently creates only 'Transactions' and 'Summary' sheets. Logic to create separate sheets for 6A, Auto, HomeOffice, Personal is missing.**)
    *   **Google Sheets**: (Optional) Uploads data.
7.  **Menu System (`menu.py`)**: Provides CLI interface for triggering processing (primarily row-by-row). (**Note: Row-by-row processing seems to be the standard now.**)

### Data Flow
1.  User selects client and triggers processing via `menu.py`.
2.  Parsers extract transactions.
3.  (Planned) Transactions are normalized (payee cleaning).
4.  Transactions are saved to `normalized_transactions` table.
5.  `transaction_classifier.py` processes each transaction row-by-row:
    *   Pass 1 -> Pass 2 -> Pass 3.
    *   Each pass attempts lookup/matching before potentially using AI.
    *   Results are stored/updated in the `transaction_classifications` table.
6.  User triggers export via `menu.py`.
7.  `excel_formatter.py` reads data from DB and generates the Excel file (currently needs worksheet separation logic).

## Key Design Patterns & Decisions

1.  **Multi-Pass Processing**: Breaks down classification into logical steps (Payee -> Category -> Tax/Worksheet).
2.  **Client-Specific Context**: Leverages business profiles stored per client to guide AI classification.
3.  **Database as Source of Truth**: Classification results and transaction data are stored centrally in SQLite.
4.  **Row-by-Row Processing**: Ensures each transaction is fully processed through all passes before moving to the next.
5.  **Fallback Logic**: Uses matching/mapping first, then resorts to AI, aiming for consistency and efficiency.
6.  **Modular Components**: Separates parsing, classification, DB interaction, and output formatting.

## Areas for Improvement / Gaps
- **Payee Normalization**: Needs implementation in the normalization/parsing stage and integration into matching logic.
- **Matching Logic**: Enhance `_find_matching_transaction` to use normalized payees and copy all relevant fields consistently.
- **Worksheet Assignment Logic**: Implement rules (potentially using business profile) to assign transactions to 'Auto', 'HomeOffice', or 'Personal' worksheets. Update DB constraints/handling if 'Personal' needs to be stored differently.
- **Excel Formatting**: Add logic to `excel_formatter.py` to create separate sheets based on the final assigned worksheet.
- **Business Profile Rules**: Integrate business profile rules more directly into Pass 3 worksheet assignment (beyond just AI context).
- **Cache Removal Verification**: While explicit caching code seems gone, ensure no remnants interfere with the DB lookup/matching approach.

## Current Structure
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

## Transaction Processing

### Multi-Pass Transaction Processing
The system uses a three-pass approach for transaction classification:

1. Pass 1 - Payee Identification
   - Identifies payee from transaction description
   - Extracts business description and general category
   - Uses smart caching with field-level granularity
   - Maintains confidence scores for each field

2. Pass 2 - Business Classification
   - Determines business vs personal nature
   - Assigns business percentage
   - Provides business context
   - Uses Pass 1 data for informed decisions

3. Pass 3 - Tax Classification
   - Assigns tax categories
   - Determines worksheet placement
   - Analyzes tax implications
   - Uses data from Pass 1 and 2

### Smart Caching System
- Field-level granularity for caching
- Only performs fresh lookups when fields are missing
- Preserves high-confidence cached data
- Merges new data with existing cache entries
- Uses normalized transaction descriptions as cache keys
- Maintains separate caches for each processing pass

### Data Flow
```
PDF Files → Extraction → Normalization → Database
                                          ↓
                                    Pass 1 (Payee)
                                          ↓
                                    Pass 2 (Business)
                                          ↓
                                    Pass 3 (Tax)
                                          ↓
                                    Final Report
```

### Database Schema
- transaction_classifications
  - Core transaction data
  - Classification fields
  - Confidence scores
  - Processing timestamps

- transaction_status
  - Status tracking per pass
  - Error messages
  - Processing timestamps
  - Dependencies

### Caching Structure
```json
{
  "normalized_description": {
    "payee": "...",
    "payee_confidence": 0.95,
    "business_description": "...",
    "general_category": "...",
    "last_updated": "timestamp",
    "source": "ai/manual/cache"
  }
}
```

## Key Technical Decisions

### Smart Caching Strategy
- Decision: Implement field-level caching with selective updates
- Rationale: 
  - Reduces unnecessary API calls
  - Preserves high-confidence data
  - Allows gradual improvement of data quality
  - Maintains processing speed while ensuring completeness

### Multi-Pass Architecture
- Decision: Separate processing into three distinct passes
- Rationale:
  - Clear separation of concerns
  - Better error isolation
  - Improved data quality through progressive refinement
  - Easier debugging and maintenance

### Database-Backed Progress Tracking
- Decision: Use SQLite for progress tracking
- Rationale:
  - Reliable persistence
  - Transaction support
  - Easy querying for status
  - Simple backup and restore

## Error Handling

### Transaction-Level Isolation
- Each transaction processed independently
- Errors don't affect other transactions
- Clear error messages preserved in database
- Ability to retry failed transactions

### Progress Preservation
- Status tracked per transaction per pass
- Automatic checkpointing
- Resume capability from any point
- Force processing option for dependencies

## Data Validation

### Input Validation
- PDF parsing validation
- Transaction normalization checks
- Data type verification
- Required field validation

### Output Validation
- Classification value validation
- Confidence score checks
- Tax category verification
- Report format validation

## Reporting

### Excel Export
- Comprehensive column set
- Data validation rules
- Proper formatting
- Summary calculations

### Schedule 6A Report
- Standard format
- Required columns
- Tax calculations
- Business summaries

## Database Structure

### Core Tables
1. `clients`
   - Client identification
   - Business profile link
   - Metadata

2. `normalized_transactions`
   - Core transaction data
   - Client association
   - Unique constraints

3. `transaction_classifications`
   - Classification results
   - Multi-pass data
   - Confidence levels
   - Reasoning storage

4. `transaction_status`
   - Processing status
   - Error tracking
   - Timestamps
   - Dependencies

5. `transaction_cache`
   - Cached results
   - Pass-specific data
   - Cache invalidation
   - Performance optimization

### Table Relationships
1. Client Relationships
   - One-to-many with transactions
   - One-to-one with profile
   - Cascade operations

2. Transaction Relationships
   - One-to-one with status
   - One-to-one with classifications
   - Many-to-one with cache

## User Interface

### Menu System
1. Transaction Processing
   - Individual pass options
   - Batch processing
   - Progress tracking
   - Status display

2. Status Management
   - Color-coded display
   - Detailed transaction view
   - Force processing
   - Status reset

3. Data Management
   - Cache management
   - Export options
   - Database operations
   - Profile management

### Progress Tracking
1. Visual Indicators
   - Color coding
   - Status counts
   - Error highlighting
   - Progress updates

2. User Feedback
   - Operation status
   - Error messages
   - Success confirmation
   - Processing updates

## Future System Extensions

### Web Application Architecture

#### Frontend Architecture
```
React App
├── Components/
│   ├── TransactionManager/     # Transaction CRUD
│   ├── ProcessingDashboard/    # Status monitoring
│   ├── BatchControls/          # Batch operations
│   └── Reports/                # Reporting interface
├── Services/
│   ├── API/                    # Backend communication
│   ├── WebSocket/              # Real-time updates
│   └── Auth/                   # Authentication
└── State/
    ├── Redux Store/            # Global state
    └── Context/                # Feature-specific state
```

#### Backend Architecture
```
FastAPI Backend
├── Routes/
│   ├── transactions/           # Transaction endpoints
│   ├── processing/             # Processing controls
│   ├── websocket/             # Real-time updates
│   └── auth/                   # Authentication
├── Services/
│   ├── TransactionService/     # Business logic
│   ├── ProcessingService/      # Processing management
│   └── WebSocketManager/       # Real-time communication
└── Database/
    └── Models/                 # SQLAlchemy models
```

### Intelligent Chatbot Architecture

#### Core Components
```
Chatbot System
├── ContextManager/
│   ├── ClientContext/          # Client profile & rules
│   ├── TransactionHistory/     # Historical data
│   └── RelationshipGraph/      # Entity relationships
├── NLPEngine/
│   ├── IntentRecognition/      # Command understanding
│   ├── EntityExtraction/       # Key information
│   └── RuleGeneration/         # Dynamic rules
├── ActionEngine/
│   ├── MCPInterface/           # Database operations
│   ├── RuleProcessor/          # Rule application
│   └── ChangeTracker/          # Audit logging
└── ValidationEngine/
    ├── DataValidator/          # Input validation
    └── ConstraintChecker/      # Business rules
```

#### Integration Points
1. MCP Interface
   ```python
   class MCPInterface:
       def __init__(self):
           self.db = DatabaseConnection()
           self.validator = DataValidator()
           self.tracker = ChangeTracker()
           
       async def apply_changes(self, changes: List[Change]):
           # Validate changes
           validated = self.validator.validate(changes)
           
           # Apply changes through MCP
           results = await self.db.execute_mcp(validated)
           
           # Track changes
           self.tracker.log_changes(results)
           
           return results
   ```

2. Natural Language Processing
   ```python
   class NLPProcessor:
       def __init__(self):
           self.context = ContextManager()
           self.intent = IntentRecognizer()
           self.entities = EntityExtractor()
           
       def process_command(self, text: str) -> Action:
           # Extract intent and entities
           intent = self.intent.recognize(text)
           entities = self.entities.extract(text)
           
           # Apply context
           contextualized = self.context.apply(intent, entities)
           
           return Action.from_context(contextualized)
   ```

3. Rule Engine
   ```python
   class RuleEngine:
       def __init__(self):
           self.rules = RuleManager()
           self.processor = RuleProcessor()
           
       def apply_rules(self, transactions: List[Transaction]):
           # Get applicable rules
           rules = self.rules.get_active_rules()
           
           # Apply rules
           results = self.processor.process(transactions, rules)
           
           return results
   ```

### Key Technical Considerations

1. Real-time Updates
   - WebSocket for live status
   - Event-driven architecture
   - State synchronization
   - Optimistic updates

2. Data Consistency
   - Transaction boundaries
   - Atomic operations
   - Rollback capability
   - Version control

3. Security
   - Authentication
   - Authorization
   - Audit logging
   - Data validation

4. Scalability
   - Microservices architecture
   - Async processing
   - Caching strategy
   - Load balancing

### Implementation Strategy

1. Phase 1: Core Web App
   - Basic CRUD operations
   - Authentication system
   - Real-time status updates
   - Simple reporting

2. Phase 2: Enhanced Processing
   - Web-based reprocessing
   - Progress monitoring
   - Error handling
   - Batch operations

3. Phase 3: Chatbot Integration
   - Basic query capabilities
   - Context understanding
   - Simple updates
   - Audit logging

4. Phase 4: Advanced Features
   - Complex relationship handling
   - Target-based adjustments
   - Pattern recognition
   - Bulk operations 

### Tax Workbook System Architecture

#### Core Components
```
Tax Workbook System
├── WorkbookManager/
│   ├── Schedule6AManager/      # Core business expense tracking
│   ├── DocumentManager/        # Form management and tracking
│   ├── ProgressTracker/        # Completion status tracking
│   └── ValidationEngine/       # Cross-form validation
├── DocumentProcessor/
│   ├── FormDetector/          # Identify form types
│   ├── OCREngine/             # Extract form data
│   ├── DataValidator/         # Validate extracted data
│   └── StorageManager/        # Document storage
├── CalculationEngine/
│   ├── Schedule6ACalculator/  # Business expense calculations
│   ├── CrossFormCalculator/   # Multi-form calculations
│   ├── TaxImplicationEngine/  # Tax impact analysis
│   └── SummaryGenerator/      # Final calculations
└── ReportingEngine/
    ├── ProgressReporter/      # Status reporting
    ├── ValidationReporter/    # Error and warning reports
    ├── CompletionChecker/     # Final review system
    └── ExportManager/         # Final document export
```

#### Data Models
```python
class TaxWorkbook:
    def __init__(self, tax_year: int, client_id: str):
        self.tax_year = tax_year
        self.client_id = client_id
        self.sections = {}
        self.documents = {}
        self.progress = WorkbookProgress()
        self.validation = ValidationStatus()

class WorkbookSection:
    def __init__(self, section_id: str):
        self.id = section_id
        self.required_docs = []
        self.manual_entries = {}
        self.calculations = {}
        self.status = SectionStatus()
        self.validation = SectionValidation()

class TaxDocument:
    def __init__(self, doc_type: str, file_path: str):
        self.type = doc_type
        self.file_path = file_path
        self.extracted_data = {}
        self.validation_status = {}
        self.processing_status = ProcessingStatus()
```

#### Integration Points
1. Document Processing
   ```python
   class DocumentProcessor:
       def __init__(self):
           self.ocr = OCREngine()
           self.validator = DataValidator()
           self.storage = StorageManager()
           
       async def process_document(self, document: TaxDocument):
           # Detect form type
           doc_type = self.detect_type(document)
           
           # Extract data
           data = await self.ocr.extract_data(document)
           
           # Validate
           validation = self.validator.validate(data, doc_type)
           
           # Store
           self.storage.store(document, data, validation)
           
           return ProcessingResult(data, validation)
   ```

2. Progress Tracking
   ```python
   class ProgressTracker:
       def __init__(self, workbook: TaxWorkbook):
           self.workbook = workbook
           self.checklist = Checklist()
           self.validator = ValidationEngine()
           
       def update_status(self):
           # Check document completeness
           docs_status = self.check_required_docs()
           
           # Validate data
           data_status = self.validator.validate_all()
           
           # Update progress
           self.workbook.progress.update(docs_status, data_status)
           
           return CompletionStatus(docs_status, data_status)
   ```

3. Calculation Engine
   ```python
   class TaxCalculator:
       def __init__(self, workbook: TaxWorkbook):
           self.workbook = workbook
           self.rules = TaxRules()
           
       def calculate_all(self):
           # Process Schedule 6A
           sched_6a = self.calculate_schedule_6a()
           
           # Process other forms
           other_calcs = self.process_other_forms()
           
           # Generate summaries
           summaries = self.generate_summaries()
           
           return CalculationResults(sched_6a, other_calcs, summaries)
   ```

### Key Technical Considerations

1. Document Management
   - Secure storage
   - Version control
   - Access tracking
   - Backup system

2. Data Extraction
   - OCR accuracy
   - Form recognition
   - Data validation
   - Error correction

3. Progress Tracking
   - Real-time updates
   - Dependency tracking
   - Validation status
   - Completion criteria

4. Security
   - Document encryption
   - Access control
   - Audit logging
   - Data retention

### Implementation Strategy

1. Phase 1: Core Schedule 6A Integration
   - Link with transaction processing
   - Basic progress tracking
   - Simple document storage
   - Essential calculations

2. Phase 2: Document Management
   - Document upload system
   - Basic form recognition
   - Manual data entry
   - Storage system

3. Phase 3: Advanced Processing
   - OCR implementation
   - Automated data extraction
   - Cross-form validation
   - Progress dashboard

4. Phase 4: Complete System
   - Full workbook tracking
   - Advanced calculations
   - Comprehensive validation
   - Final review system 

### QuickBooks Integration Architecture

#### Core Components
```
QuickBooks Export System
├── QBExportManager/
│   ├── TransactionFormatter/   # Format transactions for QB
│   ├── AccountMapper/         # Map categories to QB accounts
│   ├── VendorManager/         # Handle QB vendor mapping
│   └── ValidationEngine/      # QB-specific validation
├── FileGenerator/
│   ├── IIFGenerator/         # Generate .IIF file format
│   ├── QBOGenerator/         # Generate .QBO format
│   └── QBXMLGenerator/       # Generate QB XML format
└── SyncEngine/
    ├── MappingManager/       # Handle field mappings
    ├── ConflictResolver/     # Handle duplicates/conflicts
    └── AuditLogger/         # Track export operations
```

#### Data Models
```python
class QBExportConfig:
    def __init__(self):
        self.account_map = {}      # Map categories to QB accounts
        self.vendor_map = {}       # Map payees to QB vendors
        self.class_map = {}        # Map business contexts to QB classes
        self.export_format = "IIF" # IIF, QBO, or QBXML

class QBTransaction:
    def __init__(self):
        self.trns_type = ""       # TRNS types (CHECK, BILL, etc.)
        self.date = None          # Transaction date
        self.account = ""         # QB account name
        self.amount = 0.0         # Transaction amount
        self.payee = ""          # QB vendor name
        self.memo = ""           # Transaction description
        self.class_name = ""     # QB class for tracking
        self.tax_line = ""       # Tax line mapping

class QBExportResult:
    def __init__(self):
        self.success = False
        self.file_path = ""
        self.format = ""
        self.summary = {}
        self.errors = []
```

#### Integration Points
1. Transaction Export
   ```python
   class QBExporter:
       def __init__(self, config: QBExportConfig):
           self.config = config
           self.formatter = TransactionFormatter()
           self.validator = ValidationEngine()
           
       def export_transactions(self, transactions: List[Transaction]) -> QBExportResult:
           # Format transactions for QB
           qb_transactions = self.formatter.format_for_qb(transactions)
           
           # Validate QB-specific requirements
           validation = self.validator.validate_for_qb(qb_transactions)
           
           # Generate appropriate file format
           if self.config.export_format == "IIF":
               return self.generate_iif(qb_transactions)
           elif self.config.export_format == "QBO":
               return self.generate_qbo(qb_transactions)
           else:
               return self.generate_qbxml(qb_transactions)
   ```

2. Account Mapping
   ```python
   class AccountMapper:
       def __init__(self, config: QBExportConfig):
           self.config = config
           self.default_accounts = load_default_accounts()
           
       def map_category_to_account(self, category: str, tax_category: str) -> str:
           # Try exact match
           if category in self.config.account_map:
               return self.config.account_map[category]
           
           # Try tax category based mapping
           if tax_category in self.default_accounts:
               return self.default_accounts[tax_category]
           
           # Return default catch-all account
           return "Ask My Accountant"
   ```

3. File Generation
   ```python
   class IIFGenerator:
       def generate(self, transactions: List[QBTransaction]) -> str:
           output = self.generate_header()
           
           for trans in transactions:
               # Generate TRNS line
               output += self.format_trns_line(trans)
               
               # Generate SPL line
               output += self.format_spl_line(trans)
               
               # Generate ENDTRNS
               output += "ENDTRNS\n"
           
           return output
   ```

### Key Technical Considerations

1. Data Mapping
   - Category to account mapping
   - Payee to vendor mapping
   - Business context to class mapping
   - Tax line mapping

2. File Format Support
   - IIF (Intuit Interchange Format)
   - QBO (Web Connect)
   - QBXML (Integration API)

3. Validation Rules
   - Account name validation
   - Transaction type rules
   - Amount formatting
   - Required fields

4. Error Handling
   - Invalid mappings
   - Missing required data
   - Format-specific constraints
   - Duplicate detection

### Implementation Strategy

1. Phase 1: Basic Export
   - IIF file generation
   - Essential field mapping
   - Basic validation
   - Simple error handling

2. Phase 2: Enhanced Mapping
   - Account mapping UI
   - Vendor synchronization
   - Class mapping
   - Tax line mapping

3. Phase 3: Advanced Features
   - Multiple format support
   - Conflict resolution
   - Batch export
   - Error recovery

4. Phase 4: Integration Features
   - Direct QB connection
   - Real-time sync
   - Change tracking
   - Audit logging 

## Agent Architecture

### Agent Types
1. Payee Lookup Agent
   - Purpose: Identify and normalize payee names
   - Tools: Search tool (currently using brave_search, discrepancy with searxng)
   - Response Schema: Structured payee information
   - Logging: Detailed operation logging

2. Classification Agent
   - Purpose: Categorize transactions
   - Tools: None currently
   - Response Schema: Classification details
   - Logging: Detailed operation logging

### Tool Integration
- Tools are loaded from database
- Each tool has a specific module path
- Tools can be enabled/disabled per agent
- Current discrepancy: brave_search vs searxng search tools

### Logging System
- Detailed operation logging
- Progress indicators for long-running operations
- Transaction processing monitoring
- Terminal log integration

### Field Management
1. **Payee Fields**
   - normalized_description
   - payee
   - confidence
   - reasoning
   - transaction_type
   - questions
   - payee_extraction_method

2. **Classification Fields**
   - classification_type
   - worksheet
   - category
   - confidence
   - reasoning
   - questions
   - classification_method

### Development Rules
1. NEVER modify one agent's fields without checking impact on others
2. ALWAYS test both agents after any changes
3. Keep prompts and field mappings in separate, well-documented locations
4. Use clear interfaces between agents
5. Maintain strict field separation
6. Document all field dependencies 

## Critical Safety Patterns

### Code Change Methodology
1. **Backup Before Changes**
   - Always create full backups (code + database) before making changes
   - Use `backup.sh` to create timestamped backups
   - Keep `rollback.sh` ready for quick restoration

2. **Incremental Development**
   - NEVER remove working code when adding new features
   - Keep old features active until new ones are proven stable
   - Add new features alongside existing ones
   - Test new features in isolation first

3. **Feature Addition Rules**
   - When adding new actions/features:
     - DO NOT remove or modify existing actions
     - Keep all working functionality intact
     - Add new features as additional options
     - Test new features without affecting existing ones

4. **Rollback Strategy**
   - Always have a working rollback plan
   - Use `rollback.sh` for quick restoration
   - Test rollback process regularly
   - Document rollback steps clearly

5. **Testing Protocol**
   - Test new features in isolation
   - Verify existing features still work
   - Create test endpoints for new functionality
   - Document test procedures

### Database Safety
1. **Never Assume Empty**
   - Always verify database state
   - Check for existing data before operations
   - Never delete or modify without backup

2. **Migration Safety**
   - Test migrations on test database first
   - Keep rollback migrations ready
   - Document migration dependencies

3. **Data Integrity**
   - Verify data before and after changes
   - Use transactions for data modifications
   - Keep audit trails of changes

### Feature Development Process
1. **Add, Don't Replace**
   - New features should be additive
   - Keep existing functionality intact
   - Document feature coexistence

2. **Testing Before Removal**
   - Only remove old features after:
     - New features are proven stable
     - Users have migrated to new features
     - No dependencies remain

3. **Documentation**
   - Document all feature additions
   - Keep track of feature dependencies
   - Maintain clear upgrade paths 

# System Architecture Patterns

## Current Architecture Issues

### 1. Project Structure
The current project structure has multiple overlapping Django projects:
```
/test_django/
  pdf_extractor_web/
    settings.py (port 5433)
    pdf_extractor_web/
      settings.py (port 5432)
```

This creates several problems:
- Python import path confusion
- Settings module resolution issues
- Database connection inconsistencies
- Session management conflicts

### 2. Database Architecture
Current setup:
- Multiple PostgreSQL instances (ports 5432, 5433)
- No clear database routing
- Inconsistent connection settings
- Potential transaction isolation issues

### 3. Task Processing Flow
Current implementation:
1. Admin interface creates task in database A
2. Processing command looks for task in database B
3. Task not found error occurs
4. Session data corruption observed

### 4. Session Management
Issues identified:
- Session data corruption across instances
- Inconsistent session handling
- Potential race conditions

## Required Architecture Changes

### 1. Project Structure
Proposed structure:
```
/pdf_extractor_web/
  settings/
    base.py
    development.py
    test.py
    production.py
  apps/
    profiles/
    simple_classifications/
    experimental_admin/
  manage.py
  wsgi.py
```

### 2. Database Architecture
Required changes:
- Single PostgreSQL instance
- Clear database routing
- Consistent connection settings
- Proper transaction management

### 3. Task Processing
Proposed flow:
1. Task creation in admin
2. Task queuing in Celery
3. Worker processing with proper isolation
4. Status updates with transaction safety

### 4. Session Management
Required improvements:
- Centralized session handling
- Proper session storage
- Transaction-safe session updates

## Technical Decisions

### 1. Database
- Use PostgreSQL for all environments
- Implement proper database routing
- Use connection pooling
- Enable transaction isolation

### 2. Task Processing
- Use Celery for task queue
- Implement proper worker isolation
- Add comprehensive logging
- Enable task retries

### 3. Session Management
- Use database-backed sessions
- Implement proper session cleanup
- Add session verification
- Enable session encryption

### 4. Error Handling
- Implement comprehensive logging
- Add error tracking
- Enable automatic retries
- Provide detailed error messages 