import os
import json
from openai import OpenAI
from django.test import TestCase
from profiles.models import Agent, LLMConfig, Tool
import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class TestStructuredOutputWithDBModel(TestCase):
    """Test structured output using database models for prompt and tool configuration."""

    def setUp(self):
        """Set up test data."""
        # Create LLM config
        self.llm_config = LLMConfig.objects.create(
            provider="openai", model=os.getenv("OPENAI_MODEL_FAST"), url=None
        )

        # Create tools
        self.brave_search_tool = Tool.objects.create(
            name="brave_search",
            description="Search for vendor information using Brave Search",
            module_path="tools.vendor_lookup.brave_search",
        )

        # Create agent with prompt and tools
        self.agent = Agent.objects.create(
            name="Transaction Classifier",
            purpose="Classify transactions and identify payees",
            prompt="""Your role is to:
1. Extract and normalize transaction details from bank descriptions
2. Identify the true payee/vendor
3. ALWAYS look up vendor information using the search tool
4. Standardize the transaction description

For each transaction, provide a JSON response with:
1. normalized_description: Clear, standardized version of the transaction
2. payee: The actual vendor/entity receiving the payment
3. transaction_type: One of: purchase, payment, transfer, fee, subscription, service
4. confidence: high, medium, or low indicating certainty in the normalization
5. original_context: Key details from the original description
6. questions: Any questions about unclear elements

Your response MUST be a valid JSON object with these exact field names.""",
            llm=self.llm_config,
        )
        self.agent.tools.add(self.brave_search_tool)

    def test_structured_output_with_db_model(self):
        """Test structured output using database models."""
        try:
            print("\nStarting test with transaction description...")

            # Get tools from agent
            tools = []
            for tool in self.agent.tools.all():
                # Import the tool module
                module = __import__(tool.module_path, fromlist=[""])
                # Get the function schema from the module
                if hasattr(module, "function_schema"):
                    tools.append(module.function_schema)

            # Step 1: Initial API call with tool definitions
            response = client.chat.completions.create(
                model=self.agent.llm.model,
                messages=[
                    {"role": "system", "content": self.agent.prompt},
                    {
                        "role": "user",
                        "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM",
                    },
                ],
                functions=tools,
                function_call={"name": "brave_search"},
                response_format={"type": "json_object"},
            )

            # Step 2: Check for function call
            message = response.choices[0].message
            print(f"\nInitial Response from LLM:")
            print(f"Content: {message.content}")
            print(f"Function Call: {message.function_call}")

            # Step 3: Execute the function call
            if message.function_call:
                print("\nExecuting function call...")
                function_name = message.function_call.name
                function_args = json.loads(message.function_call.arguments)

                # Execute the appropriate tool
                if function_name == "brave_search":
                    from tools.vendor_lookup.brave_search import brave_search

                    tool_result = brave_search(**function_args)
                    print(
                        f"\nBrave Search Results: {json.dumps(tool_result, indent=2)}"
                    )

                    # Step 4: Feed the tool result back to the model
                    response = client.chat.completions.create(
                        model=self.agent.llm.model,
                        messages=[
                            {"role": "system", "content": self.agent.prompt},
                            {
                                "role": "user",
                                "content": "POS PURCHASE POS PURCHASE TERMINAL 001 LOWE'S #1636 ALBUQUERQ NM",
                            },
                            {
                                "role": "assistant",
                                "content": None,
                                "function_call": message.function_call,
                            },
                            {
                                "role": "function",
                                "name": function_name,
                                "content": json.dumps(tool_result),
                            },
                        ],
                        response_format={"type": "json_object"},
                    )

                    # Print final structured output
                    final_message = response.choices[0].message
                    print(f"\nFinal Structured Output:")
                    print(json.dumps(json.loads(final_message.content), indent=2))

        except Exception as e:
            print(f"Error in test: {str(e)}")
            raise
