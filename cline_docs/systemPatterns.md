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

## Transaction Processing

### Three-Pass Classification
1. Pass 1: Payee Identification
   - AI-based payee extraction
   - Brave Search enrichment
   - Confidence scoring

2. Pass 2: Category Assignment
   - Requires valid payee from Pass 1
   - Uses business context
   - Suggests new categories

3. Pass 3: Classification
   - Requires valid category from Pass 2
   - Business vs Personal determination
   - Tax implications

### Status Tracking
1. Status Values
   - `pending`: Not yet processed
   - `processing`: Currently being processed
   - `completed`: Successfully processed
   - `error`: Failed with error
   - `skipped`: Skipped due to missing dependency
   - `force_required`: Needs force processing

2. Status Management
   - Each pass tracked independently
   - Error messages preserved
   - Processing timestamps recorded
   - Force processing available

3. Dependencies
   - Pass 2 requires Pass 1 completion
   - Pass 3 requires Pass 2 completion
   - Dependencies can be bypassed with force

### Caching System
1. Cache Storage
   - Per-client caching
   - Pass-specific results
   - JSON result storage
   - Cache key generation

2. Cache Management
   - Cache hit logging
   - Cache invalidation
   - Cache cleanup
   - Cache size monitoring

### Error Handling
1. Transaction Level
   - Individual transaction isolation
   - Error status tracking
   - Error message preservation
   - Recovery options

2. System Level
   - Database connection handling
   - API rate limiting
   - Resource cleanup
   - State consistency

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