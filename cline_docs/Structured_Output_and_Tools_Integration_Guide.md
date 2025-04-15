# Structured Output and Tools Integration Guide

This document provides step-by-step instructions and clear examples for integrating structured outputs and tool calling with the OpenAI API. The primary goal is to enable a single API call where the LLM performs all processing (including tool execution) and returns a valid JSON object that is automatically validated against a defined schema.

## Table of Contents
1. Overview
2. Structured Output with JSON Schema Enforcement
3. Attaching Tools to the LLM Agent
4. End-to-End Example
5. Processing Results
6. Best Practices and Tips
7. Troubleshooting Common Errors
8. Detailed Implementation Flow
9. Code Review and Verification

## Overview

In our flow, we want an LLM agent to:
- Extract and normalize transaction details from a bank description.
- Identify the correct payee/vendor.
- Use an attached tool (e.g., Brave Search) to fetch additional vendor information if needed.
- Return a structured JSON response that includes fields such as the normalized payee, confidence, reasoning, and other details.

This approach eliminates manual post-processing and multiple LLM calls by:
- Providing a detailed system prompt.
- Defining a JSON schema that the LLM must adhere to.
- Integrating tool definitions so that the LLM calls them internally.

## Structured Output with JSON Schema Enforcement

### Why Use Structured Outputs?
- Validation: The schema guarantees that responses include all required fields.
- Simplicity: Downstream systems receive a validated JSON object, eliminating the need for manual parsing or cleanup.
- Integration: Encourages a single API call where both analysis and tool execution are handled by the LLM.

### Defining the JSON Schema

The structured output is defined using a JSON schema. Here's an example schema for transaction classification:

```json
{
  "type": "object",
  "properties": {
    "classification_type": {
      "type": "string",
      "enum": ["business", "personal"]
    },
    "worksheet": {
      "type": "string",
      "enum": ["6A", "Auto", "HomeOffice", "None"]
    },
    "irs_category": {
      "type": "string"
    },
    "confidence": {
      "type": "string",
      "enum": ["high", "medium", "low"]
    },
    "reasoning": {
      "type": "string"
    },
    "questions": {
      "type": "string"
    }
  },
  "required": [
    "classification_type",
    "worksheet",
    "irs_category",
    "confidence",
    "reasoning",
    "questions"
  ],
  "additionalProperties": false
}
```

### How to Include the Schema in the API Call

When using the OpenAI Python client's higher-level methods (e.g., client.responses.create), you pass the schema under the text.format key as follows:

```python
text_config = {
    "format": {
        "type": "json_schema",
        "name": "transaction_classification",
        "schema": {  # Use "schema" here, not "json_schema"
            "type": "object",
            "properties": {
                "classification_type": {
                    "type": "string",
                    "enum": ["business", "personal"]
                },
                "worksheet": {
                    "type": "string",
                    "enum": ["6A", "Auto", "HomeOffice", "None"]
                },
                "irs_category": {
                    "type": "string"
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"]
                },
                "reasoning": {
                    "type": "string"
                },
                "questions": {
                    "type": "string"
                }
            },
            "required": [
                "classification_type",
                "worksheet",
                "irs_category",
                "confidence",
                "reasoning",
                "questions"
            ],
            "additionalProperties": False
        },
        "strict": True  # Enforce strict adherence to the schema
    }
}
```

## Attaching Tools to the LLM Agent

Tools are external functions that the LLM can call to enrich its responses. For example, a tool might perform a Brave Search lookup to gather vendor information.

### Example: Brave Search Tool Definition

```python
tool_definition = {
    "type": "function",
    "function": {
        "name": "brave_search",
        "description": (
            "Brave Search API Integration for Vendor Information Lookup\n\n"
            "This tool uses the Brave Search API to look up vendor information and descriptions.\n"
            "It takes a vendor name as input and returns structured information about the vendor, including a description and relevant details.\n\n"
            "The tool requires a BRAVE_SEARCH_API_KEY environment variable to be set."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up"
                }
            },
            "required": ["query"]
        }
    }
}
```

### How to Include Tools in the API Call

Attach the tool definitions to your API payload under a "tools" key. For example:

```python
tools = [tool_definition]
```

## End-to-End Example

### Complete Payload Example

Below is a complete API payload example that integrates both the structured output and an attached tool, using the OpenAI Python client method client.responses.create.

