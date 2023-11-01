# PDF Extractor for VISA Card Statements

## Description
This project is designed to extract VISA card purchases from PDF statements provided by Bank of America and Chase as well as Amazon Invoices. It then consolidates all transaction rows into Excel or CSV files for further processing.

## Features
- Extracts VISA card transactions from PDF statements for 2023 card statement formats.
- Supports Bank of America and Chase VISA formats and Amazon Invoices.
- Outputs consolidated transaction data to Excel and CSV formats.

## Prerequisites
- Python 3.x
- pip

## Installation
First, clone the repository to your local machine:

git clone https://github.com/glindberg2000/PDF-extractor.git


Then install the necessary packages:

pip install -r requirements.txt


## Usage
To run the project, put your VISA card and/or Amazon Invoice PDF statements in the corresponding folders. For Amazon Invoices click on Invoice details, then click on the print to pdf option on the top of the page to generate PDF for each invoice. Navigate to the project directory and run the following command(s):

python pdf_bofa_extract.py
python pdf_chase_extract.py
python pdf_amazon_extract.py


## Modules Used
- `os` for operating system dependent functionalities.
- `re` for regular expressions.
- `pandas` for data manipulation and analysis.
- `PyPDF2`,`PDFPlumber` for PDF file reading.
- `datetime` for manipulating dates and times.

## To-Do
- [ ] Add support for Wells Fargo statements.
- [X] Add support for Amazon purchase records.
- [ ] Implement AI analysis for categorizing all transactions based on descriptions.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[A[Apache License 2.0](https://choosealicense.com/licenses/apache-2.0/)]]