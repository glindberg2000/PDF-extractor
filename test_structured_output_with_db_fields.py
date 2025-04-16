from openai import OpenAI
import os
import json
import sys
from dotenv import load_dotenv

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.vendor_lookup.brave_search import lookup_vendor_info

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
            "It returns structured information including business title, URL, description, and relevance score."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_name": {
                    "type": "string",
                    "description": "The name of the vendor/business to look up"
                },
                "max_results": {
                    "type": "number",
                    "description": "Maximum number of results to return (default: 5, max: 20)",
                    "default": 5
                }
            },
            "required": ["vendor_name"]
        }
    }
}

# Admin-editable prompt section
ADMIN_PROMPT = """Your role is to:
1. Extract and normalize transaction details from bank descriptions
2. Identify the true payee/vendor
3. ALWAYS look up vendor information using the search tool
4. Standardize the transaction description

For each transaction, provide:
1. Normalized Description: Clear, standardized version of the transaction (e.g., "Grocery shopping", "Online subscription")
2. Payee: The actual vendor/entity receiving the payment
3. Transaction Type: One of: purchase, payment, transfer, fee, subscription, service
4. Confidence Score: high, medium, or low indicating certainty in the normalization
5. Original Context: Key details from the original description
6. Questions: Any questions about unclear elements"""

def construct_prompt():
    """
    Construct the system prompt using the admin-editable section and dynamic field definitions.
    """
    # Define field descriptions based on database schema
    field_descriptions = {
        "payee": {
            "type": "string",
            "description": "The identified payee/merchant name",
            "max_length": 255,
            "required": True
        },
        "confidence": {
            "type": "string",
            "description": "Confidence level in the identification",
            "choices": ["high", "medium", "low"],
            "required": True
        },
        "reasoning": {
            "type": "text",
            "description": "Explanation of the identification and classification",
            "required": True
        },
        "needs_search": {
            "type": "boolean",
            "description": "Whether additional vendor information is needed",
            "required": True,
            "default": True
        },
        "transaction_type": {
            "type": "string",
            "description": "Type of transaction",
            "choices": ["purchase", "payment", "transfer", "fee", "subscription", "service"],
            "required": True
        },
        "normalized_description": {
            "type": "text",
            "description": "What the transaction was for, without the vendor name",
            "required": True
        },
        "original_context": {
            "type": "text",
            "description": "Key details from the original description",
            "required": True
        },
        "questions": {
            "type": "text",
            "description": "Any questions about unclear elements",
            "required": True
        }
    }

    # Start with admin-editable prompt
    system_prompt = ADMIN_PROMPT + "\n\n"

    # Add dynamic JSON schema
    system_prompt += "IMPORTANT: Return a JSON object with EXACTLY these field names:\n{\n"
    for field_name, field_info in field_descriptions.items():
        if field_info.get("required", False):
            choices = field_info.get("choices")
            if choices:
                choices_str = ", ".join(f"'{choice}'" for choice in choices)
                system_prompt += f"    '{field_name}': 'string - Must be one of: {choices_str}',\n"
            else:
                system_prompt += f"    '{field_name}': '{field_info['type']} - {field_info['description']}',\n"
    system_prompt += "}"

    return system_prompt

def test_structured_output_with_db_fields():
    """
    Test structured output with JSON schema enforcement and tool usage.
    Uses admin-editable prompt with dynamic field definitions.
    """
    try:
        print("\nStarting test with transaction description...")
        
        # Get the system prompt constructed from admin section and dynamic fields
        system_prompt = construct_prompt()
        
        # Step 1: Initial API call with tool definitions
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_FAST"),
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM",
                },
            ],
            functions=[brave_search_tool["function"]],
            function_call={"name": "brave_search"},
            response_format={"type": "json_object"},
        )

        # Step 2: Check for function call
        message = response.choices[0].message
        print(f"\nInitial Response from LLM:")
        print(f"Content: {message.content}")
        print(f"Function Call: {message.function_call}")

        if message.function_call:
            # Step 3: Execute the function
            function_name = message.function_call.name
            if function_name == "brave_search":
                # Parse arguments
                arguments = json.loads(message.function_call.arguments)
                print(f"\nCalling Brave Search with arguments: {arguments}")
                
                # Execute the function with actual Brave Search implementation
                try:
                    tool_output = lookup_vendor_info(
                        vendor_name=arguments["vendor_name"],
                        max_results=arguments.get("max_results", 5)
                    )
                    
                    print(f"\nBrave Search Results:")
                    print(json.dumps(tool_output, indent=2))

                    # Step 4: Feed tool output back to the model
                    updated_response = client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL_FAST"),
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {"role": "assistant", "content": json.dumps(tool_output)},
                            {
                                "role": "user",
                                "content": "Now, based on that vendor information, provide the final structured output.",
                            },
                        ],
                        response_format={"type": "json_object"},
                    )

                    print(f"\nFinal Response:")
                    print(json.dumps(json.loads(updated_response.choices[0].message.content), indent=2))
                except Exception as e:
                    print(f"\nError executing Brave Search: {str(e)}")
                    raise

    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    test_structured_output_with_db_fields()
