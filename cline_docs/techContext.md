# Technical Context

## Technology Stack

1. Core Technologies
   - Python 3.11+
   - OpenAI API (GPT-4.5-preview)
   - PyMuPDF (PDF processing)
   - Pandas (Data handling)
   - SQLite (History tracking)

2. Key Libraries
   - openai: Vision API integration
   - fitz: PDF to image conversion
   - pillow: Image processing
   - pandas: Data manipulation
   - httpx: HTTP client
   - sqlite3: Database management

3. Development Tools
   - pip: Package management
   - pytest: Testing framework
   - black: Code formatting
   - mypy: Type checking
   - logging: Debug and error tracking

## Development Setup

1. Environment Setup
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. API Configuration
   ```bash
   # .env file
   OPENAI_API_KEY=your-api-key
   ```

3. Directory Structure
   ```
   clients/
   ├── {client_name}/
   │   ├── input/       # PDF statements
   │   └── output/      # Extracted data
   ```

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