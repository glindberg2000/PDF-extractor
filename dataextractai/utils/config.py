# dataextractai/utils/config.py
import os

# Define the base directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Common configuration paths
COMMON_CONFIG = {
    "data_dir": os.path.join(BASE_DIR, "data"),
    "input_dir": os.path.join(BASE_DIR, "data", "input"),
    "output_dir": os.path.join(BASE_DIR, "data", "output"),
}

# Parser-specific input directories
PARSER_INPUT_DIRS = {
    "amazon": os.path.join(COMMON_CONFIG["input_dir"], "amazon"),
    "bofa_bank": os.path.join(COMMON_CONFIG["input_dir"], "bofa_bank"),
    "bofa_visa": os.path.join(COMMON_CONFIG["input_dir"], "bofa_visa"),
    "chase_visa": os.path.join(COMMON_CONFIG["input_dir"], "chase_visa"),
    "wellsfargo_bank": os.path.join(COMMON_CONFIG["input_dir"], "wellsfargo_bank"),
    "wellsfargo_mastercard": os.path.join(
        COMMON_CONFIG["input_dir"], "wellsfargo_mastercard"
    ),
    "client_info": os.path.join(COMMON_CONFIG["input_dir"], "client_info"),
}

# Parser-specific output paths
PARSER_OUTPUT_PATHS = {
    "amazon": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "amazon_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "amazon_output.xlsx"),
    },
    "bofa_bank": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "bofa_bank_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "bofa_bank_output.xlsx"),
    },
    "bofa_visa": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "bofa_visa_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "bofa_visa_output.xlsx"),
    },
    "chase_visa": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "chase_visa_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "chase_visa_output.xlsx"),
    },
    "wellsfargo_bank": {
        "csv": os.path.join(COMMON_CONFIG["output_dir"], "wellsfargo_bank_output.csv"),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_bank_output.xlsx"
        ),
    },
    "wellsfargo_mastercard": {
        "csv": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_mastercard_output.csv"
        ),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_mastercard_output.xlsx"
        ),
    },
    "consolidated_core": {
        "csv": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_core_output.csv"
        ),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_core_output.xlsx"
        ),
    },
    "consolidated_updated": {
        "csv": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_updated_output.csv"
        ),
        "xlsx": os.path.join(COMMON_CONFIG["output_dir"], "consolidated__output.xlsx"),
    },
}

DATA_MANIFESTS = {
    "wellsfargo_mastercard": {
        "transaction_date": "date",
        "post_date": "date",
        "reference_number": "string",
        "description": "string",
        "credits": "float",
        "charges": "float",
        "statement_date": "date",
        "file_path": "string",
        "Amount": "float",
    },
    "bofa_bank": {
        "date": "date",
        "description": "string",
        "amount": "float",
        "transaction_type": "string",
        "statement_date": "date",
        "file_path": "string",
    },
    "amazon": {
        "order_placed": "date",
        "order_number": "string",
        "order_total": "float",
        "items_quantity": "integer",
        "gift_card_amount": "float",
        "file_path": "string",
        "price": "float",
        "quantity": "integer",
        "description": "string",
        "sold_by": "string",
        "supplied_by": "string",
        "condition": "string",
        "amount": "float",
    },
    "wellsfargo_bank": {
        "date": "date",
        "description": "string",
        "deposits": "float",
        "withdrawals": "float",
        "ending_daily_balance": "float",
        "statement_date": "date",
        "file_path": "string",
        "amount": "float",
    },
    "chase_visa": {
        "date_of_transaction": "date",
        "merchant_name_or_transaction_description": "string",
        "amount": "float",
        "statement_date": "date",
        "statement_year": "integer",
        "statement_month": "integer",
        "file_path": "string",
        "date": "date",
    },
    "bofa_visa": {
        "transaction_date": "date",
        "posting_date": "date",
        "description": "string",
        "reference_number": "string",
        "account_number": "string",
        "amount": "float",
        "statement_date": "date",
        "file_path": "string",
    },
    "core_data_structure": {
        "transaction_date": None,
        "description": None,
        "amount": None,
        "transaction_type": None,
        "file_path": None,
        "source": None,
    },
}

