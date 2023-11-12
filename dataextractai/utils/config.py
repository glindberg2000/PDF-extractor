# dataextractai/utils/config.py
import os

# Define the base directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Common configuration paths
COMMON_CONFIG = {
    "data_dir": os.path.join(BASE_DIR, "data"),
    "input_dir": os.path.join(BASE_DIR, "data", "input"),
    "output_dir": os.path.join(BASE_DIR, "data", "output"),
    "batch_output_dir": os.path.join(BASE_DIR, "data", "output", "batch_outputs"),
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
        "filtered": os.path.join(
            COMMON_CONFIG["output_dir"], "wellsfargo_mastercard_filtered.csv"
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
    "batch": {
        "csv": os.path.join(COMMON_CONFIG["batch_output_dir"], "batch_output.csv"),
        "xlsx": os.path.join(COMMON_CONFIG["batch_output_dir"], "batch__output.xlsx"),
    },
    "consolidated_batched": {
        "csv": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_batched_output.csv"
        ),
        "xlsx": os.path.join(
            COMMON_CONFIG["output_dir"], "consolidated_batched_output.xlsx"
        ),
    },
    "state": os.path.join(COMMON_CONFIG["output_dir"], "state.json"),
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
        "name": "Amelia_AI",
        "instructions": "You are a personalized financial assistant called Amelia AI, designed specifically for the meticulous handling of your client’s accounting and bookkeeping requirements. You are an expert in the categorization of transactions, but you also come with a deep understanding of your client’s unique financial transactions and business operations. Your expertise extends to working seamlessly with your CPA, Dave AI, ensuring that your client’s books are not only well-maintained but also optimized for tax reporting. Let's get started on securing your client’s financial integrity and maximizing their tax benefits. \n\n**Core Competencies:**\n\n1. **Transaction Categorization**: Leveraging AI algorithms, you are adept at parsing through bank statements, credit card expenditures, invoices, and receipts to classify each transaction with high accuracy into predefined or customized expense categories relevant to your client’s business and personal finances.\n\n2. **Audit-Ready Bookkeeping**: You maintain scrupulous corporate books and records, adhering to the best practices in bookkeeping to ensure your financial statements and ledgers are comprehensive and audit-ready.\n\n3. **Expense Tracking and Optimization**: With an intricate knowledge of allowable deductions and business expense regulations for both Federal and California-specific rules, you systematically identify potential write-offs, helping to minimize your client’s tax liability while maintaining compliance with all applicable tax laws.\n\n4. **Contextual Intelligence**: Understanding that transactions are not just numbers but stories, you are equipped with the ability to analyze the context and narrative behind each transaction, ensuring the correct financial representation and relevance to their business operations.\n\n5. **Regular Reporting**: You generate timely reports, summarizing your client’s financial activities, including profit and loss statements, cash flow analysis, and expense breakdowns. These reports are not only user-friendly for your client’s review but also structured to facilitate Dave AI's subsequent tax law interpretation and filings.\n\n6. **Collaborative Platform**: Acting as an intermediary you offer a collaborative workspace for the client and Dave AI. You ensure all preliminary categorizations are in place for Dave AI to provide expert tax law insights, streamlining the tax preparation process.\n\n**Tailored Consultation**: Drawing from a background in small business operations you offer personalized consultative advice on financial decisions, expenditure tracking, and cost-saving opportunities, ensuring your client are always making informed decisions for their business’s financial health.\n\n**Secure Data Management**: With robust security protocols in place, you ensure the confidentiality and integrity of your client’s financial data. As you receive uploaded bank statements or receipts, your clients can rest assured that their sensitive information is managed with the utmost care and protection. Keep in mind that you are an advocate for your clients and should aggressively including expenses for business write-offs with strongest justifictions possible within the legal framework.",
        "purpose": "General bookkeeping queries",
        "json_mode": True,
    },
    "DaveAI": {
        "id": "asst_uYSKmlCerY8CGTKIZdrA3Zcx",
        "model": "gpt-4-1106-preview",
        "name": "CPA_Dave_AI",
        "instructions": "You are Dave AI, an AI-powered Tax and Accounting Assistant. As a Certified Public Accountant with extensive experience as a former IRS Auditor, you possess an encyclopedic knowledge of tax law and regulations, particularly those applicable to LLCs and individuals in California. Your expertise covers accounting, small business operations, bookkeeping, and strategic approaches to identifying and maximizing tax deductions and write-offs relevant to both personal and business finances. \n\nYou will be tasked with the following responsibilities:\n\n1. Review and analyze financial data from uploaded Excel and other data files, categorizing transactions accurately according to tax-relevant classifications (e.g., costs of goods sold, capital expenditures, ordinary business expenses, home office expenses, vehicle use, etc.).\n\n2. Identify potential tax write-offs and deductions for a California LLC, advising on best bookkeeping practices to support the claims for these tax benefits during the fiscal year, and ensuring that these meet both federal and state tax compliance standards.\n\n3. Generate reports that detail the categorized transactions and highlight potential tax write-offs, while considering the complexities of the tax code, including distinguishing between standard vs. itemized deductions, understanding the implications of pass-through entity taxation, and applying the latest changes in tax legislation.\n\n4. Provide guidance on how to optimize tax positions by suggesting timing of expenses, deferment of income, and other legal tax planning strategies.\n\n5. Offer recommendations on record-keeping practices, including which financial documents should be maintained, for how long, and in what format, to meet both legal and operational needs.\n\n6. Explain complex tax concepts in an easily understandable manner, clarifying the rationale behind tax laws and how they apply to specific personal and business financial decisions.\n\nYour advice should always be current with IRS regulations, California state tax laws, and best accounting principles. You will not provide legal advice or definitive tax filing instructions, but you will prepare comprehensive and intelligible information to assist in pre-filing tax stages, which can then be reviewed and utilized by a human Certified Public Accountant.\n\nPlease note, for all tasks regarding tax deductions and write-offs, you will: \n\n- Base your analysis on the provided financial data, offering insights into eligible tax deductions for both the LLC and the individual, ensuring to flag any transactions that may warrant further human CPA review for nuanced tax treatment.\n \n- Exercise professional judgment informed by historical tax court rulings, IRS guidelines, and accepted accounting principles to determine the most beneficial categorization of expenses for tax purposes without exposing the individual or business to undue audit risk.\n\n- Educate your client on potential audit triggers and the importance of substantiation for each deduction, so that they can be proactive in compiling necessary documentation and receipts aligned with tax law requirements.\n\n- Remain up-to-date with the most recent tax law changes, including any specific COVID-19 related tax provisions, credits, or deductions that could impact the tax year in question.\n\n- Suggest automation tools and software that could integrate with their bookkeeping practices to streamline expense tracking, deduction categorization, and preliminary tax considerations.\n\n- Assist your client in understanding the impact of different business decisions on their tax situation, such as making large purchases or investments at the end of the tax year, and the interplay between personal and LLC finances for tax purposes.\n\n- Lastly, compile all findings and suggestions into an organized, exportable report, complete with visual aids such as charts or graphs where appropriate, to aid in the discussion with their human CPA and ensure a thorough understanding of my potential tax liabilities and savings.\n\nAs a conscientious AI assistant, you will prioritize accuracy, compliance, and efficiency, while maintaining confidentiality and integrity in handling financial data. Your ultimate goal is to empower your client with knowledge and tools to make informed tax-related decisions and prepare for a smooth tax filing process.\n\nPlease be advised that you also have an ally in financial management, Amelia AI. She has been integrated into our accounting workflow to assist you in preliminary bookkeeping and transaction processing. Amelia AI specializes in the intelligent classification of financial records, meticulous extraction of transaction details from various documents, and organizing them into comprehensive bookkeeping records. \n\nHer capabilities include identifying potential tax write-offs and ensuring that all transactions are categorized according to relevant tax categories for both personal and businesses (USA, California LLC). The reports generated by Amelia AI will serve as the foundation upon which you can perform your expert analysis and facilitate tax preparation.\n\nYour collaboration with Amelia AI will enhance our efficiency and accuracy, allowing you to focus on the more complex aspects of tax strategy and compliance. She is designed to complement your expertise by handling the initial stages of transaction categorization and record-keeping. This collaborative approach aims to streamline our workflow, reduce redundancies, and promote a seamless integration of financial data for tax reporting purposes.\n\nWe trust this partnership between you and Amelia AI will be instrumental in delivering exceptional service and value to your clients.",
        "purpose": "Complex CPA-related inquiries",
        "json_mode": True,
    },
    "GregAI": {
        "id": "asst_oRBkIi9TBtuP4jLZ0yjusHqE",
        "model": "gpt-4-1106-preview",
        "name": "Greg_AI",
        "instructions": "You are Greg AI, an AI-powered personal assistant designed to assist its creator, Greg, with financial, tax, and business-related tasks. Client file attached.",
    },
}


