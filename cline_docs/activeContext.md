# Active Context

## Current Focus
- Transaction processing system with three-pass approach
- Implementation of caching system for transaction analysis
- Error handling and progress tracking
- CapitalOne Visa print-to-PDF parser is in progress but cannot extract the amount field due to PDF encoding issues. Both PyPDF2 and pdfplumber fail to extract numeric values for the amount column. OCR or alternative formats may be required.
- New focus: Implementing a robust CapitalOne CSV transaction parser to bypass PDF extraction issues.
- **NEW:** Universal parser detection function is now available. All modularized parsers (CSV and PDF) are auto-registered and available for strict, robust detection. The detection utility is available both as a CLI and as a function for module users.
- **NEW:** ChaseCheckingParser now exposes a robust `extract_metadata` method, callable on demand, returning all key metadata fields (bank_name, account_type, parser_name, file_type, account_number, statement_date, account_holder_name, address, statement_period_start, statement_period_end) for any Chase Checking PDF. This is tested and ready for LedgerDev and other consumers.

## Current State
- Successfully implemented multi-client parser system
- Fixed client name handling with spaces
- Standardized directory structure for clients
- Implemented basic client configuration system
- **NEW:** Detection logic is strict and robust—no guessing or partial matches. Only modularized and registered parsers are used for detection. This ensures reliability and extensibility as new parsers are added.

## Recent Changes
1. Implemented comprehensive caching system:
   - Persistent cache storage in JSON format
   - Cache keys based on normalized transaction descriptions
   - Separate caching for each processing pass (payee, category, classification)
   - Clear logging of cache hits and misses
   - Cache persistence between program runs

2. Enhanced error handling and progress tracking:
   - Detailed error messages for each processing pass
   - Progress saving after each pass
   - Resume capability from any pass
   - Clear logging of processing status

3. Improved transaction processing:
   - Single transaction processing for better accuracy
   - Proper validation of classification values
   - Consistent output file organization
   - Better error isolation

4. Marked the PDF parser task as in-progress with critical unresolved issues (amount extraction not possible with current tools).
5. Created a new task in Task Master to implement a CapitalOne CSV parser, with detailed subtasks for scaffolding, parsing, detection, testing, documentation, and validation.

6. Modular parser system is fully operational and production-ready.
7. All parsers (e.g., First Republic, Wells Fargo Visa) are class-based, registry-driven, and tested with real data.
8. Universal file-to-parser detection function is implemented. All modularized parsers are auto-registered and available for strict, robust detection.
9. Robust normalization: Every output DataFrame now forcibly includes `source` (parser canonical name), `file_path` (relative input path), and `file_name` (base file name) for every row.
10. Debug prints confirm these fields are present in all code paths, including Django and downstream imports.
11. Team notified and confirmed the fix works in their environment.
12. Testing has confirmed detection and normalization for all migrated parsers.

## CapitalOne CSV Parser Deep Dive
- **Sample CSV columns:** Transaction Date, Posted Date, Card No., Description, Category, Debit, Credit
- **Key requirements:**
  - Combine Debit and Credit columns into a single 'amount' column (debits positive, credits negative)
  - Normalize date fields to standard format (YYYY-MM-DD)
  - Map Description, Category, Card No. to normalized fields
  - Output must match the standardized schema used by other parsers (transaction_date, description, amount, source_file, source, transaction_type, etc.)
  - Parser must be robust to minor header variations and missing/malformed data
- **Integration:**
  - Place parser in dataextractai/parsers/capitalone_csv_parser.py
  - Inherit from BaseParser, register in parser registry
  - Implement can_parse to detect CapitalOne CSVs by header
  - Ensure compatibility with both modular and CLI workflows
- **Testing:**
  - Unit tests for normal and edge cases (missing columns, malformed rows)
  - Integration tests for CLI/standalone use
  - Manual validation with provided sample and real data

## Task Master Subtasks for CSV Parser
1. Scaffold parser module and register it
2. Implement parse_file logic for column mapping and normalization
3. Implement can_parse logic for CapitalOne CSV detection
4. Write unit tests for parser
5. Write integration tests for CLI/standalone use
6. Document parser usage and edge cases
7. Validate output with provided sample and real data

## Next Steps
1. Test the caching system with real transaction data
2. Monitor cache effectiveness and hit rates
3. Consider adding cache statistics reporting
4. Evaluate performance improvements from caching
5. Consider adding cache cleanup/management features

6. Begin with scaffolding the parser and registering it
7. Implement core parsing and normalization logic
8. Add robust detection for CapitalOne CSVs
9. Write and run tests
10. Document usage and edge cases
11. Validate with sample and real data

### 1. Port Legacy Features
1. AI Processing:
   - Batch processing system
   - Multiple AI assistants support
   - Progress tracking per client
   - State management

2. Data Consolidation:
   - Batch merging
   - Data normalization
   - Year filtering
   - Transaction deduplication

