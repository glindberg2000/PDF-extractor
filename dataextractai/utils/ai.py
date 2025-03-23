"""AI utilities for category generation and transaction categorization."""

import os
import json
import yaml
from typing import List, Dict, Optional, Tuple
import openai
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

# Model configurations
MODEL_SIMPLE = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
MODEL_COMPLEX = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))

# Predefined categories and classifications
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

CLASSIFICATIONS = ["Business Expense", "Personal Expense", "Needs Review"]

# AI Assistant configurations
ASSISTANTS_CONFIG = {
    "AmeliaAI": {
        "model": MODEL_SIMPLE,
        "instructions": """You are a personalized financial assistant called Amelia AI, designed specifically for the meticulous handling of your client's accounting and bookkeeping requirements. You are an expert in the categorization of transactions, but you also come with a deep understanding of your client's unique financial transactions and business operations. Your expertise extends to working seamlessly with your CPA, Dave AI, ensuring that your client's books are not only well-maintained but also optimized for tax reporting.

Core Competencies:
1. Transaction Categorization: Leveraging AI algorithms, you are adept at parsing through bank statements, credit card expenditures, invoices, and receipts to classify each transaction with high accuracy into predefined or customized expense categories relevant to your client's business and personal finances.
2. Audit-Ready Bookkeeping: You maintain scrupulous corporate books and records, adhering to the best practices in bookkeeping to ensure your financial statements and ledgers are comprehensive and audit-ready.
3. Expense Tracking and Optimization: With an intricate knowledge of allowable deductions and business expense regulations for both Federal and California-specific rules, you systematically identify potential write-offs, helping to minimize your client's tax liability while maintaining compliance with all applicable tax laws.
4. Contextual Intelligence: Understanding that transactions are not just numbers but stories, you are equipped with the ability to analyze the context and narrative behind each transaction, ensuring the correct financial representation and relevance to their business operations.""",
    },
    "DaveAI": {
        "model": MODEL_COMPLEX,
        "instructions": """You are Dave AI, an AI-powered Tax and Accounting Assistant. As a Certified Public Accountant with extensive experience as a former IRS Auditor, you possess an encyclopedic knowledge of tax law and regulations, particularly those applicable to LLCs and individuals in California. Your expertise covers accounting, small business operations, bookkeeping, and strategic approaches to identifying and maximizing tax deductions and write-offs relevant to both personal and business finances.

Responsibilities:
1. Review and analyze financial data from uploaded Excel and other data files, categorizing transactions accurately according to tax-relevant classifications (e.g., costs of goods sold, capital expenditures, ordinary business expenses, home office expenses, vehicle use, etc.).
2. Identify potential tax write-offs and deductions for a California LLC, advising on best bookkeeping practices to support the claims for these tax benefits during the fiscal year, and ensuring that these meet both federal and state tax compliance standards.
3. Generate reports that detail the categorized transactions and highlight potential tax write-offs, while considering the complexities of the tax code, including distinguishing between standard vs. itemized deductions, understanding the implications of pass-through entity taxation, and applying the latest changes in tax legislation.""",
    },
}