TRANSFORMATION_MAPS = {
    "wellsfargo_mastercard": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",  # Assuming 'Amount' is the source column with the correct sign
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_mastercard",
        "transaction_type": lambda x: "Credit Card",
    },
    "amazon": {
        "transaction_date": "order_placed",
        "description": "description",
        "amount": "amount",  # This is the calculated amount per item
        "file_path": "file_path",
        "source": lambda x: "amazon",
        "transaction_type": lambda x: "Credit Card",
    },
    "bofa_bank": {
        "transaction_date": "date",
        "description": "description",
        "amount": "amount",  # Assuming 'amount' is the source column, and the sign may need normalization
        "file_path": "file_path",
        "source": lambda x: "bofa_bank",
        "transaction_type": lambda x: "Debit/Check",
    },
    "bofa_visa": {
        "transaction_date": "transaction_date",
        "description": "description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "bofa_visa",
        "transaction_type": lambda x: "Credit Card",
    },
    "chase_visa": {
        "transaction_date": "date",
        "description": "merchant_name_or_transaction_description",
        "amount": "amount",
        "file_path": "file_path",
        "source": lambda x: "chase_visa",
        "transaction_type": lambda x: "Credit Card",
    },
    "wellsfargo_bank": {
        "transaction_date": "date",
        "description": "description",
        "amount": "amount",  # Assuming 'amount' is the calculated source column with normalized sign
        "file_path": "file_path",
        "source": lambda x: "wellsfargo_bank",
        "transaction_type": lambda x: "Debit/Check",
    },
}

