# Product Context

## Purpose
The PDF Extractor is a specialized tool designed to automate the extraction and processing of financial data from various bank statements and financial documents. It serves as a bridge between raw financial documents and structured financial data, making it easier to analyze and manage financial records.

## Problems Solved
1. **Manual Data Entry Elimination**: Automates the extraction of transaction data from PDF and CSV files, reducing manual data entry errors and time consumption.
2. **Multi-Format Support**: Handles various file formats from different financial institutions, providing a unified interface for data processing.
3. **Client-Specific Processing**: Supports multiple clients with separate data directories, allowing for organized and isolated data processing.
4. **Standardized Output**: Converts diverse financial data formats into a standardized structure, facilitating easier analysis and reporting.
5. **Batch Processing**: Enables processing of multiple files simultaneously, improving efficiency for large datasets.

## How It Works
1. **Input Processing**:
   - Accepts PDF and CSV files from various financial institutions
   - Supports both default and client-specific directory structures
   - Validates input files and formats

2. **Data Extraction**:
   - Parses PDF files using PyPDF2
   - Processes CSV files using pandas
   - Extracts relevant transaction data based on institution-specific patterns

3. **Data Transformation**:
   - Converts extracted data into a standardized format
   - Applies institution-specific transformations
   - Handles date formats and numerical values consistently

4. **Output Generation**:
   - Creates CSV and Excel files with processed data
   - Generates consolidated reports
   - Maintains state tracking for batch processing

5. **Client Management**:
   - Supports multiple clients with isolated data directories
   - Allows client-specific configurations
   - Maintains separate input and output directories per client

## Key Features
- Multi-format support (PDF, CSV)
- Client-specific processing
- Automated data extraction
- Standardized data transformation
- Batch processing capabilities
- Comprehensive output generation
- Configurable processing options

## Core Functionality
1. Document Processing
   - PDF parsing for multiple institutions
   - CSV import support
   - Batch processing capabilities

2. AI Integration
   - OpenAI-powered categorization
   - Multiple AI assistants (Bookkeeper & CPA)
   - Context-aware processing

3. Data Export
   - CSV/Excel output
   - Google Sheets integration
   - Structured for accounting use

## Target Users
- Accountants/Bookkeepers
- Small Business Owners
- Financial Advisors
- Individual Users

## Success Criteria
1. Accurate extraction of transaction data
2. Correct categorization of expenses
3. Efficient batch processing
4. Reliable Google Sheets integration
5. Support for multiple clients

## Recent Enhancements (NEW)
- Universal file-to-parser detection function: All modularized parsers are auto-registered and available for strict, robust detection.
- Detection utility is available both as a CLI and as a function for module users.
- Strict detection logic ensures no guessing or misclassification, improving reliability and extensibility.
- **NEW:** Modular parsers (starting with ChaseCheckingParser) now expose a robust `extract_metadata` method, enabling reliable, on-demand metadata extraction for downstream consumers (e.g., LedgerDev, CLI, Django, etc.).

# Product Context: Robust Date Extraction for Chase Checking

- The product must reliably extract statement dates from Chase Checking PDFs, even when text extraction is non-standard or edge-case.
- Robust date extraction is critical for downstream normalization, reporting, and client trust.
- The current debugging session is focused on ensuring that all client files, including edge cases, are handled correctly.

## Migration to Canonical Pydantic Parser Output Contract (2025-06)

### Motivation
- Ensure all modularized parsers output transaction data in a strictly enforced, minimal, and extensible schema.
- Guarantee schema reliability for ingestion, 3rd parties, and downstream consumers.
- Enforce separation of concerns: transaction data only in main output, all context/statement-level metadata returned separately.
- Use Pydantic models for type safety, validation, and maintainability.

### Goals
- Refactor all modularized parsers to output only transaction data fields in a list of TransactionRecord objects.
- Move all statement-level/contextual info to a StatementMetadata object.
- Return a ParserOutput object from each parser, validated by Pydantic.
- Remove all context fields (e.g., statement_file, client, file_path) from per-transaction output.
- Use the `extra` field for parser/bank-specific or experimental fields.
- Update ingestion and downstream systems to consume the new contract.
- Document the migration and update all relevant developer and system documentation. 