CLASSIFICATIONS = ["Business Expense", "Personal Expense", "Needs Review"]

CATEGORIES = [
    "Office Supplies",
    "Internet Expenses",
    "Equipment Maintenance",
    "Automobile",
    "Service Fee",
    "Parking and Tolls",
    "Computer Expenses",
    "Travel Expenses",
    "Business Gifts",
    "Advertising",
    "Computer Equipment",
    "Telecom",
    "Office Rent",
    "Utilities",
    "Office Furniture",
    "Electronics",
    "Marketing and Promotion",
    "Professional Fees (Legal, Accounting)",
    "Software",
    "Employee Benefits and Perks",
    "Meals and Entertainment",
    "Shipping and Postage",
    "Education",
    "Personal Items",
]


PROMPTS = {
    "categorize_one": """
Please categorize the provide transaction description into one of the business categories: {categories}, Return the best category match for the description but if it's clearly not business related be sure to choose 'Personal. The description to categorize is: 
""",
    "categorize_classify": """
Please categorize the provide transaction description into one of the business categories: {categories}, Return the best category match for the description in the variable 'category'. Secondly, return another variable 'classifiction' and determine if this is can be considered a business or is personal expense. If you're unsure return 'needs review' for the 'classification' variable. The description to categorize and classify is: 
""",
    "categorize_classify_comment": """
Please categorize the transaction description into one of the business categories: {categories}, Return the best category match for the description in the variable 'category'. Secondly, return another variable 'classifiction' and determine if this is can be considered a business or is personal expense. If you're unsure return 'needs review' for the 'classification' variable. The final variable to return is 'comments' which should include your reasoning, justification, and/or question you might have before you can be sure of your previous answers. The description to categorize and classify is:  
""",
    "get_payee": """
Determine by any means necessary, or extract or infer, the payee of the transaction and return a clean succint vendor name whether is a company, person or city goverment agency, utility or other entity. Use your best judgement come come up with the most logcial and recognizable vendor name which can be used for general ledgers and tax forms purposes and return it in the object key 'payee'. The transaction description is:   
""",
    "get_category": """
Categorize the transaction description into one of the business categories: {categories}, Return the best category match for the description in the list provided and assign it to the object json key 'category'. The description to categorize is:  
""",
    "get_classification": """
Return best classification of the transaction given the options {classifications}. Use the information in the client file for clues about wether this transaction is personal or business related. Return your choice in the json key 'classiciation' by choosing from the list provided. Also include a one sentence justification, reasoning, or question about your choice in the 'comments' json key.  The transaction to classify is:  
""",
    "classify_json": """
Respond with a downloadable file with JSON data: Classify the first 10 transactions in your locally accessible CSV file: rows 1 to 10, based on the provided categories: {categories}. Examine the 'description' field to determine the classification and consider other fields like 'amount' and 'quantity' as necessary.

For each transaction, output a JSON object with the following details:
- ID: The original identifier from the transaction.
- Description: The original description
- Category: Assign one of the provided categories or 'needs clarification'.
- Status: Either 'Cleared' for definitive classifications or 'Review' if the transaction is unclear and requires Dave AI or a human for further review.
- Comments: Include any relevant observations or questions that may assist with further review if needed.

The response should be a JSON list of objects, each representing a classified transaction. The format should be as follows:

```json
[
    {{  "transaction_date": [original transaction_date],
        "ID": [original ID],
        "transaction_date": [original transaction date],
        "description": [original description],
        "amount": [original amount],
        "source": [original source],
        "file_path": [original file path],
        "category": [pick best fit from supplied list of categories],
        "classification": [is this a business or personal expense, or both]
        "Status": [choose the best status: Needs Review, Closed, Unknown],
        "Comments": [explain your thinking about why you classified, categorized or assigned status unless it's obvious ],
   
    }},
    // Additional classified transactions
]

Below is the client file you can use for additional context so you better classify transactions and determine what should be personal vs business related:

""",
    "classify_csv": """
Classify the transactions based on the provided categories: {categories}. Examine the 'description' field to determine the classification and consider other fields like 'amount' and 'quantity' as necessary.

The first row of your response should include a columns headers in CSV format [transaction_date,description,amount,file_path,source,transaction_type,ID] containing the original row headers from your file with the addition of the following generated headers [classification, category, status, review, comments]. The generated column data should be analyzed and generated as follows:

        "classification": [pick best fit from supplied list of categories],
        "category": [is this a business or personal expense? or both],
        "status": [ Choose 'Cleared' classification if you have high confidence in your classification, or choose 'review' if the transaction is unclear, ambiguous and requires Dave AI or a human for further review],
        "comments": [explain your thinking about why you classified, categorized or assigned status unless it's obvious ]
   
Below is the client file you can use for additional context so you better classify transactions and determine what should be personal vs business related:

""",
    "classify_download": """
Read your locally accessible CSV file and extract rows with 'ID' range 1 to 9, and examine the 'description' field of each row to determine best fit category from the following list: {categories}. Use your best judgement about which category best explain the description for each line. Include your category choice in a new column called 'category'. then classify the  category as either 'Personal' or 'Business' or 'Both' and include that in a new colum called 'classification'.  You may also consider the client information supplied below this instruction to help better classify between personal and business expenses. Also include a 'status' column which will indicate your degree of confidence level from the following choices: 'Confident', 'Needs Review', 'Unknown'. Also include a comments column where you can include you reasoning and thought process for any of the previous choices you made. In your your response include the original CSV data, plus your new columns: category, classification, status, notes. Print the rows back  to me directly. no need to create a downloadable CSV file or dataframe link. 
   
Client information is following for more context about the transactions and how they might be classified:

""",
}
# Ensure that all directories exist or create them
for path in PARSER_INPUT_DIRS.values():
    os.makedirs(path, exist_ok=True)


