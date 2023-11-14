
# DataExtractAI

## Introduction
`DataExtractAI` is a tool designed for parsing various financial documents and classifying transactions using advanced AI techniques. It streamlines the process of extracting data from PDFs, such as bank statements and credit card invoices, and uses AI to intelligently categorizes transactions, aiding in financial analysis and reporting.

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

