# test_structured_output.py
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()


def test_structured_output():
    """
    Test structured output with JSON schema enforcement.
    """
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL_FAST"),
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a transaction classification assistant. Your task is to:\n"
                        "1. Analyze the transaction description\n"
                        "2. Identify the vendor/payee\n"
                        "3. Classify the transaction type\n"
                        "4. Provide reasoning for your classification"
                    ),
                },
                {
                    "role": "user",
                    "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM",
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "transaction_classification",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "payee": {"type": "string"},
                            "transaction_type": {
                                "type": "string",
                                "enum": [
                                    "purchase",
                                    "payment",
                                    "transfer",
                                    "fee",
                                    "subscription",
                                    "service",
                                ],
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "reasoning": {"type": "string"},
                            "needs_search": {"type": "boolean"},
                        },
                        "required": [
                            "payee",
                            "transaction_type",
                            "confidence",
                            "reasoning",
                            "needs_search",
                        ],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
        )

        print("\nRaw Response:")
        print(response.output_text)

    except Exception as e:
        print(f"\nError during test: {str(e)}")
        raise


if __name__ == "__main__":
    test_structured_output()