```python
from openai import OpenAI
import os

client = OpenAI()

response = client.responses.create(
    model="gpt-4o-mini",
    input=[
        {
            "role": "system",
            "content": (
                "Your role is to:\n"
                "1. Extract and normalize transaction details from bank descriptions\n"
                "2. Identify the true payee/vendor\n"
                "3. ALWAYS look up vendor information using the search tool\n"
                "4. Standardize the transaction description\n\n"
                "For each transaction, provide:\n"
                "1. Normalized Description: Clear, standardized version of the transaction (e.g., 'Grocery shopping', 'Online subscription')\n"
                "2. Payee: The actual vendor/entity receiving the payment\n"
                "3. Transaction Type: One of: purchase, payment, transfer, fee, subscription, service\n"
                "4. Confidence Score: high, medium, or low indicating certainty in the normalization\n"
                "5. Original Context: Key details from the original description\n"
                "6. Questions: Any questions about unclear elements\n\n"
                "IMPORTANT: Return a JSON object with EXACTLY these field names:\n"
                "{\n"
                "    'payee': 'string - The identified payee/merchant name',\n"
                "    'confidence': 'string - Must be exactly \"high\", \"medium\", or \"low\"',\n"
                "    'reasoning': 'string - Explanation of the identification',\n"
                "    'needs_search': 'boolean - ALWAYS set this to true',\n"
                "    'transaction_type': 'string - Must be one of: purchase, payment, transfer, fee, subscription, service',\n"
                "    'normalized_description': 'string - What the transaction was for, without the vendor name',\n"
                "    'original_context': 'string - Key details from the original description',\n"
                "    'questions': 'string - Any questions about unclear elements'\n"
                "}"
            )
        },
        {
            "role": "user",
            "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM"
        }
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "transaction_classification",
            "schema": {
                "type": "object",
                "properties": {
                    "classification_type": {
                        "type": "string",
                        "enum": ["business", "personal"]
                    },
                    "worksheet": {
                        "type": "string",
                        "enum": ["6A", "Auto", "HomeOffice", "None"]
                    },
                    "irs_category": {
                        "type": "string"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"]
                    },
                    "reasoning": {
                        "type": "string"
                    },
                    "questions": {
                        "type": "string"
                    }
                },
                "required": [
                    "classification_type",
                    "worksheet",
                    "irs_category",
                    "confidence",
                    "reasoning",
                    "questions"
                ],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    tools=[tool_definition],
    max_tokens=150,
    temperature=0.7
)

print(response.output_text)
```

### Explanation
- System Prompt: Provides detailed instructions for the task and strictly defines the expected output format.
- User Message: Contains the transaction description.
- text.format: The schema is defined under text.format with "schema" (not "json_schema"), including all required keys. The schema forces the LLM to output a JSON object that meets your exact requirements.
- tools: Attaches the brave_search function so that the LLM can internally call the tool if necessary.
- Other Parameters: Such as max_tokens and temperature control the response length and randomness.

## Processing Results

After you receive the response from client.responses.create, you can directly access the structured output via response.output_text. Here's an example of processing the result:

```python
import json

try:
    # Assume response.output_text is a JSON string as per our schema
    result = json.loads(response.output_text)
    print("Structured Response:", result)
    
    # Validate the fields
    required_fields = [
        "classification_type", "worksheet", "irs_category", 
        "confidence", "reasoning", "questions"
    ]
    
    if not all(field in result for field in required_fields):
        raise ValueError("Missing required field in response")
        
    # Process the result as needed (e.g., store it in your database)
except Exception as e:
    print("Failed to process response:", str(e))
```

This snippet:
- Parses the JSON output.
- Verifies that all required fields are present.
- Processes the structured result accordingly.

## Best Practices and Tips
- Clear Instructions: Provide as detailed a system prompt as possible. Outline the expected output format in plain text to guide the LLM.
- Strict Schema Mode: Use "strict": True to enforce exact adherence to the schema.
- Tool Integration: Define and attach tools clearly. Include a description and parameter definitions so that the LLM knows when to invoke them.
- Client vs. Raw Calls: Use the OpenAI Python client's high-level methods (like client.responses.create) for structured output features. These are designed to handle the additional formatting parameters.
- Error Handling: Always validate the output (using JSON parsing and field checks) to ensure you have the expected structured response.

## Troubleshooting Common Errors
- Missing Required Parameters:
  Ensure all keys defined in your schema's "properties" array are also listed in the "required" array if using strict mode.
- Incorrect Key Names:
  Use "schema" (not "json_schema") under text.format.
- Unrecognized Parameters:
  If using raw HTTP calls, note that structured output parameters (under "text") might not be supported. Use the OpenAI Python client's method instead.
- Tool Invocation Issues:
  Verify that tool definitions are correct and that any required environment variables (such as BRAVE_SEARCH_API_KEY) are set.

## Detailed Implementation Flow

The following sections detail the complete flow of a working implementation that successfully integrates tool calling with structured output.

### 1. Initialization and Environment Setup

```python
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()
```

### 2. Tool Definition

```python
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
                    "description": "The search query to look up vendor information."
                }
            },
            "required": ["query"]
        }
    }
}
```

### 3. Mock Lookup Function

