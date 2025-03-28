# PDF Transaction Extractor

A powerful tool for extracting, categorizing, and analyzing financial transactions from PDF statements using AI.

## Features

- **Multi-Format Support**: Handles various PDF statement formats
- **AI-Powered Categorization**: Intelligent transaction classification
- **Multi-Client Support**: Manage multiple client accounts
- **Google Sheets Integration**: Export data to spreadsheets
- **Custom Category Management**: AI-assisted category creation and management
- **Business Context Awareness**: Industry-specific categorization

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/PDF-extractor.git
cd PDF-extractor
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

## Usage

### Command Line Interface

The CLI provides an interactive menu system for managing clients and processing documents. To start:

```bash
python main.py
```

This will present you with the following options:
1. Client Management
   - Create new client
   - List clients
   - Update client
   - Delete client
   - Manage categories
   - Enhance business profile
2. Process Documents
3. Categorize Transactions
4. Upload to Google Sheets
5. Google Sheets Setup

### Supported Document Types

Place your PDF files in the appropriate input directories:
```
data/clients/<client_name>/input/<parser_type>/
```

Available parser types:
- `amazon` - Amazon order invoices
- `bofa_bank` - Bank of America bank statements
- `bofa_visa` - Bank of America credit card statements
- `chase_visa` - Chase Visa credit card statements
- `wellsfargo_bank` - Wells Fargo bank statements
- `wellsfargo_mastercard` - Wells Fargo Mastercard statements
- `wellsfargo_visa` - Wells Fargo Visa statements
- `wellsfargo_bank_csv` - Wells Fargo bank CSV exports
- `first_republic_bank` - First Republic bank statements

### Client Configuration

Each client needs a configuration file at `data/clients/<client_name>/client_config.yaml`:

```yaml
business_type: "Business Type"
business_details:
  industry: "Industry"
  business_activities: ["Activity 1", "Activity 2"]
  typical_expenses: ["Expense 1", "Expense 2"]
  location: "Location"
  annual_revenue: "Revenue Range"
custom_categories: []
```

## Development

### Project Structure

```
dataextractai/
├── agents/           # AI agents for different tasks
├── cli/             # Command-line interface
├── parsers/         # PDF parsing modules
├── utils/           # Utility functions
└── __init__.py
```

### Running Tests

```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

# DataExtractAI

## Overview
DataExtractAI comes in two versions:
1. **Command-Line Version (Original/Stable)**: Parser-based approach for specific financial institutions
2. **Vision Version (Experimental)**: Uses GPT-4 Vision for universal document support

# Command-Line Version

## Introduction
The original `DataExtractAI` is a robust tool for parsing various financial documents and classifying transactions using advanced AI techniques. It streamlines the process of extracting data from PDFs, such as bank statements and credit card invoices, and uses AI to intelligently categorize transactions, aiding in financial analysis and reporting.

## Features
- Parses multiple PDF document types, including bank statements and credit card invoices.
- Includes parsers for Amazon, Bank of America, Chase, and Wells Fargo documents.
- Integrates with the OpenAI API to leverage AI models for transaction classification.
- Outputs structured data in CSV format for easy integration with financial systems.
- Uplaods to Google Sheets for display and formatting

## Getting Started

### Prerequisites
- Python 3.x
- pip

### Installation
Clone the repository to your local machine:
```bash
git clone https://github.com/yourusername/PDF-Extractor.git
```

Navigate to the project directory and install the necessary packages:
```bash
pip install -r requirements.txt
```

OR 

Conda environment setup:
```bash
conda env create -f environment.yml
```

OR 

## Alternative for one step set up of the Environment
To set up the required environment:

1. Install [Anaconda or Miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) if you haven't already.
2. Clone the repository and navigate to the project directory.
3. Run `conda env create -f environment.yml` to create a new Conda environment with all the required dependencies.
4. Activate the new environment using `conda activate <env_name>`.


### File Structure
```
├── README.MD
├── conda-requirements.txt
├── data
│   ├── input
│   │   ├── amazon
│   │   ├── bofa_bank
│   │   ├── bofa_visa
│   │   ├── chase_visa
│   │   ├── client_info
│   │   ├── wellsfargo_bank
│   │   └── wellsfargo_mastercard
│   └── output
│       ├── batch_outputs
│       └── state.json
├── dataextractai
│   ├── __init__.py
│   ├── classifiers
│   │   ├── __init__.py
│   │   └── ai_categorizer.py
│   ├── parsers
│   │   ├── __init__.py
│   │   ├── amazon_parser.py
│   │   ├── bofa_bank_parser.py
│   │   ├── bofa_visa_parser.py
│   │   ├── chase_visa_parser.py
│   │   ├── run_parsers.py
│   │   ├── wellsfargo_bank_parser.py
│   │   └── wellsfargo_mastercard_parser.py
│   └── utils
│       ├── __init__.py
│       ├── config.py
│       ├── data_transformation.py
│       └── utils.py
├── directory_structure.txt
├── environment.yml
├── requirements.txt
├── pyproject.toml
├── requirements.txt
├── scripts
│   ├── __init__.py
│   └── grok.py
├── setup.py
└── tests
    ├── __init__.py
    ├── print_samples.py