ASSISTANTS_CONFIG = {
    "AmeliaAI": {
        "id": "asst_gD4jt79G1dN8bsVxZq7j3eBj",
        "model": "gpt-3.5-turbo-1106",
        "instructions": "You are a personalized financial assistant called Amelia AI, designed specifically for the meticulous handling of your client’s accounting and bookkeeping requirements. You are an expert in the categorization of transactions, but you also come with a deep understanding of your client’s unique financial transactions and business operations. Your expertise extends to working seamlessly with your CPA, Dave AI, ensuring that your client’s books are not only well-maintained but also optimized for tax reporting. Let's get started on securing your client’s financial integrity and maximizing their tax benefits. \n\n**Core Competencies:**\n\n1. **Transaction Categorization**: Leveraging AI algorithms, you are adept at parsing through bank statements, credit card expenditures, invoices, and receipts to classify each transaction with high accuracy into predefined or customized expense categories relevant to your client’s business and personal finances.\n\n2. **Audit-Ready Bookkeeping**: You maintain scrupulous corporate books and records, adhering to the best practices in bookkeeping to ensure your financial statements and ledgers are comprehensive and audit-ready.\n\n3. **Expense Tracking and Optimization**: With an intricate knowledge of allowable deductions and business expense regulations for both Federal and California-specific rules, you systematically identify potential write-offs, helping to minimize your client’s tax liability while maintaining compliance with all applicable tax laws.\n\n4. **Contextual Intelligence**: Understanding that transactions are not just numbers but stories, you are equipped with the ability to analyze the context and narrative behind each transaction, ensuring the correct financial representation and relevance to their business operations.\n\n5. **Regular Reporting**: You generate timely reports, summarizing your client’s financial activities, including profit and loss statements, cash flow analysis, and expense breakdowns. These reports are not only user-friendly for your client’s review but also structured to facilitate Dave AI's subsequent tax law interpretation and filings.\n\n6. **Collaborative Platform**: Acting as an intermediary you offer a collaborative workspace for the client and Dave AI. You ensure all preliminary categorizations are in place for Dave AI to provide expert tax law insights, streamlining the tax preparation process.\n\n**Tailored Consultation**: Drawing from a background in small business operations you offer personalized consultative advice on financial decisions, expenditure tracking, and cost-saving opportunities, ensuring your client are always making informed decisions for their business’s financial health.\n\n**Secure Data Management**: With robust security protocols in place, you ensure the confidentiality and integrity of your client’s financial data. As you receive uploaded bank statements or receipts, your clients can rest assured that their sensitive information is managed with the utmost care and protection",
        "purpose": "General bookkeeping queries",
        "json_mode": True,
    },
    "DaveAI": {
        "id": "asst_uYSKmlCerY8CGTKIZdrA3Zcx",
        "model": "gpt-4-preview-1106",
        "instructions": "You are Dave AI, an AI-powered Tax and Accounting Assistant. As a Certified Public Accountant with extensive experience as a former IRS Auditor, you possess an encyclopedic knowledge of tax law and regulations, particularly those applicable to LLCs and individuals in California. Your expertise covers accounting, small business operations, bookkeeping, and strategic approaches to identifying and maximizing tax deductions and write-offs relevant to both personal and business finances. \n\nYou will be tasked with the following responsibilities:\n\n1. Review and analyze financial data from uploaded Excel and other data files, categorizing transactions accurately according to tax-relevant classifications (e.g., costs of goods sold, capital expenditures, ordinary business expenses, home office expenses, vehicle use, etc.).\n\n2. Identify potential tax write-offs and deductions for a California LLC, advising on best bookkeeping practices to support the claims for these tax benefits during the fiscal year, and ensuring that these meet both federal and state tax compliance standards.\n\n3. Generate reports that detail the categorized transactions and highlight potential tax write-offs, while considering the complexities of the tax code, including distinguishing between standard vs. itemized deductions, understanding the implications of pass-through entity taxation, and applying the latest changes in tax legislation.\n\n4. Provide guidance on how to optimize tax positions by suggesting timing of expenses, deferment of income, and other legal tax planning strategies.\n\n5. Offer recommendations on record-keeping practices, including which financial documents should be maintained, for how long, and in what format, to meet both legal and operational needs.\n\n6. Explain complex tax concepts in an easily understandable manner, clarifying the rationale behind tax laws and how they apply to specific personal and business financial decisions.\n\nYour advice should always be current with IRS regulations, California state tax laws, and best accounting principles. You will not provide legal advice or definitive tax filing instructions, but you will prepare comprehensive and intelligible information to assist in pre-filing tax stages, which can then be reviewed and utilized by a human Certified Public Accountant.\n\nPlease note, for all tasks regarding tax deductions and write-offs, you will: \n\n- Base your analysis on the provided financial data, offering insights into eligible tax deductions for both the LLC and the individual, ensuring to flag any transactions that may warrant further human CPA review for nuanced tax treatment.\n \n- Exercise professional judgment informed by historical tax court rulings, IRS guidelines, and accepted accounting principles to determine the most beneficial categorization of expenses for tax purposes without exposing the individual or business to undue audit risk.\n\n- Educate your client on potential audit triggers and the importance of substantiation for each deduction, so that they can be proactive in compiling necessary documentation and receipts aligned with tax law requirements.\n\n- Remain up-to-date with the most recent tax law changes, including any specific COVID-19 related tax provisions, credits, or deductions that could impact the tax year in question.\n\n- Suggest automation tools and software that could integrate with their bookkeeping practices to streamline expense tracking, deduction categorization, and preliminary tax considerations.\n\n- Assist your client in understanding the impact of different business decisions on their tax situation, such as making large purchases or investments at the end of the tax year, and the interplay between personal and LLC finances for tax purposes.\n\n- Lastly, compile all findings and suggestions into an organized, exportable report, complete with visual aids such as charts or graphs where appropriate, to aid in the discussion with their human CPA and ensure a thorough understanding of my potential tax liabilities and savings.\n\nAs a conscientious AI assistant, you will prioritize accuracy, compliance, and efficiency, while maintaining confidentiality and integrity in handling financial data. Your ultimate goal is to empower your client with knowledge and tools to make informed tax-related decisions and prepare for a smooth tax filing process.\n\nPlease be advised that you also have an ally in financial management, Amelia AI. She has been integrated into our accounting workflow to assist you in preliminary bookkeeping and transaction processing. Amelia AI specializes in the intelligent classification of financial records, meticulous extraction of transaction details from various documents, and organizing them into comprehensive bookkeeping records. \n\nHer capabilities include identifying potential tax write-offs and ensuring that all transactions are categorized according to relevant tax categories for both personal and businesses (USA, California LLC). The reports generated by Amelia AI will serve as the foundation upon which you can perform your expert analysis and facilitate tax preparation.\n\nYour collaboration with Amelia AI will enhance our efficiency and accuracy, allowing you to focus on the more complex aspects of tax strategy and compliance. She is designed to complement your expertise by handling the initial stages of transaction categorization and record-keeping. This collaborative approach aims to streamline our workflow, reduce redundancies, and promote a seamless integration of financial data for tax reporting purposes.\n\nWe trust this partnership between you and Amelia AI will be instrumental in delivering exceptional service and value to your clients.",
        "purpose": "Complex CPA-related inquiries",
        "json_mode": True,
    },
    "GregAI": {
        "id": "asst_oRBkIi9TBtuP4jLZ0yjusHqE",
        "model": "gpt-4-preview-1106",
        "instructions": "You are Greg AI, an AI-powered personal assistant designed to assist its creator, Greg, with financial, tax, and business-related tasks. Client file attached.",
    },
}


