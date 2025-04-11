# Project Specification: PDF Extractor Web Application

## 1. Introduction & Goals

This document outlines the technical specification for building a web application companion to the Amelia AI PDF Extractor toolkit.

**Primary Goals:**

*   Provide a user-friendly web interface for managing client business profiles, expense categories, and keywords.
*   Display and facilitate the classification of financial transactions, leveraging existing AI capabilities.
*   Generate and allow export of tax worksheets based on classified transactions.
*   Offer AI-driven suggestions and insights during profile management.
*   Serve as the primary interface for a single user interacting with client data.

This specification assumes a low-load environment with a single concurrent user. Scalability is a secondary concern to functionality and ease of use for this primary user.

## 2. High-Level Architecture

*   **Backend Framework:** Python / Django
    *   *Reasoning:* Leverages the existing Python codebase (`TransactionClassifier`, potential database interaction logic). Django's "batteries-included" nature (ORM, Admin, Forms, Auth) accelerates development for CRUD-heavy applications.
*   **Database:** PostgreSQL
    *   *Reasoning:* Offers robust data types (including mature JSONB support for profile fields), data integrity features, and is a standard, well-supported database for Django applications. It provides a clear upgrade path from SQLite.
*   **Data Ingestion Modification:** The existing data parsing/ingestion process (currently writing to SQLite) **must be updated** to write directly to the PostgreSQL database according to the Django model schema (defined in Section 4). This is essential for supporting new clients and ongoing data processing, not just the initial migration of existing data.
*   **Frontend:** Django Templates + HTMX
    *   *Reasoning:* Enables dynamic UI updates (e.g., after AI processing) without full page reloads and avoids the complexity of a separate JavaScript SPA framework. Keeps the focus on server-side logic within Django.
*   **AI Integration:** Direct calls to Python functions/classes (e.g., `TransactionClassifier`) within Django views or background tasks.
*   **Deployment (Initial):** Docker Compose (Django App + Postgres DB) or a simple Platform-as-a-Service (PaaS).

## 3. Core Features (Detailed User Flows & UI)

### 3.1. Authentication & Client Selection
*   **Auth:** Simple Django session-based login for a single pre-defined superuser. No public registration.
*   **Client Context:** Upon login, the user should be able to select the `client_name` they wish to work with. This context should persist throughout the session and filter data accordingly. A dropdown or searchable list populated from available data (e.g., existing profiles or transaction files) should be used.

### 3.2. Business Profile Management
*   **UI:** A dedicated section for managing Business Profiles.
    *   List view: Display existing profiles (Client ID, Business Type).
    *   Detail/Edit view: Form to Create/Update/View a profile for the selected client.
*   **Fields:** Map directly to the `business_profiles` table schema (see Section 4). Use appropriate Django form fields (TextField, JSONField widgets if available/practical, etc.).
*   **AI Assistance:**
    *   **Trigger:** A button ("Generate AI Insights/Suggestions") within the profile edit form.
    *   **Action:** Call a backend function (potentially async using HTMX polling or WebSockets if long-running) that uses the profile data (description, type, keywords) to query an LLM.
    *   **Display:** Update fields like `industry_insights`, `category_hierarchy`, `business_context` directly in the form using HTMX partial updates. Provide clear visual indication while processing.
*   **Storage:** CRUD operations via Django ORM interacting with the `business_profiles` table.

### 3.3. Category and Keyword Management
*   **UI:** Dedicated section, likely linked from Business Profile or main navigation.
    *   Tabbed interface or separate pages for "Expense Categories" (`client_expense_categories`) and "Industry Keywords" (stored within `business_profiles.industry_keywords`).
*   **Expense Categories:**
    *   CRUD interface for `client_expense_categories` table (Category Name, Type, Description, Tax Year, Worksheet linkage).
    *   Use dropdowns/select widgets for `category_type` and `worksheet`.
*   **Industry Keywords:**
    *   Interface to add/remove keywords within the selected client's `business_profiles.industry_keywords` JSON field. Display current keywords clearly.
*   **Storage:** CRUD via Django ORM.

### 3.4. Transaction Management
*   **UI:** A primary dashboard/table view displaying transactions from `normalized_transactions` for the selected client.
    *   **Table Columns:** Include fields from `normalized_transactions` and related `transaction_classifications` (ID, Date, Description, Amount, Payee, Category, Classification, Status).
    *   **Filtering/Searching:** Allow filtering by date range, classification status (e.g., "Unclassified", "Business", "Personal", "Needs Payee", "Needs Category"), and searching by description/payee.
    *   **Pagination:** Implement pagination for large transaction sets.
*   **Editing:**
    *   Allow inline editing (via HTMX) or a modal/detail view to update fields in the `transaction_classifications` table (Payee, Category, Classification).
