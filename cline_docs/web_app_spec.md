# Web App Specification for PDF Extractor

## Overview

The web app will serve as an interface for managing business profiles, categories, and keywords, as well as displaying and handling transactions and tax worksheets. It will interact with the existing database and leverage AI for certain operations.

## Key Features

### 1. Business Profile Management
- **Manual Entry**: Users can manually input business type, description, custom categories, industry keywords, and other profile data.
- **AI Assistance**: The app will use AI to suggest industry insights, category hierarchies, and business context based on the entered data.
- **Profile Storage**: Profiles will be stored in the `business_profiles` table in the database.

### 2. Category and Keyword Management
- **Category Creation**: Users can create and manage categories, linking them to specific tax worksheets.
- **Keyword Management**: Users can manage industry keywords that influence transaction classification.
- **Database Interaction**: Categories and keywords will be stored in the `client_expense_categories` and `business_profiles` tables.

### 3. Transaction Management
- **Transaction Display**: Display transactions from the `normalized_transactions` table, allowing users to view and edit details.
- **Classification**: Use AI to classify transactions into business or personal categories, and assign them to tax worksheets.
- **Status Tracking**: Track processing status using the `transaction_status` table.

### 4. Tax Worksheet Generation
- **Worksheet Display**: Generate and display tax worksheets (6A, Auto, HomeOffice, Personal) based on classified transactions.
- **Excel Export**: Allow users to export worksheets to Excel for tax preparation.

## Database Schema

### Business Profiles Table
- `client_id`: INTEGER, PRIMARY KEY
- `business_type`: TEXT
- `business_description`: TEXT
- `custom_categories`: JSON
- `industry_keywords`: JSON
- `category_patterns`: JSON
- `industry_insights`: TEXT
- `category_hierarchy`: JSON
- `business_context`: TEXT
- `profile_data`: JSON

### Normalized Transactions Table
- `id`: INTEGER, PRIMARY KEY
- `client_id`: INTEGER
- `transaction_id`: TEXT
- `transaction_date`: DATE
- `description`: TEXT
- `amount`: REAL
- `normalized_amount`: REAL
- `source`: TEXT
- `transaction_type`: TEXT

### Transaction Classifications Table
- `id`: INTEGER, PRIMARY KEY
- `client_id`: INTEGER
- `transaction_id`: TEXT
- `payee`: TEXT
- `category`: TEXT
- `classification`: TEXT

### Client Expense Categories Table
- `id`: INTEGER, PRIMARY KEY
- `client_id`: INTEGER
- `category_name`: TEXT
- `category_type`: TEXT
- `description`: TEXT
- `tax_year`: INTEGER
- `worksheet`: TEXT

## Interaction with AI and Database
- **AI Integration**: Use AI for classification and insights generation.
- **Database Operations**: CRUD operations on profiles, categories, and transactions.

## Additional Considerations
- **User Interface**: Design a user-friendly interface for easy navigation and data entry.
- **Security**: Implement authentication and authorization to protect sensitive data.
- **Scalability**: Ensure the app can handle multiple clients and large datasets efficiently.

---

This specification provides a foundation for an app designer to brainstorm and design the web app, ensuring it aligns with the existing system and meets user needs. 