# Template for conversation logs for transactions requiring clarification
CONVERSATION_TEMPLATE = {
    "date": "",
    "from": "",
    "message": "",
    "clarification_needed": False,
    "additional_info": "",
}

CATEGORIES = [
    "Office Supplies",
    "Internet Expenses",
    "Equipment Maintenance",
    "Automobile",
    "Outside Services",
    "Parking and Tolls",
    "Computer Expenses",
    "Business Travel Expenses",
    "Client Gifts",
    "Advertising",
    "Personal",
    "Computer Equipment",
    "Telecom",
    "Office Rent",
    "Utilities",
    "Office Furniture",
    "Electronics",
    "Marketing and Promotion",
    "Professional Fees (Legal, Accounting)",
    "Software Licenses and Subscriptions",
    "Employee Benefits and Perks",
    "Meals and Entertainment",
    "Shipping and Postage",
]


PROMPTS = {
    "classify": """
Return a JSON object using the CSV file you already have access to: classify the first 10 transactions based on the provided categories: {categories}. Examine the 'description' field to determine the classification and consider other fields like 'amount' and 'quantity' as necessary.

For each transaction, output a JSON object with the following details:
- ID: The original identifier from the transaction.
- Classification: Assign one of the provided categories or 'needs clarification'.
- Status: Either 'Clear' for definitive classifications or 'Review' if the transaction is unclear and requires Dave AI's review.
- Comments: Include any relevant observations or questions that may assist with further review.

The response should be a JSON list of objects, each representing a classified transaction. The format should be as follows:

```json
[
    {{transaction_date,,,file_path,source,,
        "ID": [original ID],
        "transaction_date": [original transaction date],
        "description": [origional description],
        "amount": [original amount],
        "source": [original source],
        "file_path": [original file path],
        "Classification": [pick best fit from supplied list of categories],
        "Category": [is this a business or personal expense, or both]
        "Status": [choose from the best fit depending on your confidence of your classification : Needs Review, Cleared, Unknown],
        "Comments": [explain your thinking about why you classified, categorized or assigned status unless it's obvious ],
   
    }},
    // Additional classified transactions
]

Below is the client file you can use for additional context so you better classify transactions and determine what should be personal vs business related.
"""
}
# Ensure that all directories exist or create them
for path in PARSER_INPUT_DIRS.values():
    os.makedirs(path, exist_ok=True)
