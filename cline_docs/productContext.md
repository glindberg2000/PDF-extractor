# Product Context

## Purpose
The PDF Extractor is a specialized tool designed to automate the extraction, processing, and classification of financial data from various bank statements (PDF, CSV) and other financial documents. It serves as a bridge between raw financial documents and structured, categorized financial data suitable for tax preparation and financial analysis. The primary goal is to produce clean, categorized data separated into relevant tax worksheets (6A, Auto, HomeOffice) and a Personal worksheet.

## Problems Solved
1. **Manual Data Entry Elimination**: Automates transaction data extraction, reducing errors and time.
2. **Multi-Format Support**: Handles diverse file formats, providing a unified processing interface.
3. **Client-Specific Processing**: Supports multiple clients with unique business profiles and custom categories.
4. **Intelligent Classification**: Uses AI, informed by the client's business profile, to categorize transactions and determine their relevance for different tax worksheets (6A, Auto, HomeOffice, Personal).
5. **Consistent Classification**: Aims to classify identical transactions consistently using matching logic, even with minor variations in descriptions.
6. **Tax Worksheet Preparation**: Organizes classified business expenses into specific worksheets (6A, Auto, HomeOffice), separating personal expenses.

## How It Should Work (Ideal Flow)
1. **Input Processing**: Accepts PDF/CSV files, routes them based on client configuration.
2. **Data Extraction & Normalization**: Parses documents, extracts core transaction data (Date, Description, Amount). Normalizes payee names by removing extraneous details (store #, location) for consistent matching.
3. **AI-Driven Classification (Multi-Pass)**:
   * **Pass 1 (Payee ID)**: Identifies payee using AI and normalized description. Stores normalized payee.
   * **Pass 2 (Category Assignment)**: Assigns a general expense category (e.g., "Software", "Meals") using AI, transaction details, payee, and business profile context.
   * **Pass 3 (Tax/Worksheet Classification)**:
      * Determines final tax category (e.g., "Office expenses", "Meals and entertainment") based on Pass 2 category, business profile, and predefined tax rules/categories.
      * Assigns transaction to a specific worksheet ('6A', 'Auto', 'HomeOffice', 'Personal') based on the tax category, business profile rules (e.g., vehicle expenses relevant only if business uses a vehicle), and business percentage.
      * Leverages matching logic: Looks for previously classified transactions with the same normalized payee or similar description. If found, copies existing classification (Tax Category, Worksheet, Business %) for consistency. Otherwise, uses AI.
4. **Output Generation**:
   * Stores all processed data in a database.
   * Generates an Excel file with separate sheets:
      * `6A`: Contains only transactions classified under standard 6A tax categories and client-specific 'Other Expenses' for Schedule 6A.
      * `Auto`: Contains relevant vehicle expenses.
      * `HomeOffice`: Contains relevant home office expenses.
      * `Personal`: Contains all transactions classified as personal.
      * `All Transactions`: (Optional) A sheet with all raw/processed data.
      * `Summary`: A summary sheet reflecting the categorized totals.
   * (Optional) Uploads data to Google Sheets.

## Key Features
- Multi-format support (PDF, CSV)
- Client-specific processing via Business Profiles
- AI-driven classification (Payee, Category, Tax Worksheet)
- Payee Normalization
- Consistent classification via matching logic
- Tax worksheet separation (6A, Auto, HomeOffice, Personal)
- Batch processing (Row-by-row)
- Database storage
- Excel & Google Sheets export

## Target Users
- Accountants/Bookkeepers preparing tax documents (esp. Schedule 6A)
- Small Business Owners managing finances

## Success Criteria
1. Accurate extraction of transaction data.
2. Correct AI-driven classification leveraging business profiles.
3. Consistent classification of recurring vendor transactions.
4. Accurate separation of transactions into 6A, Auto, HomeOffice, and Personal worksheets.
5. Clean and usable Excel export formatted for tax preparation.
6. Efficient row-by-row processing. 