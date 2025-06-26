# PRD: Fix `first_republic_bank_parser` Crashing on Null Dates

**1. Objective:**
Resolve the critical `pydantic.ValidationError` crash in the `first_republic_bank_parser.py` and improve its robustness to prevent future failures from similar data issues.

**2. Background:**
The First Republic Bank parser is a critical component of our data extraction pipeline. It is currently crashing when it encounters certain transaction lines in PDF statements, which prevents the processing of entire documents. The root cause is a failure to extract a `transaction_date` from a line, leading to a `None` value being passed to a data model that requires a valid date string.

**3. Problem Details:**
- **Error Type:** `pydantic_core._pydantic_core.ValidationError`
- **Field:** `transaction_date`
- **Error Message:** `Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]`
- **Location of Failure:** The error occurs in the `_extract_transactions_from_text` method within the `FirstRepublicBankParser` class in `dataextractai/parsers/first_republic_bank_parser.py`.

**4. Problematic Files:**
The parser is confirmed to fail on the following files. These should be used as the primary test cases for debugging and validation:
- `20240131-statements-4894- (2).pdf`
- `20240229-statements-4894- (1).pdf`

**5. Technical Requirements & Acceptance Criteria:**

1.  **Analyze Date Extraction Logic:**
    -   Thoroughly investigate the regular expressions and string processing logic within the `_extract_transactions_from_text` method responsible for identifying and extracting the date from a transaction line.

2.  **Improve Regex/Logic Robustness:**
    -   Modify the date extraction logic to correctly parse the date formats present in the failing PDF files.
    -   The logic must be flexible enough to handle potential variations in date formatting or multi-line transaction descriptions that might displace the date.

3.  **Implement a Pre-Validation Guardrail:**
    -   Before attempting to create a `TransactionRecord` object, a check **must** be implemented to verify that a valid, non-null date string has been successfully extracted.
    -   **If a date cannot be extracted** from a line that is otherwise identified as a transaction, the parser must **not** crash. Instead, it must:
        -   Log a detailed warning message that includes the content of the problematic line and the file it came from.
        -   Gracefully skip that specific record.
        -   Continue processing the rest of the document.

**6. Verification & Testing:**
- The fix will be considered successful when the `first_republic_bank_parser` can process both of the problematic PDF files (`20240131-statements-4894- (2).pdf` and `20240229-statements-4894- (1).pdf`) from start to finish without crashing.
- The parser must still successfully extract all valid transactions from these documents.
- The system logs must show warning messages for any records that were skipped due to a missing date, rather than showing a traceback for a `ValidationError`. 