```

## Usage

All commands have a help function which can be invoked with '--help'. The main script is:
```bash
python scripts/grok.py --help
```
![Main help menu](assets/main_menu.png)

To use `DataExtractAI`, place your PDF documents in the appropriate `data/input` statement directories (parsers are updated as of November, 2023 statement formats) and run the appropriate parser script directly or you can run all parsers at once using the command:

```bash
python scripts/grok.py run-parsers
```

The transactions will be saved individually in their original column formats and also transformed, merged and saved in the `data/output` directory as CSV file (consolidated_core_output.csv):

![Parser Output](assets/parser_output.png)

Use the AI classifier command to  categorize, classify, and justify each transaction for bookkeeping purposes. It's currently set up to use a bookeeper AI Assistant (AmeliaAI) using Open AI model 3.5 Turbo - 1106 which works well for simple transactions and is cost effective. For more complex transactions you can pass in the assistant '-- ai_name DaveAI' which is set up to gpt4-turbo and has a more extensive CPA system prompt. For best results create a client text file in the inputs/client_info folder which describes your personal business or job situation, marital status, any tools or expenses which are typically used in your business or craft. This will help AI consider whether they are personal or business expenses for tax purposes classificaiton.

You can adjust the AI batch size processing by adding --batch-size 
This ensures that AI processed files are saved in batches in case there is a break in connectivity with Open AI and don't want to re-process them and incur added expenses.

```bash
python scripts/grok.py process
```

 Sample output from AI batch rocessing:

![Process Output](assets/process_output.png)

After reviewing the batch files you can merge them into one consolidated file (consolidated_batched_output.csv) or merge directly without reviewing using the command process --merge-directly:

```bash
python scripts/grok.py merge-batch-files
```

To use the google sheets uploader be sure to export your google sheets auth key"

'export GOOGLE_SHEETS_CREDENTIALS_PATH = xxxx'

and the Sheet identifier which you will be uplaoding to:

'export GOOGLE_SHEETS_ID = xxxx'

 The file will be named 'ExpenseReport' unless changed in the config.py:

```bash
python scripts/grok.py upload-to-sheet
```

## Built With
- Python 3 - The programming language used.
- OpenAI API - For leveraging AI models for classification.
- pdfplumber, Fitz, PyPDF2 - Libraries used for PDF processing.

## Contributing
Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

## Versioning
We use [SemVer](http://semver.org/) for versioning. For the versions available, see the tags on this repository.

## Authors
- **Gregory Lindberg** - *Initial work* - [glindberg2000](https://github.com/glindberg2000)
- Updated on November 5, 2023

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contact
If you have any questions or suggestions, please feel free to contact us at [greglindbereg@gmail.com](mailto:greglindbereg@gmail.com).

## Acknowledgements
- OPENAI for breakthrough AI technology without which this coding could not have been completed, and all open source AI tools paving the way to massive productivity increases. 

# Vision Version (Experimental)

## Introduction
`DataExtractAI Vision` is a modernized tool that uses GPT-4 Vision to extract transaction data from any financial document format. This experimental version aims to eliminate the need for document-specific parsers.

## Features
- Universal PDF Support: Works with any financial document format
- AI-Powered Extraction: Uses GPT-4 Vision for accurate data extraction
- Automatic Transaction Categorization: Includes best-guess transaction categories
- Multi-Client Support: Organized structure for handling multiple clients
- Simple Interface: Easy-to-use command-line tools
- Batch Processing: Handle multiple documents efficiently
- Structured Output: Clean CSV format for easy integration

## Getting Started

### Prerequisites
- Python 3.8 or higher
- OpenAI API key with GPT-4 Vision access
- `poppler-utils` for PDF processing:
  - macOS: `brew install poppler`
  - Ubuntu: `apt-get install poppler-utils`
  - Windows: Download from [poppler releases](http://blog.alivate.com.au/poppler-windows/)

### Installation
1. Clone the repository:
```bash
git clone https://github.com/glindberg2000/PDF-extractor.git
cd PDF-extractor
```

2. Create and activate virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install the package:
```bash
pip install -e .
```

### Configuration
1. Set your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```
Or create a `.env` file:
```
OPENAI_API_KEY=your-api-key-here
```

