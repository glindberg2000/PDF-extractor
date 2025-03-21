# System Patterns

## Architecture Overview
The system follows a modular architecture with clear separation of concerns:

1. **Configuration Management**
   - Centralized configuration in `config.py`
   - Client-specific configuration support
   - Dynamic path management
   - Configuration validation

2. **Parser System**
   - Modular parser design
   - Institution-specific parsers
   - Common interface for all parsers
   - Error handling and logging

3. **Data Processing Pipeline**
   - Input validation
   - Data extraction
   - Transformation
   - Output generation

4. **Directory Structure**
   ```
   PDF-extractor/
   ├── clients/
   │   └── <client_name>/
   │       ├── input/
   │       └── output/
   ├── data/
   │   ├── input/
   │   └── output/
   └── scripts/
   ```

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

1. **Factory Pattern**
   - Parser creation
   - Configuration management
   - Path generation

2. **Strategy Pattern**
   - Institution-specific parsing
   - Format-specific processing
   - Transformation strategies

3. **Observer Pattern**
   - Progress tracking
   - Logging system
   - State management

4. **Template Pattern**
   - Parser interface
   - Transformation pipeline
   - Output generation

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