# Legacy Parser Utility

## Overview
This directory contains the legacy CLI-based parser utility that was used before the Django project implementation. It serves as a preprocessing tool for data before ingestion into the main Django application.

## Components

### 1. Legacy Parser (`app/`)
- Preprocess and parse data files before ingestion
- Handle initial data validation and transformation
- Provide CLI tools for data management

### 2. DataExtractAI (`dataextractai/`)
- Main CLI application for transaction processing
- AI-powered classification system
- Database integration
- Interactive menu system

## Directory Structure

### Legacy Parser
- `cli.py`: Main command-line interface
- `parser/`: Core parsing functionality
- `sheets/`: Spreadsheet processing utilities
- `utils/`: Helper functions and utilities
- `client/`: API client implementations

### DataExtractAI
- `main.py`: Entry point for the CLI application
- `menu.py`: Interactive menu system
- `agents/`: AI classification components
- `db/`: Database integration
- `parsers/`: Data parsing utilities
- `classifiers/`: Classification models
- `utils/`: Helper functions

## Usage

### Running the CLI
```bash
# From the project root
python utilities/legacy_parser/main.py
```

### Preprocessing Workflow
1. Use the DataExtractAI CLI to process and classify transactions
2. Export processed data in a format compatible with the Django project
3. Use the legacy parser for additional preprocessing if needed
4. Import the processed data into the Django application

## Integration
While these are legacy tools, they're still actively used as preprocessing steps before data enters the main Django application. The workflow is:
1. Use DataExtractAI for initial processing and classification
2. Use the legacy parser for additional preprocessing if needed
3. Export processed data in a format compatible with the Django project
4. Import the processed data into the Django application

## Status
- **Maintenance**: Active but limited to bug fixes
- **New Features**: Not actively developed
- **Integration**: Used as preprocessing steps for the main Django application