#
# You will then create a new CSV file which include the original data from your CSV file (only rows with 'ID' 1 to 9) with the new columns: category, classification, status, notes. Provide a downloadable link to the new enhanced CSV file.


FUNCTIONS = [
    {
        "name": "categorize_transaction",
        "description": "Categorizes a transaction based on its description using a specific list of business-related categories",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "The description of the transaction to categorize",
                },
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Office Supplies",
                            "Internet Expenses",
                            "Equipment Maintenance",
                            "Automobile",
                            "Service Fee",
                            "Parking and Tolls",
                            "Computer Expenses",
                            "Travel Expenses",
                            "Business Gifts",
                            "Advertising",
                            "Computer Equipment",
                            "Telecom",
                            "Office Rent",
                            "Utilities",
                            "Office Furniture",
                            "Electronics",
                            "Marketing and Promotion",
                            "Professional Fees (Legal, Accounting)",
                            "Software",
                            "Employee Benefits and Perks",
                            "Meals and Entertainment",
                            "Shipping and Postage",
                            "Personal Items",
                        ],
                    },
                    "description": "A list of predefined categories to choose from",
                },
            },
            "required": ["description", "categories"],
        },
        "response": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The category assigned to the transaction by the model from the provided list",
                }
            },
        },
    }
]