*   **AI Classification (Multi-Step Process):** The classification involves: 1) Payee Extraction, 2) Category Classification, 3) Business/Personal Determination.
    *   **Triggers (UI):**
        *   Buttons per transaction for each step: "Extract Payee", "Classify Category", "Classify Business/Personal".
        *   A button per transaction for the full pipeline: "Classify Full".
        *   Bulk action buttons: "Extract Payee (Unprocessed)", "Classify Category (Needs Category)", "Classify Bus/Pers (Needs Bus/Pers)", "Classify Full (Unclassified)".
    *   **Action:** Backend views will call the relevant parts of the `TransactionClassifier` logic or associated functions. Handle potential long processing times as described below.
        *   *Step 1 (Payee Extraction):* Input: Description. Output: Suggested Payee, enhanced description. Updates `TransactionClassification.payee`.
        *   *Step 2 (Category Classification):* Input: Enhanced Description, Payee, Amount, Date, Client Context. Output: Suggested `ClientExpenseCategory`. Updates `TransactionClassification.category`.
        *   *Step 3 (Business/Personal):* Input: All previous info + Category. Output: 'Business' or 'Personal'. Updates `TransactionClassification.classification`.
        *   *Full Pipeline:* Executes steps 1-3 sequentially.
    *   **Processing Time Handling:**
        *   Option A (Simpler): Synchronous calls with loading indicators via HTMX for individual steps/transactions if expected to be fast (< ~3 seconds).
        *   Option B (Robust): Trigger background tasks (Celery recommended) for bulk actions or potentially the full pipeline per transaction. Update status via polling (HTMX) or WebSockets.
    *   **Display:** Update the relevant transaction row fields and status upon completion of each step or the full pipeline using HTMX partials.
*   **Storage:** Read from `normalized_transactions`. CRUD operations on `transaction_classifications` via Django ORM. The `status` field in `TransactionClassification` should reflect the current processing state (e.g., 'Pending Payee', 'Pending Category', 'Pending Bus/Pers', 'Classified', 'Review Needed').

### 3.5. Tax Worksheet Generation
*   **UI:** A dedicated section to generate worksheets.
*   **Trigger:** User selects worksheet type (6A, Auto, HomeOffice, Personal, **Review/Unclassified**) and Tax Year. Clicks "Generate Worksheet".
*   **Action:** Backend logic queries `transaction_classifications` filtered by client, year, and classification status.
    *   **For Official Worksheets (6A, Auto, HomeOffice):** Filter for `classification='Business'` and the relevant `worksheet` linkage (from `ClientExpenseCategory.worksheet`).
    *   **Handling 6A 'Other Expenses':** The query should retrieve all categories linked to worksheet '6A'. The rendering logic will need to group standard categories and sum up remaining ('Other') user-defined 6A categories separately.
    *   **For Personal/Review Worksheet:** Filter for `classification='Personal'` or statuses like 'Unclassified', 'Needs Review'.
    *   Aggregate data as needed per worksheet format.
*   **Display:** Render the worksheet data in an HTML table on the page.
*   **Export:** Provide an "Export to Excel" button that generates and downloads an Excel file (`.xlsx`) representation of the displayed worksheet. Use libraries like `openpyxl` or `pandas.ExcelWriter`. Ensure the export reflects the specific filtering applied (e.g., no Personal transactions in the 6A export).

## 4. Database Schema (PostgreSQL with Django ORM)

Define Django models corresponding to the schema outlined in `web_app_spec.md`, using appropriate Django field types.

*   **`BusinessProfile` Model (`business_profiles` table):**
    *   `client_id`: `models.CharField(max_length=..., primary_key=True)` (Assuming client ID is not just an integer sequence and is unique string identifier like `client_name` used elsewhere) or `models.ForeignKey(User, on_delete=models.CASCADE)` if linked to Django users. **Clarify Client ID source/type. Assuming CharField for now.**
    *   `business_type`: `models.TextField(blank=True, null=True)`
    *   `business_description`: `models.TextField(blank=True, null=True)`
    *   `custom_categories`: `models.JSONField(default=dict, blank=True)` # Purpose? Relation to ClientExpenseCategory? For suggestions?
    *   `industry_keywords`: `models.JSONField(default=list, blank=True)` # Seems clear.
    *   `category_patterns`: `models.JSONField(default=dict, blank=True)` # **CONFIRM PURPOSE / REDUNDANCY.** How is this used? Different from keyword/category mapping?
    *   `industry_insights`: `models.TextField(blank=True, null=True)` # AI Generated.
    *   `category_hierarchy`: `models.JSONField(default=dict, blank=True)` # AI Generated.
    *   `business_context`: `models.TextField(blank=True, null=True)` # AI Generated.
    *   `profile_data`: `models.JSONField(default=dict, blank=True)` # **CONFIRM PURPOSE / REDUNDANCY.** Generic blob, avoid if possible. Specify needed fields directly.

