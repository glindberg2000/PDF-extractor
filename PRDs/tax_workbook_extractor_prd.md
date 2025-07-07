# Product Requirements Document (PRD): Tax Organizer Workbook Extractor

## Product Title
**Tax Organizer Extractor Module** (Extension of `PDF-Extractor` Parsing App)

## Overview
This module will enable automated parsing of professional tax organizer PDFs (e.g. from UltraTax, Lacerte, Drake) to extract structured, machine-readable tax data. It will support both scanned and digitally generated PDFs and will integrate into an existing UI that already supports drag-and-drop parsing of bank statements.

The goal is to:
1. Identify and parse each worksheet/form (e.g., 1099-INT, 1099-DIV, Schedule D)
2. Extract labeled fields and values with types
3. Detect document inclusions (e.g. attached W2, 1099)
4. Output structured JSON for downstream use
5. Optionally generate filled summary reports

## Objectives
- Extend existing parsing architecture to support tax workbooks
- Parse entire organizer into a structured JSON schema
- Enable export to CSV, JSON, and potentially regenerated PDFs or summary tables
- Allow future automation (e.g. AI review, validation, integration with tax software)

---

## Features

### 1. File Ingest & Format Detection
- Detect whether uploaded PDF is text-based or scanned
- Run OCR (Tesseract) on scanned pages
- Extract per-page text content

### 2. Table of Contents (TOC) Parser
- Identify and extract TOC section mappings (e.g. "Interest Income" = 5A = Page 13)
- Map section labels and codes to page numbers
- Store in dictionary for downstream alignment

### 3. Section & Form Parser
- Identify worksheet headers using TOC mapping or keyword detection
- For each recognized form:
  - Extract line-item fields
  - Capture labels, values, inferred types (checkbox, number, text, date)
  - Identify TSJ column (Taxpayer, Spouse, Joint)
  - Mark section as complete/incomplete

### 4. Document Reference Extractor
- Identify references to attached W2, 1099, brokerage statements, etc.
- Extract payer, year, account numbers where possible
- Flag document as received or missing

### 5. JSON Output Schema
```json
{
  "organizer_sections": [
    {
      "name": "Interest Income",
      "page_number": 13,
      "fields": [
        {
          "label": "Name of Payer",
          "line_number": null,
          "value": "FIRST REPUBLIC BANK",
          "type": "text",
          "notes": "TSJ: T"
        },
        ...
      ],
      "complete": true
    },
    ...
  ],
  "documents": [
    {
      "type": "1099-INT",
      "received": true,
      "details": "FIRST REPUBLIC BANK"
    },
    ...
  ],
  "unclassified_fields": [
    { "text": "Note: List all items sold on Schedule D.", "page_number": 15 }
  ],
  "metadata": {
    "errors": [
      {
        "section": "Interest Income",
        "page": 13,
        "field": "Name of Payer",
        "reason": "OCR failed"
      }
      // ...
    ]
  }
}
```

### 6. Output/Export Options
- JSON (for database or pipeline ingestion)
- CSV or Airtable (for reviewer analysis)
- Markdown summary (for preview or support agents)
- Regenerated summary PDF (future)

### 7. Frontend Integration
- Extend current drag-and-drop UI used for bank statements
- Add template detection to distinguish "Tax Organizer"
- Auto-trigger relevant parser on drop
- Provide visual preview of extracted data
- Export buttons for CSV/JSON

---

## User Stories

### As a Tax Preparer
- I want to upload a scanned or digital tax workbook and get a structured summary of all forms filled
- I want to see which sections are incomplete or missing documents
- I want to export data to my CRM/spreadsheet

### As a Developer
- I want to reuse the parsing modules from bank statements
- I want to plug in form-specific extractors for each tax worksheet
- I want to match page content to TOC entries for accurate mapping

---

## Milestones

### Phase 1: Foundation
- [x] TOC Extractor and Page Mapping
- [x] Section Label Detection
- [x] Simple Payer/Amount Field Parser

### Phase 2: Structured Field Extraction
- [ ] Form-specific extractors (e.g. 5A, 5B, 6A, 9A)
- [ ] TSJ flagging and annotations
- [ ] Document attachment detection

### Phase 3: Frontend + Export
- [ ] UI integration with `PDF-Extractor`
- [ ] Structured preview and download
- [ ] CSV/JSON/Airtable export

### Phase 4: Bonus/AI Layer (Optional)
- [ ] Natural language summary per section
- [ ] Flag inconsistencies or missing data
- [ ] Ask questions like: "Did they include all their 1099s?"

---

## Dependencies
- `PyPDF2` or `pdfplumber` for text extraction
- `pytesseract` for OCR
- `re` for regex-based field parsing
- Optional: `pdf2image` for rasterizing PDFs
- Existing `PDF-Extractor` infrastructure for UI and upload

---

## Notes
- Organizers from CCH, UltraTax, Drake, and Lacerte follow similar layouts
- Worksheet codes like `5A`, `14A`, etc. are stable anchors for parsing
- Parsing errors should log line, page, and reason
- Metadata (e.g. year, client name) can also be extracted from headers

---

## Author
Professor Synapse 🧙🏾‍♂️ — Conductor of Expert Parsers

## Additional Implementation Notes

- Extraction should be partial: if some sections or fields fail, return all successfully extracted data and log errors in the metadata.errors array. Upstream users can fill in missing fields manually.
- Attempt to infer field types (number, date, checkbox, etc.), but never block extraction if parsing fails. If a value cannot be parsed to its logical type, default to string. Ambiguous or multi-valued fields should be captured as strings.
- No plugin/config system required; parser should be extensible but focus on current workbook format.
- No special requirements for redaction, anonymization, or performance limits.
- Module should be importable and follow the same interface as other parsers (e.g., can_parse, parse, etc.). Implement a can_parse (auto-detect) feature to identify tax organizer workbooks.