3. Google Sheets Integration:
   - Client-specific sheet configuration
   - Category/Classification dropdowns
   - Sheet formatting
   - Data validation

### 2. CLI Consolidation
1. Phase out grok.py:
   - Document all features
   - Create migration path
   - Port unique functionality

2. Enhance main.py:
   - Add missing features
   - Improve error handling
   - Add progress tracking
   - Better logging

### 3. Testing & Documentation
1. Add comprehensive tests
2. Update documentation
3. Create migration guides
4. Add example configurations

### 4. Fix First Republic Bank parser issues
1. Parser is running but finding 0 transactions
2. Need to investigate date parsing in `first_republic_bank_parser.py`
3. Warning about date format "May 01, 2024 - May 24, 2024" not being parsed correctly
4. Verify PDF structure hasn't changed

### 5. Future Improvements
1. Add more comprehensive error handling in parsers
2. Improve logging for better debugging
3. Add unit tests for date parsing edge cases

## Current CLI Structure
1. Legacy System (scripts/grok.py):
   - Two-pass AI classification approach
   - Uses OpenAI assistants (AmeliaAI, DaveAI)
   - Batch processing with review workflow
   - Google Sheets integration

2. New Multi-Client System (dataextractai/cli/main.py):
   - Client management
   - Document processing
   - Basic categorization
   - Google Sheets setup/upload

## Current CLI Commands
```bash
# List all categories
python -m dataextractai.cli.main categories list <client_name>

# Add a new category
python -m dataextractai.cli.main categories add <client_name>

# Edit an existing category
python -m dataextractai.cli.main categories edit <client_name>

# Delete a category (by number or name)
python -m dataextractai.cli.main categories delete <client_name>

# Generate AI-suggested categories
python -m dataextractai.cli.main categories generate <client_name>
```

## Category Management Features
1. **List Categories**
   - Shows all categories with numbers
   - Displays system and custom categories
   - Shows descriptions and tax implications

2. **Add Categories**
   - Natural language input
   - AI-assisted formatting
   - System category matching
   - Tax implication suggestions

3. **Edit Categories**
   - Natural language updates
   - Side-by-side change preview
   - System category matching
   - Confidence level tracking

4. **Delete Categories**
   - Support for number or name input
   - Confirmation prompts
   - Category details preview

5. **Generate Categories**
   - Uses full business context
   - Industry-specific suggestions
   - Tax implication guidance
   - System category matching

## Current Work
- Successfully implemented client-specific directory structure
- Fixed path handling in parser modules
- Added proper configuration management
- Implemented debug logging for path verification

## Current Status
1. Command-Line Version (Core)
   - Functional parser system
   - Working Google Sheets integration
   - Basic AI categorization
   - Recently added Wells Fargo CSV parser

2. Web Version (In Progress)
   - React frontend started
   - FastAPI backend framework
   - Database schema defined
   - File upload system working

## Known Issues
1. Parser System
   - Empty directory handling needs testing
   - Some parsers may need updates for new formats

2. AI Categorization
   - Needs testing with new parsers
   - May need optimization for large datasets

3. Google Sheets
   - Credentials setup needs documentation
   - Multi-client sheet management needed

## Current Challenges
1. Ensuring efficient file upload handling
2. Managing batch upload states
3. Implementing real-time status updates
4. Handling large files effectively

## Immediate Tasks
1. Design file upload component
2. Implement drag-and-drop interface
3. Add file validation
4. Create status tracking UI

## Legacy System (scripts/grok.py):
- Two-pass AI classification approach
- Uses OpenAI assistants (AmeliaAI, DaveAI)
- Batch processing with review workflow
- Google Sheets integration

## Current System:
- Modular parser architecture
- Transaction normalization
- Client profile management
- CLI and menu interfaces
- AI classifier system (in progress)

## Current Problem

- **Issue:** The normalized DataFrame for Chase Checking statements is empty (all rows dropped) because the transformation map expects case-sensitive column names, but the parser outputs standardized (lowercase, underscore) column names.
- **Test Script:** A test script was created to reproduce the issue locally using the `normalize_parsed_data` function with the `chase_checking` parser and the provided file path.
- **Conversation with Ledgerflow:** Ledgerflow confirmed the parser name (`chase_checking`) and the input file path (`../clients/testfiles/20240612-statements-7429-.pdf`).

## Test Script

```python
import pandas as pd
from dataextractai.utils.normalize_api import normalize_parsed_data

# Test parameters
file_path = "../clients/testfiles/20240612-statements-7429-.pdf"
parser_name = "chase_checking"
client_name = "sample2"

# Run the normalizer
transactions = normalize_parsed_data(
    file_path=file_path,
    parser_name=parser_name,
    client_name=client_name,
    config=None,
)

# Print the normalized DataFrame
print(transactions)
```

## Relevant Code Examples

### Transformation Map for `chase_checking`