*   **`NormalizedTransaction` Model (`normalized_transactions` table):**
    *   `id`: `models.AutoField(primary_key=True)`
    *   `client`: `models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='transactions')` **Confirmed relationship.**
    *   `transaction_id`: `models.CharField(max_length=255, unique=True)` **Assuming text transaction ID, confirm max length.**
    *   `transaction_date`: `models.DateField()`
    *   `description`: `models.TextField()`
    *   `amount`: `models.DecimalField(max_digits=10, decimal_places=2)`
    *   `normalized_amount`: `models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)`
    *   `source`: `models.CharField(max_length=100)` **Confirm max length.**
    *   `transaction_type`: `models.CharField(max_length=50)` **Confirm max length.**

*   **`TransactionClassification` Model (`transaction_classifications` table):**
    *   `id`: `models.AutoField(primary_key=True)`
    *   `transaction`: `models.OneToOneField(NormalizedTransaction, on_delete=models.CASCADE, related_name='classification_details')` **Verified: One classification record per transaction.**
    *   `client`: `models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='classifications')` **Technically redundant if always accessed via transaction, but potentially useful for direct client-level queries/indexing. Keep for now unless performance dictates otherwise.**
    *   `payee`: `models.CharField(max_length=255, blank=True, null=True)` **Confirm max length.**
    *   `category`: `models.ForeignKey('ClientExpenseCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')`
    *   `classification`: `models.CharField(max_length=50, blank=True, null=True, choices=[('Business', 'Business'), ('Personal', 'Personal')])` # Added choices
    *   `status`: `models.CharField(max_length=50, default='Pending Payee', choices=[('Pending Payee', 'Pending Payee'), ('Pending Category', 'Pending Category'), ('Pending Bus/Pers', 'Pending Bus/Pers'), ('Classified', 'Classified'), ('Needs Review', 'Needs Review')])` # Added status field with choices

*   **`ClientExpenseCategory` Model (`client_expense_categories` table):**
    *   `id`: `models.AutoField(primary_key=True)`
    *   `client`: `models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='expense_categories')`
    *   `category_name`: `models.CharField(max_length=255)` **Confirm max length.**
    *   `category_type`: `models.CharField(max_length=50, choices=[('Income', 'Income'), ('Expense', 'Expense')])` # Added choices
    *   `description`: `models.TextField(blank=True, null=True)`
    *   `tax_year`: `models.IntegerField()`
    *   `worksheet`: `models.CharField(max_length=50, choices=[('6A', '6A'), ('Auto', 'Auto'), ('HomeOffice', 'HomeOffice'), ('Personal', 'Personal'), ('None', 'None')])` # Added choices
    *   **Constraint:** `models.UniqueConstraint(fields=['client', 'category_name', 'tax_year'], name='unique_client_category_year')` # Added constraint

**Note:** Relationships (ForeignKey, OneToOneField) need verification based on actual data flow and uniqueness requirements.

## 5. AI Integration Details

*   **Transaction Classification:**
    *   The Django view handling the "Classify" action will instantiate or call the existing `TransactionClassifier` class/functions.
    *   It will pass the necessary transaction data (description, amount, date, potentially payee) and client context (profile info, categories, keywords).
    *   The classifier should return structured data (suggested category, classification type - Business/Personal).
    *   The view updates the `TransactionClassification` model instance.
*   **Profile Insights:**
    *   A dedicated utility function/service within Django will encapsulate the LLM call logic.
    *   Input: Business description, type, keywords.
    *   Output: JSON or text containing insights, hierarchy suggestions, context.
    *   LLM Interaction: Use a suitable Python library (e.g., `openai`, `langchain`) to interact with the chosen LLM API. API keys should be managed securely via environment variables or Django settings.

## 6. API Endpoints

Primarily, interactions will be handled via standard Django views rendering HTML, enhanced with HTMX requests targeting specific view endpoints designed to return HTML partials. No separate REST API is planned initially. Potential HTMX target endpoints:

*   `/clients/<client_id>/profile/ai_insights/` (POST, returns profile fields partial)
*   `/clients/<client_id>/transactions/<tx_id>/extract_payee/` (POST, returns updated transaction row partial)
*   `/clients/<client_id>/transactions/<tx_id>/classify_category/` (POST, returns updated transaction row partial)
*   `/clients/<client_id>/transactions/<tx_id>/classify_business_personal/` (POST, returns updated transaction row partial)
*   `/clients/<client_id>/transactions/<tx_id>/classify_full/` (POST, returns updated transaction row partial)
*   `/clients/<client_id>/transactions/extract_payee_bulk/` (POST, returns status message or updated table partial)
*   `/clients/<client_id>/transactions/classify_category_bulk/` (POST, returns status message or updated table partial)
*   `/clients/<client_id>/transactions/classify_business_personal_bulk/` (POST, returns status message or updated table partial)
*   `/clients/<client_id>/transactions/classify_full_bulk/` (POST, returns status message or updated table partial)
*   `/clients/<client_id>/transactions/<tx_id>/edit/` (GET for form, POST for update, returns updated row partial)
*   `/clients/<client_id>/categories/` (Standard Django CRUD views/URLs, potentially using HTMX for list updates)
*   `/clients/<client_id>/keywords/` (Endpoints to add/delete, returning updated list partial)

