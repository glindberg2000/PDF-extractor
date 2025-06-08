# PRD: CapitalOne Visa Print Statement Parser

## Overview
Develop a new parser module to extract transaction data from CapitalOne Visa statements that were originally HTML lists printed to PDF. These statements differ from standard PDF bank statements (which are often scanned or image-based) in that they are text-based, with a regular, structured layout. The parser should leverage this structure for robust extraction and normalization.

## Goals
- Accurately extract all transaction data from CapitalOne Visa print-to-PDF statements.
- Output a CSV with standardized, normalized columns compatible with the existing DataExtractAI pipeline.
- Integrate seamlessly with the current parser/normalizer framework (including transformation maps, client config, and output conventions).

## Input
- PDF files generated from HTML lists (not scanned images).
- Files will be placed in the appropriate input directory, e.g.:
  - `data/clients/<client_name>/input/capitalone_visa_print/`

## Output
- A CSV file in the standard output directory, e.g.:
  - `data/clients/<client_name>/output/capitalone_visa_print_output.csv`
- The output must have the following **standardized columns** (all lowercase, underscores, no special characters):
  - `transaction_date` (YYYY-MM-DD, string)
  - `description` (transaction description, string)
  - `amount` (float, positive for credits, negative for debits)
  - `source` (string, always set to 'capitalone_visa_print')
  - `file_path` (relative path to the source PDF file)
  - (Optional, if available): `statement_end_date`, `account_number`, `normalized_date`, `normalized_amount`
- The output must be compatible with the transaction normalizer and transformation map system.

## Required Fields to Extract
- **Transaction Date**: The date of the transaction (must be parsed and normalized to YYYY-MM-DD).
- **Description**: Merchant or transaction description.
- **Amount**: Transaction amount (parse as float, handle debits/credits correctly).
- **(Optional) Balance**: If present, extract but not required for normalization.
- **Account Number**: If present, extract for reference.
- **Statement End Date**: If present, extract for use in normalization (e.g., for interest credits).

## Extraction/Parsing Notes
- The parser should use a text extraction library (e.g., PyPDF2, pdfplumber) to read the PDF.
- Identify the transaction table/list by searching for headers (e.g., 'Date', 'Description', 'Amount').
- Each transaction row should be parsed into its components.
- Handle multi-line descriptions if present.
- Ignore summary, totals, or non-transaction rows.
- Standardize all column names using the existing `standardize_column_names` utility.

## Integration Requirements
- The parser must be implemented as a new module in `dataextractai/parsers/` (e.g., `capitalone_visa_print_parser.py`).
- Register the parser in any relevant parser registries or CLI interfaces if required.
- Ensure the output CSV is written to the correct output path and is picked up by the normalizer.
- Add or update the transformation map for 'capitalone_visa_print' in the config so the normalizer can map fields correctly.
- Add tests using representative sample PDFs (if available).

## Edge Cases & Validation
- If a transaction row is missing a required field, log a warning and skip the row.
- Validate that all output rows have valid `transaction_date`, `description`, and `amount`.
- Ensure the parser works with both single and multi-page statements.
- If the PDF structure changes, fail gracefully and log a clear error.

## Example Output (CSV)
| transaction_date | description         | amount  | source                | file_path                  |
|------------------|--------------------|---------|-----------------------|----------------------------|
| 2024-05-01       | AMAZON MARKETPLACE | -25.99  | capitalone_visa_print | input/capitalone_visa.pdf  |
| 2024-05-02       | STARBUCKS          | -4.50   | capitalone_visa_print | input/capitalone_visa.pdf  |
| 2024-05-03       | PAYMENT RECEIVED   | 100.00  | capitalone_visa_print | input/capitalone_visa.pdf  |

## Next Steps
1. Implement the parser as described above.
2. Add/verify transformation map for 'capitalone_visa_print'.
3. Test with sample files and validate output against requirements.
4. Update documentation and integration points as needed. 