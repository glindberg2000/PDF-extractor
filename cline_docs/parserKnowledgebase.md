# Parser Knowledgebase

## Purpose
This file documents the detailed logic, normalization flows, and edge-case handling for all statement parsers in the system. It is the persistent reference for how each parser works, especially regarding date and year inference, normalization, and known gotchas.

---

## Date & Year Inference: Summary Table

| Parser                        | Input Date Format      | Year Inference? | Year Source/Logic                        |
|-------------------------------|-----------------------|-----------------|------------------------------------------|
| CapitalOne CSV (modular)      | YYYY-MM-DD            | No              | Always present in data                   |
| Wells Fargo Checking CSV      | MM/DD/YYYY            | No              | Always present in data                   |
| Wells Fargo Bank CSV (legacy) | MM/DD/YYYY            | No              | Always present in data                   |
| BofA Visa (PDF)               | MM/DD                 | Yes             | Inferred from statement date (filename/header) |
| Chase Checking (PDF)          | MM/DD                 | Yes             | Inferred from statement date (filename/header) |
| Wells Fargo Visa (PDF)        | MM/DD                 | Yes             | Inferred from statement date (filename/header) |
| Wells Fargo Mastercard (PDF)  | MM/DD                 | Yes             | Inferred from statement date (filename/header) |
| First Republic Bank (PDF)     | MM/DD                 | Yes             | Inferred from statement date (filename/header) |

---

## Normalization & Year Inference Logic

### 1. CSV Parsers (CapitalOne, Wells Fargo Checking, Wells Fargo Bank CSV)
- **Date is always present in full (YYYY-MM-DD or MM/DD/YYYY).**
- No year inference is needed; the parser simply parses the date string and normalizes it to ISO format.
- Example (CapitalOne):
  ```python
  df[norm_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
  ```
- Example (Wells Fargo Checking):
  ```python
  return datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
  ```

### 2. PDF Parsers (BofA Visa, Chase Checking, Wells Fargo Visa, etc.)
- **Date in transaction lines is often only MM/DD.**
- The parser must infer the year from the statement date (usually found in the filename or statement header).
- **Year Inference Logic:**
  - If the statement is for January and the transaction is in December, the year is set to the previous year (handles year rollovers).
  - Otherwise, the year is set to the statement year.
  - Example:
    ```python
    if statement_month == 1 and transaction_month == 12:
        year_to_append = statement_year - 1
    else:
        year_to_append = statement_year
    new_date = f"{row[date_col]}/{year_to_append}"
    ```
- The normalized date is then parsed as MM/DD/YYYY and converted to ISO format.

### 3. Normalizer (normalize_api.py)
- The normalizer expects a `statement_year` field in the row if only MM/DD is present.
- If present, it constructs the date as:
  ```python
  if "statement_year" in row and row["statement_year"]:
      year = int(row["statement_year"])
      m, d = [int(x) for x in str(date_str).split("/")]
      return pd.Timestamp(year=year, month=m, day=d)
  ```
- If not present, and only MM/DD is available, normalization may fail (resulting in NaT).

---

## Edge Cases & Gotchas
- **Year Rollover:** If the statement is for January and a transaction is in December, the year must be set to the previous year to avoid future-dated transactions.
- **Missing Year:** If a parser outputs only MM/DD and does not provide a `statement_year`, normalization will fail.
- **CSV Parsers:** No risk of missing year, as all dates are full.
- **PDF Parsers:** Always ensure the parser extracts the statement year and applies it to all MM/DD dates.

---

## Example: BofA Visa Year Inference
```python
def append_year(row):
    statement_date = pd.to_datetime(row["Statement Date"])
    statement_year = statement_date.year
    statement_month = statement_date.month
    for date_col in ["Transaction Date", "Posting Date"]:
        transaction_month = int(row[date_col].split("/")[0])
        if statement_month == 1 and transaction_month == 12:
            year_to_append = statement_year - 1
        else:
            year_to_append = statement_year
        new_date = f"{row[date_col]}/{year_to_append}"
        row[date_col] = new_date
    return row
```

---

## Best Practices for Future Parsers
- If only MM/DD is present, always add a `statement_year` field to each row.
- If the date is already YYYY-MM-DD or MM/DD/YYYY, no inference is needed.
- Always normalize output dates to ISO format (YYYY-MM-DD).
- Document any special logic or edge cases in this file for future reference.

---

## To Do
- Update this file whenever a new parser is added or normalization logic changes.
- Add example input/output for each parser as needed. 