## 7. Frontend Details

*   **Framework:** Django Templates with standard HTML, CSS.
*   **Dynamic Behavior:** HTMX for partial page updates, form submissions without full reloads, triggering backend actions.
*   **CSS:** Use a simple CSS framework (e.g., Bootstrap, TailwindCSS via CDN or basic setup) for styling and layout consistency, or custom CSS.
*   **JavaScript:** Minimal custom JavaScript. Use HTMX attributes where possible.

## 8. Deployment

*   **Recommendation:** Docker Compose locally and potentially for production.
    *   `docker-compose.yml` defining services for:
        *   Django web application (using `python:latest` or specific version).
        *   PostgreSQL database (using `postgres:latest` or specific version).
    *   Include volume mounts for persistent data (Postgres data, potentially media files if any).
    *   Use `.env` file for configuration (DB credentials, Django secret key, LLM API keys).
*   **Alternatives:** PaaS like Heroku, Render, or Fly.io.

## 9. Non-Functional Requirements

*   **Security:**
    *   Use Django's built-in authentication for the single user.
    *   Protect against common web vulnerabilities (CSRF - handled by Django, XSS - use template escaping, SQL Injection - handled by ORM).
    *   Securely store secrets (API keys, `SECRET_KEY`).
*   **Logging:** Configure basic Django logging to file or stdout for monitoring and debugging.
*   **Error Handling:** Implement user-friendly error pages and provide informative feedback for failed operations (e.g., AI classification errors).

## 10. Development Setup

*   **Repository:** Git repository.
*   **Dependencies:** `requirements.txt` including `Django`, `psycopg2-binary` (or `psycopg2`), `requests` (for LLM), `openpyxl` (for Excel), `python-dotenv`, `django-htmx`. Add `dataextractai` modules or refactor them into the Django project structure.
*   **Database:** Local PostgreSQL instance running (via Docker or installed directly).
*   **Environment:** `.env` file for local configuration.
*   **README:** Include clear setup instructions in `README.md`.

## 11. Future Considerations

*   Multi-user support with permissions.
*   More sophisticated background task handling (Celery).
*   Real-time updates (WebSockets).
*   Enhanced dashboarding and reporting.
*   Direct PDF upload and processing integration.
*   Unit and integration tests.

## 12. Data Migration (SQLite to PostgreSQL)

*   **Requirement:** Existing data currently resides in SQLite databases (`client_name.db` likely). This data needs to be migrated to the new PostgreSQL database structure defined by the Django models (Section 4) before the web application can be fully utilized.
*   **Strategy:** The web application itself **should not** perform the migration during runtime. A separate, one-time migration process is required.
*   **Recommended Approaches:**
    1.  **Standalone Python Script:** Create a script using libraries like `sqlite3`, `psycopg2`, and potentially `SQLAlchemy` or `pandas`. This script will:
        *   Connect to the source SQLite database(s).
        *   Connect to the target PostgreSQL database.
        *   Read data from SQLite tables.
        *   Transform data as needed to match the Django model schema (handle data type differences, relationships, JSON structures).
        *   Write the transformed data to the corresponding PostgreSQL tables.
        *   This offers maximum control over the mapping and transformation logic.
    2.  **ETL/Migration Tools:** Utilize tools designed for database migration, such as `pgloader`. This might require configuration files defining the source (SQLite) and target (PostgreSQL) schemas and mapping rules. This can be faster for simpler migrations but offers less custom transformation logic.
*   **Considerations:**
    *   **Schema Mapping:** Carefully map old table columns to the new Django model fields.
    *   **Data Transformation:** Handle differences in data types (e.g., TEXT vs VARCHAR, JSON handling).
    *   **Foreign Keys:** Ensure relationships are correctly established in PostgreSQL.
    *   **Client Databases:** Determine if migration needs to happen per-client or consolidated.
    *   **Testing:** Thoroughly test the migration script/process on sample data before running on production data.
    *   **Backup:** **CRITICAL:** Back up the original SQLite databases before attempting any migration (as per `database-rules.mdc`).
*   **Timing:** This migration should occur after the PostgreSQL database schema is finalized (via Django migrations `makemigrations`, `migrate`) but before the web application is deployed or used with real data. 