
# DataExtractAI

## Introduction
`DataExtractAI` is a tool designed for parsing various financial documents and classifying transactions using advanced AI techniques. It streamlines the process of extracting data from PDFs, such as bank statements and credit card invoices, and intelligently categorizes transactions, aiding in financial analysis and reporting.

## Features
- Parses multiple PDF document types, including bank statements and credit card invoices.
- Includes parsers for Amazon, Bank of America, Chase, and Wells Fargo documents.
- Integrates with the OpenAI API to leverage AI models for transaction classification.
- Outputs structured data in CSV format for easy integration with financial systems.

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
Conda environment setup:
```bash
conda env create -f environment.yml
```


### File Structure
```
PDF-Extractor/
│
├── data/
│   ├── input/
│   └── output/
│
├── dataextractai/
│   ├── parsers/
│   │   ├── amazon_parser.py
│   │   ├── bofa_bank_parser.py
│   │   ├── bofa_visa_parser.py
│   │   ├── chase_visa_parser.py
│   │   ├── wells_fargo_bank_parser.py
│   │   └── wells_fargo_mastercard_parser.py
│   │
│   ├── classifiers/
│   │   └── transaction_classifier.py
│   │
│   └── utils/
│       ├── file_io.py
│       └── date_helpers.py
│
├── scripts/
│   └── run_parsers.py
│
├── tests/
│   ├── test_bank_parser.py
│   └── test_mastercard_parser.py
│
├── README.md
├── requirements.txt
└── setup.py
```

## Usage
To use `DataExtractAI`, place your PDF documents in the `data/input` directory and run the appropriate parser script or you can run all parsers using the script:
```bash
python scripts/run_parsers.py
```
The transactions will be classified and saved in the `data/output` directory as CSV files.

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

