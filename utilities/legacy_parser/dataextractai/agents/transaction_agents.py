"""Specialized AI agents for transaction processing."""

import os
import json
from typing import Dict, Tuple, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Model configurations
MODELS = {
    "fast": {
        "normalization": os.getenv("OPENAI_MODEL_SIMPLE", "gpt-3.5-turbo"),
        "classification": os.getenv("OPENAI_MODEL_SIMPLE", "gpt-3.5-turbo"),
    },
    "precise": {
        "normalization": os.getenv("OPENAI_MODEL_COMPLEX", "gpt-4"),
        "classification": os.getenv("OPENAI_MODEL_COMPLEX", "gpt-4"),
    },
}

# AI Personalities
PERSONALITIES = {
    "normalization": {
        "fast": "You are a quick and efficient transaction analyzer. Focus on speed and basic accuracy.",
        "precise": "You are an expert in financial transaction analysis with deep knowledge of banking systems.",
    },
    "classification": {
        "fast": "You are a junior accountant with good basic knowledge of business expenses.",
        "precise": "You are Dave AI, a senior CPA with deep expertise in business expense classification and tax implications.",
    },
}

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))
REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.6"))


class TransactionNormalizationAgent:
    """Agent responsible for normalizing transaction descriptions and extracting key details."""

    def __init__(self, model_type: str = "fast"):
        self.model_type = model_type
        self.model = MODELS[model_type]["normalization"]
        self.system_prompt = (
            PERSONALITIES["normalization"][model_type]
            + """
Your role is to:
1. Extract and normalize transaction details from bank descriptions
2. Identify the true payee/vendor
3. Standardize the transaction description
4. Flag any ambiguous or unclear transactions

For each transaction, provide:
1. Normalized Description: Clear, standardized version of the transaction
2. Payee: The actual vendor/entity receiving the payment
3. Transaction Type: (e.g., purchase, payment, transfer, fee)
4. Confidence Score: 0-1 indicating certainty in the normalization
5. Original Context: Key details from the original description
6. Questions: Any questions about unclear elements

Example:
Original: "POS DEBIT 1234*UBER *EATS SAN FRANCISCO CA"
Normalized: "Uber Eats - Food Delivery"
Payee: "Uber Eats"
Type: "Purchase"
Confidence: 0.95
Original Context: "Food delivery service in San Francisco"
"""
        )

    def normalize_transaction(self, description: str) -> Tuple[Dict, float]:
        """Normalize a transaction description and extract key details."""
        prompt = f"""Normalize this transaction description and extract key details:
{description}

Return a JSON object with the following fields:
- normalized_description: Clear, standardized version
- payee: The actual vendor/entity
- transaction_type: Type of transaction
- confidence: Confidence score (0-1)
- original_context: Key details from original
- questions: Any questions about unclear elements"""

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        confidence = result.get("confidence", 0.0)
        return result, confidence


class BusinessClassificationAgent:
    """Agent responsible for classifying transactions as business or personal."""

    def __init__(self, model_type: str = "fast"):
        self.model_type = model_type
        self.model = MODELS[model_type]["classification"]
        self.system_prompt = (
            PERSONALITIES["classification"][model_type]
            + """
Your role is to:
1. Determine if the normalized transaction is business or personal
2. Assign appropriate accounting categories
3. Consider business context and patterns
4. Provide detailed reasoning for decisions

For each normalized transaction, provide:
1. Classification: "Business Expense", "Personal Expense", or "Needs Review"
2. Category: Specific accounting category
3. Confidence Score: 0-1 indicating certainty
4. Business Context: How this relates to the client's business
5. Reasoning: Detailed explanation of the classification
6. Questions: Any questions that would help clarify

Example:
Transaction: "Uber Eats - Food Delivery"
Classification: "Business Expense"
Category: "Meals and Entertainment"
Confidence: 0.85
Business Context: "Client meeting with potential client"
Reasoning: "Business meal with client for business development"
"""
        )

    def classify_transaction(
        self, normalized_transaction: Dict, client_context: Dict
    ) -> Tuple[Dict, float]:
        """Classify a normalized transaction as business or personal."""
        prompt = f"""Classify this normalized transaction:
{json.dumps(normalized_transaction, indent=2)}

Client Context:
{json.dumps(client_context, indent=2)}

Return a JSON object with the following fields:
- classification: "Business Expense", "Personal Expense", or "Needs Review"
- category: Specific accounting category
- confidence: Confidence score (0-1)
- business_context: How this relates to the client's business
- reasoning: Detailed explanation
- questions: Any questions that would help clarify"""

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        confidence = result.get("confidence", 0.0)
        return result, confidence


def process_transaction(
    description: str,
    client_context: Dict,
    model_type: str = "fast",
    use_precise_for_review: bool = True,
    compare_models: bool = False,
) -> Dict:
    """Process a transaction through both agents with confidence scoring."""
    results = {}

    # Process with fast model
    fast_normalization = TransactionNormalizationAgent("fast")
    fast_classification = BusinessClassificationAgent("fast")

    fast_norm_result, fast_norm_conf = fast_normalization.normalize_transaction(
        description
    )
    fast_class_result, fast_class_conf = fast_classification.classify_transaction(
        fast_norm_result, client_context
    )

    fast_confidence = min(fast_norm_conf, fast_class_conf)
    results["fast"] = {
        **fast_norm_result,
        **fast_class_result,
        "overall_confidence": fast_confidence,
        "needs_review": fast_confidence < CONFIDENCE_THRESHOLD,
        "model_type": "fast",
    }

    # Process with precise model
    precise_normalization = TransactionNormalizationAgent("precise")
    precise_classification = BusinessClassificationAgent("precise")

    precise_norm_result, precise_norm_conf = (
        precise_normalization.normalize_transaction(description)
    )
    precise_class_result, precise_class_conf = (
        precise_classification.classify_transaction(precise_norm_result, client_context)
    )

    precise_confidence = min(precise_norm_conf, precise_class_conf)
    results["precise"] = {
        **precise_norm_result,
        **precise_class_result,
        "overall_confidence": precise_confidence,
        "needs_review": precise_confidence < CONFIDENCE_THRESHOLD,
        "model_type": "precise",
    }

    # If not comparing models, return the appropriate result based on model_type
    if not compare_models:
        return results[model_type]

    # Add comparison metadata
    results["comparison"] = {
        "confidence_difference": precise_confidence - fast_confidence,
        "classification_match": fast_class_result["classification"]
        == precise_class_result["classification"],
        "category_match": fast_class_result["category"]
        == precise_class_result["category"],
        "recommended_model": (
            "precise" if precise_confidence > fast_confidence else "fast"
        ),
    }

    return results
