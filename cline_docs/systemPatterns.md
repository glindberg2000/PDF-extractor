# System Patterns

## Architecture Overview

### Frontend Architecture
1. **Component Structure**
   - Dashboard: Overview and metrics
   - Clients: Client management
   - Files: Document handling
   - Transactions: Transaction management
   - Shared components (modals, tables, forms)

2. **State Management**
   - React hooks for local state
   - Context for global state
   - WebSocket for real-time updates

3. **UI Patterns**
   - Modal-based forms for actions
   - Table-based data display
   - Drag-and-drop file upload
   - Status indicators and progress bars

### Backend Architecture
1. **API Structure**
   - RESTful endpoints for CRUD operations
   - WebSocket for real-time updates
   - Background task processing

2. **File System Organization**
   ```
   client_files/
   ├── {client_id}_{client_name}/
   │   ├── uploads/
   │   ├── processed/
   │   └── archived/
   ```

3. **Database Schema**
   ```sql
   -- Statement Types Table
   CREATE TABLE statement_types (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       name TEXT NOT NULL UNIQUE,
       parser_script TEXT NOT NULL,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   -- Statements Table
   CREATE TABLE statements (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       client_id INTEGER NOT NULL,
       statement_type_id INTEGER NOT NULL,
       file_path TEXT NOT NULL,
       status TEXT NOT NULL DEFAULT 'pending',
       upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       process_timestamp TIMESTAMP,
       error_message TEXT,
       FOREIGN KEY (client_id) REFERENCES clients(id),
       FOREIGN KEY (statement_type_id) REFERENCES statement_types(id)
   );

   -- Transactions Table (existing)
   CREATE TABLE transactions (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       statement_id INTEGER NOT NULL,
       date DATE NOT NULL,
       description TEXT NOT NULL,
       amount DECIMAL(10,2) NOT NULL,
       category TEXT,
       FOREIGN KEY (statement_id) REFERENCES statements(id)
   );
   ```

## Key Technical Decisions

### 1. File Processing
- Asynchronous processing using background tasks
- Status tracking via WebSocket
- File system organization by client
- Support for multiple file formats

### 2. Data Management
- SQLite for data storage
- File system for document storage
- JSON for configuration and metadata
- CSV for transaction exports

### 3. Security
- File type validation
- Client isolation
- Secure file storage
- Access control

### 4. Performance
- Batch processing
- Background tasks
- Efficient file storage
- Optimized database queries

## Design Patterns

### 1. Repository Pattern
- Abstract data access
- Consistent CRUD operations
- Transaction management

### 2. Factory Pattern
- Parser creation
- File handler creation
- Document processor creation

### 3. Observer Pattern
- Status updates
- Processing notifications
- Real-time updates

### 4. Strategy Pattern
- Parser selection
- File handling
- Processing methods

## Error Handling

### 1. File Processing
- Validation errors
- Processing failures
- Format mismatches

### 2. Data Management
- Database constraints
- File system errors
- State inconsistencies

### 3. User Interface
- Form validation
- Network errors
- Processing status

## Testing Strategy

### 1. Unit Tests
- Component testing
- Service testing
- Utility testing

### 2. Integration Tests
- API testing
- File processing
- Database operations

### 3. End-to-End Tests
- User workflows
- File uploads
- Processing pipeline

## Code Organization

1. Main Modules
   ```
   dataextractai_vision/
   ├── __init__.py
   ├── cli.py           # Command-line interface
   └── extractor.py     # Core extraction logic
   ```

2. Support Files
   ```
   ├── requirements.txt  # Dependencies
   ├── setup.py         # Package configuration
   └── README.md        # Documentation
   ```

3. Data Organization
   ```
   clients/
   ├── {client_name}/
   │   ├── input/       # PDF statements
   │   └── output/      # Extracted data
   ```

## Best Practices

1. Code Quality
   - Type hints for better maintainability
   - Comprehensive docstrings
   - Consistent error handling
   - Detailed logging

2. Data Management
   - Atomic file operations
   - Transaction tracking
   - Source file preservation
   - Processing history

3. Error Recovery
   - Graceful failure handling
   - Detailed error logging
   - State preservation
   - Retry mechanisms

4. Performance
   - Efficient image processing
   - Batch operations
   - Resource cleanup
   - Memory management

## Directory Structure Pattern
```
├── data/
│   ├── input/          # PDF document directories
│   └── output/         # Processed data output
├── dataextractai/
│   ├── classifiers/    # AI classification logic
│   ├── parsers/        # PDF parsing implementations
│   └── utils/          # Shared utilities
├── scripts/            # Command-line tools
└── tests/              # Test suite
```

## Configuration Patterns
- Environment-based configuration
- Separate configuration for:
  - Parser input/output paths
  - AI assistant configurations
  - Classification categories
  - System prompts 