## Setting Up a New Client

### 1. Create Client Directory
```bash
# Create new client directory from template
cp -r clients/_template clients/new_client_name
```

### 2. Configure Client Settings
1. Edit `clients/new_client_name/client_config.yaml`:
   - Update client information
   - Customize transaction categories
   - Set processing preferences

### 3. Prepare Document Directories
The client directory structure:
```
clients/
├── new_client_name/
│   ├── client_config.yaml
│   ├── input/           # Place PDF statements here
│   └── output/          # Processed results appear here
├── _template/           # Template for new clients
└── _examples/           # Example configurations
```

### 4. Process Documents
1. Place PDF statements in the client's input directory
2. Run the processor:
```bash
# Process a single file
dataextractai-vision process-file clients/new_client_name/input/statement.pdf --output clients/new_client_name/output

# Process all files in input directory
dataextractai-vision process-dir clients/new_client_name/input --output clients/new_client_name/output
```

## Example Client Setup
Check out the example client configuration in `clients/_examples/tech_consultant/` for a sample setup of a technology consulting business.

## Output Format
The tool generates CSV files with the following columns:
- `date`: Transaction date (YYYY-MM-DD format)
- `description`: Full transaction description
- `amount`: Transaction amount (negative for debits)
- `category`: Best-guess transaction category

Example:
```csv
date,description,amount,category
2024-03-14,AMAZON.COM PURCHASE,-29.99,Shopping
2024-03-15,DIRECT DEPOSIT SALARY,5000.00,Income
```

## Best Practices
1. Client Organization
   - Keep each client's data separate in their own directory
   - Use meaningful client directory names
   - Maintain client-specific configuration files

2. Document Management
   - Organize input documents by date or type
   - Regular backup of processed data
   - Review output files promptly

3. Configuration
   - Customize categories based on client's business
   - Adjust batch sizes based on document volume
   - Document any special processing requirements

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contact
For questions or suggestions, please contact [greglindbereg@gmail.com](mailto:greglindbereg@gmail.com).

## Acknowledgements
- OpenAI for the powerful GPT-4 Vision API
- The open-source community for various Python libraries
- All contributors and users of the project

## Client Data Structure

The project uses a standardized directory structure for client data:

```
data/clients/
├── _template/              # Template structure for new clients
│   ├── client_config.yaml  # Template configuration
│   ├── input/             # Input directories for different parsers
│   │   ├── amazon/
│   │   ├── bofa_bank/
│   │   ├── bofa_visa/
│   │   ├── chase_visa/
│   │   ├── first_republic_bank/
│   │   ├── wellsfargo_bank/
│   │   ├── wellsfargo_bank_csv/
│   │   ├── wellsfargo_mastercard/
│   │   └── wellsfargo_visa/
│   └── output/            # Processed output files
├── _examples/             # Example client setups
│   └── tech_consultant/   # Example for a tech consultant
└── [client_name]/         # Individual client directories
```

### Setting Up a New Client

1. Copy the `_template` directory to create a new client:
   ```bash
   cp -r data/clients/_template data/clients/new_client_name
   ```

2. Edit the `client_config.yaml` file to set:
   - Client name and type
   - Google Sheets configuration
   - Parser selection
   - AI processing settings
   - Custom categories

3. Place source documents in the appropriate input directories:
   - Bank statements in respective bank folders
   - Credit card statements in respective card folders
   - Ensure files are in supported formats (PDF, CSV)

### Client Configuration

The `client_config.yaml` file controls:
- Sheet names and IDs for Google Sheets export
- Which parsers to run for the client
- AI assistant selection and settings
- Custom categories for expense classification

See the example configurations in `data/clients/_examples/` for reference implementations.