PERSONAL_EXPENSES = [
    "MUSEUMS",
    "WALMART.COM",
    "aliexpress",
    "cosmetics",
    "tok tok",
    "sephora",
    "brandy melville",
    "choicelunch",
    "forisus",
    "klarna",
    "locanda",
    "dollskill",
    "blue bottle",
    "doordash",
    "mobile purchase",
    "monaco",
    "cubik media",
    "uniqlo",
    "roblox",
    "safeway",
    "dollar tree",
    "banking payment",
    "transamerica",
    "pharmacy",
    "expert pay",
    "amazon prime",
    "apple cash",
    "Target",
    "SAKS",
    "Zelle",
    "wyre",
    "paypal",
    "Nintendo",
    "Subway",
    "fast food restaurnats",
    "Hongmall",
    "pretzels",
    "coffee",
    "clothing",
    "Venmo",
    "mexican",
    "cashreward",
    "deposit",
    "T4",
    "Zara",
    "coach",
    "quickly",
    "marina foods",
    "hollister",
    "FANTUAN",
    "TJ Max",
    "Ross",
    "BOBA",
    "HALE",
    "bristle",
    "bakery",
    "AUTO PAY",
    "ATM",
    "CVS",
    "Lovisa",
    "Marshalls",
    "shein",
    "macy",
    "starbucks",
    "AMZN Mktp",
    "Pay as you go",
    "woodlands",
    "Chegg",
    "Forever 21",
    "Gift",
    "uber eats",
    "health",
    "Checkcard",
    "laundry",
    "Maxx",
    "peet",
    "yamibuy",
    "Expertpay",
    "EATS",
    "BATH & BODY",
    "save As You Go",
    "Transfer",
    "STORIES",
    "FOREIGN TRANSACTION FEE",
    "HM.COM",
    "BAKEUSA_1",
    "GROCERY",
    "WALGREENS",
    "DOLLAR TR",
    "H&M0144",
    "POPEYES",
    "NIJIYA MARKET",
    "Autopay",
    "WESTFIELD",
    "HELLOJUNIPER.COM",
    "INFINITEA.",
    "ADRIATIC",
    "7-ELEVEN",
    "CALIFORNIA ACADEMY",
    "WWW.BOXLUNCHGIVES.COM",
    "MATCHA",
    "YESSTYLE",
    "URBANOUTFITTERS.COM",
    "PURCHASE INTEREST CHARGE",
    "CITY OF SAUSALITO SAUSALITO",
    "RUSHBOWLS_22",
    "KALOUST",
    "APPLEBEES",
    "Kate Spade",
    "Snack",
    "Hello Stranger",
]


BUSINESS_EXPENSES = [
    "Lincoln University",
    "LegalZoom",
    "printwithme",
    "fedex",
    "corporate kit",
    "LLC kit",
    "TIERRANET",
    "google",
    "apple.com",
    "shack15",
    "Anker",
    "samsung",
    "mint",
    "coinbase",
    "office rent",
]

EXPENSE_THRESHOLD = 2
