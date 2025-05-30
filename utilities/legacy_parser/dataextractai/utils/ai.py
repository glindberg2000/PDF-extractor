"""AI utilities for data extraction and processing."""

import os
import json
import yaml
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from .config import ASSISTANTS_CONFIG, PROMPTS, CATEGORIES, CLASSIFICATIONS

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Model configurations
MODEL_SIMPLE = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
MODEL_COMPLEX = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))

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


def get_assistant(assistant_name: str) -> Dict:
    """Get assistant configuration by name."""
    return ASSISTANTS_CONFIG.get(assistant_name)


def create_thread() -> str:
    """Create a new conversation thread."""
    thread = client.beta.threads.create()
    return thread.id


def add_message(thread_id: str, content: str) -> str:
    """Add a message to a thread."""
    message = client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=content
    )
    return message.id


def run_assistant(thread_id: str, assistant_name: str) -> str:
    """Run an assistant on a thread."""
    assistant = get_assistant(assistant_name)
    if not assistant:
        raise ValueError(f"Assistant {assistant_name} not found")

    run = client.beta.threads.runs.create(
        thread_id=thread_id, assistant_id=assistant["id"]
    )
    return run.id


def get_messages(thread_id: str) -> List[Dict]:
    """Get messages from a thread."""
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    return messages.data


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
    prompt = f"""Clean, standardize, and enhance the following business information:
    Business Type: {business_type}
    Industry: {industry}
    Description: {business_description}
    Typical Expenses: {', '.join(typical_expenses)}
    Business Activities: {', '.join(business_activities)}
    Employee Count: {employee_count}
    Annual Revenue: {annual_revenue}
    Location: {location}
    
    Rules:
    1. If any field contains phrases like "and also", "add", "include", or "plus", treat it as an addition to existing information
    2. Preserve existing information and append new items when requested
    3. Fix any typos or grammatical errors
    4. Use proper capitalization
    5. Standardize common business terms
    6. For activities and expenses:
       - Keep existing items
       - Add new items when requested
       - Remove duplicates
       - Sort alphabetically
       - Use consistent formatting
    7. Make it clear and professional
    
    Return a JSON object with the following fields:
    {{
        "business_type": "Standardized business type",
        "industry": "Standardized industry name",
        "business_description": "Enhanced business description",
        "typical_expenses": ["List of standardized expenses"],
        "business_activities": ["List of standardized activities"],
        "employee_count": "Standardized employee count",
        "annual_revenue": "Standardized revenue range",
        "location": "Standardized location"
    }}
    
    The response must be valid JSON only, with no additional text."""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business information standardization expert. Return only the cleaned value, no explanation or JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )

        enhanced_context = json.loads(response.choices[0].message.content)

        # Ensure we preserve existing data when no changes were requested
        if not business_type or business_type.lower() in ["n/a", "not set"]:
            enhanced_context["business_type"] = business_type
        if not industry or industry.lower() in ["n/a", "not set"]:
            enhanced_context["industry"] = industry
        if not business_activities:
            enhanced_context["business_activities"] = []
        if not typical_expenses:
            enhanced_context["typical_expenses"] = []

        return enhanced_context
    except Exception as e:
        print(f"Error enhancing business context: {e}")
        # Return original values if enhancement fails
        return {
            "business_type": business_type,
            "industry": industry,
            "business_description": business_description,
            "typical_expenses": typical_expenses,
            "business_activities": business_activities,
            "employee_count": employee_count,
            "annual_revenue": annual_revenue,
            "location": location,
        }


def categorize_transaction(
    description: str, categories: List[str], use_dave: bool = False
) -> Dict:
    """Categorize a transaction using AI."""
    assistant_name = "DaveAI" if use_dave else "AmeliaAI"
    assistant = get_assistant(assistant_name)
    thread_id = create_thread()

    prompt = PROMPTS["categorize_one"].format(categories=categories)
    add_message(thread_id, prompt + description)
    run_id = run_assistant(thread_id, assistant_name)

    messages = get_messages(thread_id)
    if messages and len(messages) > 0:
        return json.loads(messages[0].content[0].text.value)
    return {"category": "Uncategorized", "confidence": 0.0}


def review_transaction(transaction: Dict, context: Dict) -> Dict:
    """Review a transaction using AI."""
    assistant = get_assistant("AmeliaAI")
    thread_id = create_thread()

    prompt = f"""Please review this transaction:
    Description: {transaction['description']}
    Amount: ${transaction['amount']}
    Current Category: {transaction.get('category', 'Uncategorized')}
    Current Classification: {transaction.get('classification', 'Unclassified')}
    
    Business Context:
    Type: {context.get('business_type', 'Not specified')}
    Industry: {context.get('industry', 'Not specified')}
    Activities: {', '.join(context.get('business_activities', []))}
    Typical Expenses: {', '.join(context.get('typical_expenses', []))}
    
    Please provide:
    1. Correct category from: {', '.join(CATEGORIES)}
    2. Correct classification from: {', '.join(CLASSIFICATIONS)}
    3. Confidence level (0-1)
    4. Any relevant comments
    
    Return in JSON format."""

    add_message(thread_id, prompt)
    run_id = run_assistant(thread_id, "AmeliaAI")

    messages = get_messages(thread_id)
    if messages and len(messages) > 0:
        return json.loads(messages[0].content[0].text.value)
    return transaction


def enhance_business_profile(client_name: str) -> Dict:
    """Enhance business profile using AI."""
    assistant = get_assistant("AmeliaAI")
    thread_id = create_thread()

    prompt = f"""Please enhance the business profile for client: {client_name}
    
    Please provide enhanced values for:
    1. Business Type
    2. Industry
    3. Annual Revenue
    4. Number of Employees
    5. Location
    6. Fiscal Year End
    7. Business Activities
    8. Typical Expenses
    
    Return the enhanced profile in JSON format with the same structure as the input."""

    add_message(thread_id, prompt)
    run_id = run_assistant(thread_id, "AmeliaAI")

    messages = get_messages(thread_id)
    if messages and len(messages) > 0:
        return json.loads(messages[0].content[0].text.value)
    return {}


def get_payee(assistant_config: Dict, description: str) -> Tuple[Dict, float]:
    """Extract or infer the payee from the transaction description with confidence level."""
    prompt = f"""Determine by any means necessary, or extract or infer, the payee of the transaction and return a clean succinct vendor name whether is a company, person or city government agency, utility or other entity. Use your best judgement come up with the most logical and recognizable vendor name which can be used for general ledgers and tax forms purposes and return it in the object json key 'payee'. Also include a 'confidence' field with a value between 0 and 1 indicating your confidence in the payee identification. The transaction description is: {description}"""

    response = client.ChatCompletion.create(
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

    response = client.ChatCompletion.create(
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

    response = client.ChatCompletion.create(
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

    response = client.chat.completions.create(
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
            response = client.ChatCompletion.create(
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
        response = client.chat.completions.create(
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
