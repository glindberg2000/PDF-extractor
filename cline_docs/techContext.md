# Technical Context

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