```python
"chase_checking": {
    "transaction_date": "Date of Transaction",
    "description": "Merchant Name or Transaction Description",
    "amount": "Amount",
    "file_path": "File Path",
    "source": lambda x: "chase_checking",
    "transaction_type": lambda x: "Debit/Check",
    "account_number": "Account Number",
},
```

### Parser Output Columns

The `ChaseCheckingParser` outputs columns like:
- `"Date of Transaction"`
- `"Merchant Name or Transaction Description"`
- `"Amount"`
- `"Balance"`
- `"Statement Date"`
- `"Statement Year"`
- `"Statement Month"`
- `"Account Number"`
- `"File Path"`

## Launch Checklist for CSV Parser Development
- All context, mapping, and requirements are documented here
- Task Master is up to date with detailed tasks and subtasks
- Sample CSV is available in data/clients/chase_test/input/capitalone_csv/2024_Capital_one_transaction_download.csv
- Ready to begin development of the CapitalOne CSV parser

## Known Issues
- PDF parser for CapitalOne Visa print statements cannot extract amounts; CSV parser is the recommended path forward

# Active Context: Chase Checking Statement Date Extraction Debugging

## Problem
- The Chase Checking parser is failing to extract the statement date from the content of certain PDFs (e.g., `test-statement-4894.pdf`).
- The date is present in the text (e.g., 'September 10, 2024 throughOctober 07, 2024') but not being parsed by any of the current methods.

## Attempts So Far
- Multiple regexes for both 'MM/DD/YYYY' and 'Month DD, YYYY' formats, including robust and aggressive variants.
- Aggressive normalization: removing all whitespace, using non-greedy wildcards, and unicode normalization.
- Fallback to pdfplumber for alternate text extraction.
- Brute-force: searching for 'through' in split lines and parsing the rest of the line.
- None of these approaches have successfully extracted the date from the problematic file.

## Current Plan
- Try a direct substring search: find 'through' in the entire first page text (not split by lines), grab the next 30–40 characters, and attempt to parse a date from that substring using dateutil.parser.
- Print debug output for the substring and parsing attempt.

## Next Step
- Implement and test this direct substring search approach.

---
This is the current active context for the next session.

---
## Active Context Update: Migration to Canonical Pydantic Parser Output Contract (2025-06)

### Current State
- All modularized parsers are being migrated to output a canonical, Pydantic-validated contract (see productContext.md and .taskmaster/docs/prd_parser_contract_migration.txt).
- The PRD for this migration is written and parsed into Task Master; tasks have been generated and appended to the project plan.
- Canonical Pydantic models are defined in dataextractai/parsers_core/models.py and documented in systemPatterns.md.
- Internal and external stakeholders have agreed on the contract and migration plan.

### Next Steps
- (Recommended) Create a new git branch for the migration: `feature/parser-output-contract-migration`
- Begin work on the highest-priority pending tasks in Task Master (see .taskmaster/tasks/tasks.json or use Task Master tools to list next tasks)
- Refactor each modularized parser to output ParserOutput, removing context fields from per-transaction output and moving all metadata to StatementMetadata.
- Update ingestion and downstream systems to consume the new contract.
- Update and validate all documentation and memory bank files as migration progresses.
- Communicate progress and blockers in internal chat and update Task Master task statuses as work proceeds.

### Crucial Details to Preserve
- The canonical contract and rationale (see productContext.md, systemPatterns.md, and parsers_core/models.py)
- The full migration plan and deliverables (see PRD)
- The current state of all tasks and their dependencies (see .taskmaster/tasks/tasks.json)
- Any feedback or requirements from LedgerFlow_Dev and other stakeholders

## Canonical Parser Output Contract (2025-06)

- **Canonical Pydantic Models:**
    - TransactionRecord, StatementMetadata, ParserOutput (see systemPatterns.md for full code)
    - All parser outputs must validate against these models
- **Normalization Rules:**
    - Each parser uses a transformation map to map legacy/variant fields to canonical fields
    - Required: transaction_date, description, amount (ISO 8601, float, str)
    - All context/statement-level info in StatementMetadata
    - Use `extra` for parser/bank-specific fields
- **Schema Enforcement:**
    - All outputs must be validated before returning
    - A dedicated test/validation script is required to enforce this contract
- **PRIORITY:**
    - Migration to this contract is now the top priority for all parser and ingestion work
    - All future parser migrations depend on this foundation

## 2024-06-16: Amazon Invoice Downloader Integration
- Added [amazon-invoice-downloader](https://github.com/dcwangmit01/amazon-invoice-downloader) as a git submodule.
- Set up a Python 3.11 venv and installed Playwright and the downloader.
- Downloaded all 2024 Amazon detailed invoices as PDFs to `data/clients/Greg/AmazonInvoices/downloads/`.
- Next: Build a new parser specifically for these detailed invoice PDFs (different format from main Amazon parser).

--- 