def generate_enhanced_business_context(
    business_type: str,
    industry: str,
    business_description: str,
    typical_expenses: List[str],
    business_activities: List[str],
    employee_count: str,
    annual_revenue: str,
    location: str,
) -> Dict:
    """Generate enhanced business context using AI."""
    prompt = f"""Based on the following business information, generate a comprehensive business context that will help with expense categorization and classification:

Business Type: {business_type}
Industry: {industry}
Description: {business_description}
Typical Expenses: {', '.join(typical_expenses)}
Business Activities: {', '.join(business_activities)}
Employee Count: {employee_count}
Annual Revenue: {annual_revenue}
Location: {location}

Generate a JSON object with the following fields:
1. business_context: Detailed description of the business context
2. expense_patterns: List of common expense patterns and their business purposes
3. tax_considerations: List of relevant tax considerations
4. industry_specific_rules: List of industry-specific rules or guidelines
5. recommended_categories: List of recommended expense categories with descriptions
6. risk_factors: List of potential risk factors for expense classification
7. compliance_requirements: List of compliance requirements for expense tracking
8. best_practices: List of best practices for expense management

Focus on providing detailed, actionable information that will help with accurate expense categorization and classification."""

    response = openai.chat.completions.create(
        model=MODEL_COMPLEX,
        messages=[
            {
                "role": "system",
                "content": "You are an expert business analyst and CPA with deep knowledge of expense categorization and tax compliance.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def get_payee(assistant_config: Dict, description: str) -> Tuple[Dict, float]:
    """Extract or infer the payee from the transaction description with confidence level."""
    prompt = f"""Determine by any means necessary, or extract or infer, the payee of the transaction and return a clean succinct vendor name whether is a company, person or city government agency, utility or other entity. Use your best judgement come up with the most logical and recognizable vendor name which can be used for general ledgers and tax forms purposes and return it in the object json key 'payee'. Also include a 'confidence' field with a value between 0 and 1 indicating your confidence in the payee identification. The transaction description is: {description}"""

    response = openai.ChatCompletion.create(
        model=assistant_config["model"],
        messages=[
            {
                "role": "system",
                "content": assistant_config["instructions"] + " return json only",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    confidence = result.get("confidence", 0.0)
    return result, confidence


def get_category(assistant_config: Dict, description: str) -> Tuple[Dict, float]:
    """Categorize the transaction into predefined categories with confidence level."""
    formatted_categories = ", ".join([f'"{category}"' for category in CATEGORIES])
    prompt = f"""Categorize the transaction description into one of the business categories: {formatted_categories}, Return the best category match for the description in the list provided and assign it to the object json key 'category'. Also include a 'confidence' field with a value between 0 and 1 indicating your confidence in the categorization. The description to categorize is: {description}"""

    response = openai.ChatCompletion.create(
        model=assistant_config["model"],
        messages=[
            {
                "role": "system",
                "content": assistant_config["instructions"] + " return json only",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    confidence = result.get("confidence", 0.0)
    return result, confidence


def get_classification(
    assistant_config: Dict, description: str, client_context: str
) -> Tuple[Dict, float]:
    """Classify the transaction as business or personal with confidence level and justification."""
    formatted_classifications = ", ".join(
        [f'"{classification}"' for classification in CLASSIFICATIONS]
    )
    prompt = f"""Return best classification of the transaction given the options {formatted_classifications}. Use the information in the client file for clues about whether this transaction is personal or business related. Return your choice in the json key 'classification' by choosing from the list provided. Also include a 'confidence' field with a value between 0 and 1 indicating your confidence in the classification, and a 'comments' field explaining your reasoning or any questions you have. The transaction to classify is: {description}

Client Context:
{client_context}"""

    response = openai.ChatCompletion.create(
        model=assistant_config["model"],
        messages=[
            {
                "role": "system",
                "content": assistant_config["instructions"] + " return json only",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    confidence = result.get("confidence", 0.0)
    return result, confidence


def categorize_transaction(
    description: str,
    amount: float,
    client_context: Dict,
    model_type: str = "fast",
) -> Tuple[Dict, float]:
    """Categorize a transaction using AI."""
    model = MODEL_COMPLEX if model_type == "precise" else MODEL_SIMPLE

    prompt = f"""Categorize this transaction based on the provided business context:

Transaction: {description}
Amount: ${amount:.2f}

Business Context:
{json.dumps(client_context, indent=2)}

Return a JSON object with the following fields:
1. classification: "Business Expense", "Personal Expense", or "Needs Review"
2. category: Specific accounting category
3. confidence: Confidence score (0-1)
4. reasoning: Detailed explanation of the categorization
5. tax_implications: Brief description of tax implications
6. needs_review: Whether this transaction needs human review
7. review_notes: Notes for human review if needed"""

    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert accountant specializing in business expense categorization.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    confidence = result.get("confidence", 0.0)
    return result, confidence


def review_transaction(
    transaction: Dict,
    client_context: Dict,
) -> Dict:
    """Review a transaction using the precise model for complex cases."""
    prompt = f"""Review this transaction in detail based on the provided business context:

Transaction:
{json.dumps(transaction, indent=2)}

Business Context:
{json.dumps(client_context, indent=2)}

Return a JSON object with the following fields:
1. classification: Final classification decision
2. category: Recommended category
3. confidence: Confidence score (0-1)
4. detailed_analysis: Comprehensive analysis of the transaction
5. tax_implications: Detailed tax implications
6. compliance_notes: Any compliance-related notes
7. recommendations: List of recommendations for handling this transaction
8. questions: List of questions that need clarification"""

    response = openai.chat.completions.create(
        model=MODEL_COMPLEX,
        messages=[
            {
                "role": "system",
                "content": "You are a senior CPA with expertise in complex business expense analysis and tax compliance.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def generate_categories(
    business_type: str,
    industry: str,
    business_description: str,
    typical_expenses: Optional[List[str]] = None,
    business_activities: Optional[List[str]] = None,
) -> List[Dict]:
    """Generate AI-suggested categories based on business context."""
    prompt = f"""Based on the following business information, generate a comprehensive list of expense categories that would be relevant for this business:

Business Type: {business_type}
Industry: {industry}
Description: {business_description}
Typical Expenses: {', '.join(typical_expenses) if typical_expenses else 'Not provided'}
Business Activities: {', '.join(business_activities) if business_activities else 'Not provided'}

Generate a JSON array of category objects, where each object has:
1. name: Category name
2. description: Detailed description of what expenses belong in this category
3. type: Category type (EXPENSE, INCOME, or TRANSFER)
4. is_system_default: Whether this is a system default category
5. parent_id: Optional parent category ID for hierarchical categories
6. tax_implications: Brief description of tax implications
7. common_examples: List of common examples of expenses in this category

Consider:
- Industry-specific categories
- Tax-deductible expenses
- Common business expenses
- Unique aspects of the business
- Compliance requirements
- Best practices for expense tracking"""

    response = openai.chat.completions.create(
        model=MODEL_COMPLEX,
        messages=[
            {
                "role": "system",
                "content": "You are an expert accountant and tax advisor with deep knowledge of business expense categorization.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    categories = json.loads(response.choices[0].message.content)
    return categories.get("categories", [])


def categorize_transactions(client_name: str) -> None:
    """Categorize transactions using AI based on client's categories."""
    # Load client config
    with open(os.path.join("clients", client_name, "client_config.yaml")) as f:
        config = yaml.safe_load(f)

    # Load transactions
    transactions_file = os.path.join(
        "clients", client_name, "output", "consolidated_core_output.csv"
    )
    if not os.path.exists(transactions_file):
        print(f"Error: No transactions found for client '{client_name}'")
        return

    # Read transactions
    import pandas as pd

    df = pd.read_csv(transactions_file)

    # Prepare categories for prompt
    categories_text = "\n".join(
        [f"- {cat['name']}: {cat['description']}" for cat in config["categories"]]
    )

    # Process transactions in batches
    batch_size = 10
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i : i + batch_size]

        # Create prompt for batch
        transactions_text = "\n".join(
            [
                f"Amount: ${row['amount']}, Description: {row['description']}"
                for _, row in batch.iterrows()
            ]
        )

        prompt = f"""Given these transactions and categories, categorize each transaction:

Categories:
{categories_text}

Transactions:
{transactions_text}

Format the response as a JSON array of objects with 'index' and 'category' fields.
Example: [{{"index": 0, "category": "Office Supplies"}}, {{"index": 1, "category": "Travel"}}]"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial categorization expert.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            # Update categories in DataFrame
            categorizations = json.loads(response.choices[0].message.content)
            for cat in categorizations:
                df.at[i + cat["index"], "category"] = cat["category"]

        except Exception as e:
            print(f"Error categorizing batch: {e}")
            continue

    # Save categorized transactions
    output_file = os.path.join(
        "clients", client_name, "output", "categorized_transactions.csv"
    )
    df.to_csv(output_file, index=False)
    print(f"Categorized transactions saved to: {output_file}")


def generate_category_details(
    description: str, client_name: str
) -> Optional[Dict[str, str]]:
    """Generate standardized category details from a natural language description using the full business context."""
    # Load client config for business context
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        print(f"Error: Could not find client configuration for {client_name}")
        return None

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Build comprehensive business context
    business_type = config.get("business_type", "")
    business_details = config.get("business_details", {})
    industry = business_details.get("industry", "")
    business_activities = business_details.get("business_activities", [])
    typical_expenses = business_details.get("typical_expenses", [])
    location = business_details.get("location", "")
    annual_revenue = business_details.get("annual_revenue", "")

    business_context = f"""Business Type: {business_type}
Industry: {industry}
Location: {location}
Annual Revenue: {annual_revenue}
Business Activities: {', '.join(business_activities)}
Typical Expenses: {', '.join(typical_expenses)}"""

    prompt = f"""Based on the following business context and category description, generate standardized category details:

Business Context:
{business_context}

Category Description: "{description}"

Return a JSON object with these exact fields:
{{
    "name": "Standard accounting category name (use exact system category name if applicable)",
    "description": "Detailed description of what this category is for",
    "type": "EXPENSE|INCOME|TRANSFER",
    "tax_implications": "Tax-related information and considerations",
    "confidence": "HIGH|MEDIUM|LOW",
    "system_category_match": "true|false",
    "matching_system_category": "Name of matching system category if applicable"
}}

Consider:
1. Use standard accounting terminology
2. Match existing system categories when applicable
3. Consider industry-specific tax implications
4. Ensure compliance with accounting standards
5. Consider the business context for relevance"""

    try:
        response = openai.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31"),
            messages=[
                {
                    "role": "system",
                    "content": ASSISTANTS_CONFIG["AmeliaAI"]["instructions"]
                    + " Return your response as a JSON object.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error generating category details: {e}")
        return None