```python
def lookup_vendor_info(query):
    """
    Mock function to simulate Brave Search API call.
    In a real implementation, this would make an actual API call.
    """
    # Simulate API response with unique, detailed data
    return {
        "title": "Lowe's Home Improvement #1636",
        "url": "https://www.lowes.com/store/NM-Albuquerque/1636",
        "description": "Lowe's #1636 is a home improvement superstore located in Albuquerque, NM...",
        "location": {
            "address": "1234 Home Improvement Way",
            "city": "Albuquerque",
            "state": "NM",
            "zip": "87101"
        },
        "store_details": {
            "store_number": "1636",
            "square_footage": "120,000",
            "opening_date": "2005-03-15",
            "special_features": ["Garden Center", "Pro Services Desk", "Lumber Yard"]
        },
        "business_hours": {
            "monday": "6:00 AM - 10:00 PM",
            "tuesday": "6:00 AM - 10:00 PM",
            "wednesday": "6:00 AM - 10:00 PM",
            "thursday": "6:00 AM - 10:00 PM",
            "friday": "6:00 AM - 10:00 PM",
            "saturday": "6:00 AM - 10:00 PM",
            "sunday": "7:00 AM - 9:00 PM"
        },
        "relevance_score": 0.98,
        "last_updated": "2024-03-20T14:30:00Z",
        "additional_info": {
            "services": ["Delivery", "Installation", "Rental", "Design Services"],
            "payment_methods": ["Credit Cards", "Lowe's Credit Card", "Cash", "Check"],
            "special_programs": ["Military Discount", "Pro Rewards", "Project Calculator"]
        }
    }
```

### 4. Main Function Flow

```python
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
                        "    'confidence': 'string - Must be exactly \"high\", \"medium\", or \"low\"',\n"
                        "    'reasoning': 'string - Explanation of the classification (include vendor details from the search if applicable)',\n"
                        "    'needs_search': 'boolean - ALWAYS set this to true'\n"
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM"
                }
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
                                "enum": ["purchase", "payment", "transfer", "fee", "subscription", "service"]
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"]
                            },
                            "reasoning": {"type": "string"},
                            "needs_search": {"type": "boolean"}
                        },
                        "required": ["payee", "transaction_type", "confidence", "reasoning", "needs_search"],
                        "additionalProperties": False
                    }
                }
            },
            tools=[brave_search_tool],
            max_tokens=150,
            temperature=0.7
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
                            "content": "Now consider the following vendor details:"
                        },
                        {
                            "role": "assistant",
                            "content": json.dumps(tool_output)
                        },
                        {
                            "role": "user",
                            "content": "Now, based on that, provide the final structured output."
                        }
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
                                        "enum": ["purchase", "payment", "transfer", "fee", "subscription", "service"]
                                    },
                                    "confidence": {
                                        "type": "string",
                                        "enum": ["high", "medium", "low"]
                                    },
                                    "reasoning": {"type": "string"},
                                    "needs_search": {"type": "boolean"}
                                },
                                "required": ["payee", "transaction_type", "confidence", "reasoning", "needs_search"],
                                "additionalProperties": False
                            }
                        }
                    },
                    max_tokens=150,
                    temperature=0.7
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

## Code Review and Verification

### Overall Flow Verification

1. **Initialization and Environment Setup**
   - Correctly loads environment variables and initializes the OpenAI client
   - Standard practice for API integration

2. **Tool Definition**
   - Properly defines the Brave Search tool with clear name, description, and parameters
   - Correctly formatted for API integration

3. **Mock Lookup Function**
   - Provides detailed, realistic mock data for testing
   - Demonstrates expected API response structure

4. **Initial API Call (Step 1)**
   - Sends detailed system message with clear instructions
   - Includes proper response_format with JSON schema
   - Attaches tool definition correctly

5. **Tool Call Detection (Step 2)**
   - Properly checks for tool_calls in the response
   - Handles the first tool call appropriately

6. **Tool Execution (Step 3)**
   - Correctly parses tool call arguments
   - Executes the mock function with proper parameters

7. **Tool Output Integration (Step 4)**
   - Makes follow-up API call with tool results
   - Maintains consistent schema enforcement
   - Provides clear context for the LLM

### Specific Review Points

1. **Tool Call Detection**
   - Properly checks message.tool_calls
   - Handles single tool call appropriately

2. **Argument Parsing**
   - Correctly uses json.loads for argument parsing
   - Properly passes arguments to the lookup function

3. **Minimal Custom Integration**
   - Integration layer is kept minimal
   - Focuses on essential tool execution and result feeding

4. **Structured Output**
   - Well-defined JSON schema
   - Proper required fields and property restrictions
   - Consistent schema enforcement across calls

5. **Error Handling**
   - Comprehensive try/except block
   - Clear error messages and propagation

### Recommendations

1. **Edge Cases**
   - Consider handling multiple tool calls if needed
   - Verify environment variables are properly set

2. **Logging/Debugging**
   - Add more detailed logging if needed
   - Include step-by-step progress indicators

3. **Client Library Version**
   - Verify compatibility with current OpenAI client version
   - Document any version-specific requirements

## Conclusion

This implementation successfully demonstrates:
- Proper tool definition and integration
- Correct function call detection and execution
- Effective tool result integration
- Consistent structured output enforcement

The approach minimizes custom integration while leveraging the OpenAI client's built-in functionality, providing a robust and maintainable solution for structured output with tool integration. 