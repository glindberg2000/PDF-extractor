from openai import OpenAI
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()

# Define the Brave Search tool that the LLM can call
brave_search_tool = {
    "type": "function",
    "function": {
        "name": "brave_search",
        "description": (
            "Brave Search API Integration for Vendor Information Lookup.\n\n"
            "This tool uses the Brave Search API to look up vendor information based on a vendor name. "
            "It returns structured information (e.g., business title, URL, description, and relevance score)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up vendor information.",
                }
            },
            "required": ["query"],
        },
    },
}


def lookup_vendor_info(query):
    """
    Mock function to simulate Brave Search API call.
    In a real implementation, this would make an actual API call.
    """
    # Simulate API response with unique, detailed data
    return {
        "title": "Lowe's Home Improvement #1636",
        "url": "https://www.lowes.com/store/NM-Albuquerque/1636",
        "description": "Lowe's #1636 is a home improvement superstore located in Albuquerque, NM. This location specializes in home improvement products, appliances, tools, paint, and garden supplies. It's known for its extensive selection of building materials and home decor items.",
        "location": {
            "address": "1234 Home Improvement Way",
            "city": "Albuquerque",
            "state": "NM",
            "zip": "87101",
        },
        "store_details": {
            "store_number": "1636",
            "square_footage": "120,000",
            "opening_date": "2005-03-15",
            "special_features": ["Garden Center", "Pro Services Desk", "Lumber Yard"],
        },
        "business_hours": {
            "monday": "6:00 AM - 10:00 PM",
            "tuesday": "6:00 AM - 10:00 PM",
            "wednesday": "6:00 AM - 10:00 PM",
            "thursday": "6:00 AM - 10:00 PM",
            "friday": "6:00 AM - 10:00 PM",
            "saturday": "6:00 AM - 10:00 PM",
            "sunday": "7:00 AM - 9:00 PM",
        },
        "relevance_score": 0.98,
        "last_updated": "2024-03-20T14:30:00Z",
        "additional_info": {
            "services": ["Delivery", "Installation", "Rental", "Design Services"],
            "payment_methods": ["Credit Cards", "Lowe's Credit Card", "Cash", "Check"],
            "special_programs": [
                "Military Discount",
                "Pro Rewards",
                "Project Calculator",
            ],
        },
    }


def test_structured_output_with_tools():
    """
    Test structured output with JSON schema enforcement and tool usage.
    Demonstrates proper function call handling and feeding tool results back to the LLM.
    """
    try:
        # Step 1: Initial API call with tool definitions
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_FAST"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a transaction classification assistant. Your tasks are to:\n"
                        "1. Analyze the transaction description.\n"
                        "2. Identify the vendor/payee and classify the transaction type.\n"
                        "3. ALWAYS look up additional vendor information using the provided 'brave_search' tool to enhance your analysis.\n"
                        "4. Use the additional context to provide a more accurate classification.\n"
                        "5. Provide detailed reasoning that includes information obtained from the search tool.\n\n"
                        "IMPORTANT: Return a JSON object with EXACTLY these field names:\n"
                        "{\n"
                        "    'payee': 'string - The identified payee/merchant name',\n"
                        "    'transaction_type': 'string - Must be one of: purchase, payment, transfer, fee, subscription, service',\n"
                        '    \'confidence\': \'string - Must be exactly "high", "medium", or "low"\',\n'
                        "    'reasoning': 'string - Explanation of the classification (include vendor details from the search if applicable)',\n"
                        "    'needs_search': 'boolean - ALWAYS set this to true'\n"
                        "}"
                    ),
                },
                {
                    "role": "user",
                    "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM",
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
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
                },
            },
            tools=[brave_search_tool],
            max_tokens=150,
            temperature=0.7,
        )

        # Step 2: Check for function call
        message = response.choices[0].message
        if message.tool_calls:
            # Step 3: Execute the function
            tool_call = message.tool_calls[0]
            if tool_call.function.name == "brave_search":
                # Parse arguments
                arguments = json.loads(tool_call.function.arguments)
                # Execute the function
                tool_output = lookup_vendor_info(**arguments)

                # Step 4: Feed tool output back to the model
                updated_response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL_FAST"),
                    messages=[
                        {
                            "role": "system",
                            "content": "Now consider the following vendor details:",
                        },
                        {"role": "assistant", "content": json.dumps(tool_output)},
                        {
                            "role": "user",
                            "content": "Now, based on that, provide the final structured output.",
                        },
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
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
                        },
                    },
                    max_tokens=150,
                    temperature=0.7,
                )
                final_output = updated_response.choices[0].message.content
                print("\nFinal structured output with tool results:")
                print(final_output)
            else:
                raise ValueError(f"Unknown function: {tool_call.function.name}")
        else:
            # No function call - final output is already available
            final_output = message.content
            print("\nStructured output:")
            print(final_output)

    except Exception as e:
        print(f"\nError during test: {str(e)}")
        raise


if __name__ == "__main__":
    test_structured_output_with_tools()
