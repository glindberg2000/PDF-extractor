# System Patterns

## Architecture Overview
The system follows a modular architecture with clear separation of concerns:

1. Core Components
   - VisionExtractor: Main class for PDF processing and transaction extraction
   - ProcessingHistory: Manages processing state and history
   - Transaction: Data model for financial transactions
   - ProcessingResult: Result type for extraction operations

2. Processing Pipeline
   ```
   PDF -> Image Conversion -> Vision API -> JSON Parsing -> Transaction Objects -> CSV Output
   ```

## Key Technical Decisions

1. Vision Model Selection
   - Using GPT-4.5-preview for vision capabilities
   - Optimized for document understanding
   - Handles various statement formats

2. Image Processing
   - PyMuPDF for PDF to image conversion
   - Automatic image resizing for API limits
   - Base64 encoding for API transmission

3. Data Storage
   - SQLite for processing history
   - CSV files for transaction data
   - File-based organization for scalability

4. Error Handling
   - Comprehensive exception handling
   - Detailed logging at all stages
   - Graceful failure recovery

## Design Patterns

1. Builder Pattern
   - Transaction object construction
   - ProcessingResult creation
   - Structured data assembly

2. Strategy Pattern
   - Flexible image processing
   - Configurable API parameters
   - Adaptable parsing logic

3. Repository Pattern
   - Processing history management
   - Transaction storage
   - File organization

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