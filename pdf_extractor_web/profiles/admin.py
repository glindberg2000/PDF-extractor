from django.contrib import admin
from .models import (
    BusinessProfile,
    Transaction,
    LLMConfig,
    Agent,
    Tool,
    NormalizedVendorData,
    IRSWorksheet,
    IRSExpenseCategory,
    BusinessExpenseCategory,
    TransactionClassification,
)
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
import json
from jsonschema import validate, ValidationError
import requests
import os
from dotenv import load_dotenv
import logging
import traceback
from openai import OpenAI
import sys
from django.core.management import call_command

# Add the root directory to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger.addHandler(handler)


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("client_id", "business_type")
    search_fields = ("client_id", "business_description")


class ClientFilter(admin.SimpleListFilter):
    title = _("client")
    parameter_name = "client"

    def lookups(self, request, model_admin):
        clients = set(Transaction.objects.values_list("client__client_id", flat=True))
        return [(client, client) for client in clients]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(client__client_id=self.value())
        return queryset


def call_agent(agent_name, transaction, model="gpt-4o-mini"):
    """Call the specified agent with the transaction data."""
    try:
        # Get the agent object from the database
        agent = Agent.objects.get(name=agent_name)

        # Get the appropriate prompt based on agent type
        if "payee" in agent_name.lower():
            system_prompt = """You are a transaction analysis assistant. Your task is to:
1. Identify the payee/merchant from transaction descriptions
2. Use the search tool to look up vendor information if needed
3. Provide detailed, normalized descriptions
4. Return a final response in the exact JSON format specified

IMPORTANT RULES:
1. Make at most ONE search call
2. After the search (or immediately if search not needed), provide the final JSON response
3. Format the response exactly as specified"""

            user_prompt = f"""Analyze this transaction and return a JSON object with EXACTLY these field names:
{{
    "normalized_description": "string - Detailed description of what was purchased/paid for, including vendor type and purpose (e.g., 'Farm equipment purchase from Kubota dealership', 'Online subscription to business software')",
    "payee": "string - The normalized payee/merchant name (e.g., 'Lowe's' not 'LOWE'S #1636', 'Walmart' not 'WALMART #1234')",
    "confidence": "string - Must be exactly 'high', 'medium', or 'low'",
    "reasoning": "string - Explanation of the identification, including any search results used",
    "transaction_type": "string - One of: purchase, payment, transfer, fee, subscription, service",
    "questions": "string - Any questions about unclear elements",
    "needs_search": "boolean - Whether additional vendor information is needed"
}}

Transaction: {transaction.description}
Amount: ${transaction.amount}
Date: {transaction.transaction_date}

IMPORTANT INSTRUCTIONS:
1. Make at most ONE search call to look up vendor information
2. After the search (or if no search needed), provide the final JSON response
3. Include the type of business and what was purchased in the normalized_description
4. Reference any search results used in the reasoning field
5. NEVER include store numbers, locations, or other non-standard elements in the payee field
6. Normalize the payee name to its standard business name (e.g., 'Lowe's' not 'LOWE'S #1636')
7. ALWAYS provide a final JSON response"""

        else:
            # Classification prompt
            category_list = [
                "Advertising",
                "Auto",
                "Bank Charges",
                "Business Insurance",
                "Business Meals",
                "Business Travel",
                "Commissions",
                "Contract Labor",
                "Depreciation",
                "Dues & Subscriptions",
                "Equipment Rental",
                "Equipment Purchase",
                "Gas & Oil",
                "Home Office",
                "Interest",
                "Legal & Professional",
                "Licenses & Permits",
                "Maintenance & Repairs",
                "Marketing",
                "Meals & Entertainment",
                "Office Supplies",
                "Other",
                "Payroll",
                "Postage",
                "Printing",
                "Professional Development",
                "Property Taxes",
                "Rent",
                "Repairs & Maintenance",
                "Software",
                "Supplies",
                "Taxes & Licenses",
                "Telephone",
                "Travel",
                "Utilities",
                "Wages",
            ]
            system_prompt = """You are an expert in business expense classification and tax preparation. Your role is to:
1. Analyze transactions and determine if they are business or personal expenses
2. For business expenses, determine the appropriate worksheet (6A, Vehicle, HomeOffice, or Personal)
3. Provide detailed reasoning for your decisions
4. Flag any transactions that need additional review

Consider these factors:
- Business type and description
- Industry context
- Transaction patterns
- Amount and frequency
- Business rules and patterns"""

            # Get business context
            business_context = ""
            if transaction.client:
                try:
                    business_profile = BusinessProfile.objects.get(
                        client_id=transaction.client.client_id
                    )
                    business_context = f"""
Business Context:
Type: {business_profile.business_type}
Description: {business_profile.business_description}
Industry Keywords: {', '.join(business_profile.industry_keywords) if business_profile.industry_keywords else 'Not specified'}
Common Expenses: {', '.join(business_profile.common_expenses) if business_profile.common_expenses else 'Not specified'}
Category Patterns: {', '.join(business_profile.category_patterns) if business_profile.category_patterns else 'Not specified'}
"""
                except BusinessProfile.DoesNotExist:
                    logger.warning(
                        f"No business profile found for client {transaction.client.client_id}"
                    )

            user_prompt = f"""Return your analysis in this exact JSON format:
{{
    "classification_type": "business" or "personal",
    "worksheet": "6A" or "Vehicle" or "HomeOffice" or "Personal",
    "category": "Name of IRS or business category",
    "confidence": "high" or "medium" or "low",
    "reasoning": "Detailed explanation of your decision",
    "questions": "Any questions or uncertainties about this classification"
}}

Transaction: {transaction.description}
Amount: ${transaction.amount}
Date: {transaction.transaction_date}

{business_context}

Available Categories:
{chr(10).join(category_list)}

IMPORTANT RULES:
- Personal expenses MUST use 'Personal' as the worksheet
- Business expenses must NEVER use 'Personal' as the worksheet
- For business expenses, use '6A' for general business expenses
- Use 'Vehicle' for vehicle-related expenses
- Use 'HomeOffice' for home office expenses
- DO NOT use 'None' or any other value not in the list above
- For business expenses, choose the most specific category that matches
- If no exact match, use the most appropriate IRS category
- For custom business categories, use them when they match exactly
- Consider the business context when making classification decisions

IMPORTANT: Your response must be a valid JSON object."""

        # Prepare tools for the API call with proper schema
        tool_definitions = []
        for tool in agent.tools.all():
            tool_def = {
                "name": tool.name,
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query to look up",
                            }
                        },
                        "required": ["query"],
                    },
                },
            }
            tool_definitions.append(tool_def)

        # Prepare the API request payload
        payload = {
            "model": agent.llm.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        # Only add tools and tool_choice if tools are available
        if tool_definitions:
            payload["tools"] = tool_definitions
            payload["tool_choice"] = "auto"

        # Log the complete API request
        logger.info("\n=== API Request ===")
        logger.info(f"Model: {agent.llm.model}")
        logger.info(f"System Prompt: {system_prompt}")
        logger.info(f"User Prompt: {user_prompt}")
        logger.info(f"Transaction: {transaction.description}")
        if tool_definitions:
            logger.info(f"Tools: {json.dumps(tool_definitions, indent=2)}")

        try:
            # Make the API call
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(**payload)
            logger.info("\n=== API Response ===")
            logger.info(f"Response: {response}")

            # Track if we've already made a tool call
            tool_call_made = False
            max_tool_calls = 1  # Limit to one tool call

            # Handle tool calls and final response
            while (
                response.choices
                and response.choices[0].message.tool_calls
                and not tool_call_made
                and max_tool_calls > 0
            ):
                tool_call = response.choices[0].message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Tool call: {tool_name} with args: {tool_args}")

                # Execute the tool
                if tool_name == "searxng_search":
                    from tools.vendor_lookup.searxng_search import searxng_search

                    search_results = searxng_search(tool_args["query"])
                    logger.info(
                        f"Search results: {json.dumps(search_results, indent=2)}"
                    )

                    # Feed results back to the model
                    payload["messages"].extend(
                        [
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [tool_call],
                            },
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": json.dumps(search_results),
                            },
                        ]
                    )

                    # Add a message emphasizing the need for a final JSON response
                    payload["messages"].append(
                        {
                            "role": "user",
                            "content": "Now provide your final response in the exact JSON format specified. Do not make any more tool calls.",
                        }
                    )

                    # Get final response
                    response = client.chat.completions.create(**payload)
                    logger.info(f"Final response after tool: {response}")
                    tool_call_made = True
                    max_tool_calls -= 1

            # Get the final content
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("No response content received from the API")

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error in call_agent: {str(e)}")
        raise


def process_transactions(modeladmin, request, queryset):
    if "agent" not in request.POST:
        # Show the agent selection form
        agents = Agent.objects.all().order_by("name")  # Order agents by name
        if not agents:
            messages.error(
                request, "No agents available. Please create an agent first."
            )
            return HttpResponseRedirect(request.get_full_path())

        return render(
            request,
            "admin/process_transactions.html",
            context={
                "transactions": queryset,
                "agents": agents,
                "title": "Select Agent to Process Transactions",
                "opts": modeladmin.model._meta,
            },
        )

    # Process the transactions with the selected agent
    agent_id = request.POST["agent"]
    try:
        agent = Agent.objects.get(id=agent_id)
        for transaction in queryset:
            response = call_agent(agent.name, transaction)

            # Update transaction with the response
            update_fields = {
                "normalized_description": response.get("normalized_description"),
                "payee": response.get("payee"),
                "confidence": response.get("confidence"),
                "reasoning": response.get("reasoning"),
                "payee_reasoning": (
                    response.get("reasoning") if "payee" in agent.name.lower() else None
                ),
                "transaction_type": response.get("transaction_type"),
                "questions": response.get("questions"),
                "classification_type": response.get("classification_type"),
                "worksheet": response.get("worksheet"),
                "business_percentage": response.get("business_percentage"),
                "payee_extraction_method": (
                    "AI+Search" if "payee" in agent.name.lower() else "AI"
                ),
                "classification_method": "AI",
                "business_context": response.get("business_context"),
                "category": response.get("category"),
            }

            # Clean up fields
            update_fields = {k: v for k, v in update_fields.items() if v is not None}

            # For payee lookups, only update payee-related fields
            if "payee" in agent.name.lower():
                update_fields = {
                    k: v
                    for k, v in update_fields.items()
                    if k
                    in [
                        "normalized_description",
                        "payee",
                        "confidence",
                        "payee_reasoning",
                        "transaction_type",
                        "questions",
                        "payee_extraction_method",
                    ]
                }
            else:
                # For classification, ensure personal expenses have correct worksheet and category
                if update_fields.get("classification_type") == "personal":
                    update_fields["worksheet"] = "Personal"
                    update_fields["category"] = "Personal"
                    # Add detailed reasoning for personal expenses
                    if "reasoning" not in update_fields:
                        update_fields["reasoning"] = (
                            "Transaction classified as personal expense based on description and amount"
                        )

            logger.info(
                f"Update fields for transaction {transaction.id}: {update_fields}"
            )

            # Update the transaction
            rows_updated = Transaction.objects.filter(id=transaction.id).update(
                **update_fields
            )
            logger.info(f"Updated {rows_updated} rows for transaction {transaction.id}")

            # Verify the update
            updated_tx = Transaction.objects.get(id=transaction.id)
            logger.info(
                f"Transaction {transaction.id} after update: payee={updated_tx.payee}, classification_type={updated_tx.classification_type}, worksheet={updated_tx.worksheet}, confidence={updated_tx.confidence}, category={updated_tx.category}"
            )

        messages.success(
            request,
            f"Successfully processed {queryset.count()} transactions with {agent.name}",
        )
    except Agent.DoesNotExist:
        messages.error(request, "Selected agent not found")
    except Exception as e:
        messages.error(request, f"Error processing transactions: {str(e)}")

    return HttpResponseRedirect(request.get_full_path())


process_transactions.short_description = "Process selected transactions with agent"


def reset_processing_status(modeladmin, request, queryset):
    """Reset selected transactions to 'Not Processed' status."""
    updated = queryset.update(
        payee_extraction_method=None,
        classification_method=None,
        payee=None,
        normalized_description=None,
        confidence=None,
        reasoning=None,
        payee_reasoning=None,
        business_context=None,
        questions=None,
        classification_type=None,
        worksheet=None,
        business_percentage=None,
        category=None,
    )
    messages.success(
        request, f"Successfully reset {updated} transactions to 'Not Processed' status."
    )


reset_processing_status.short_description = (
    "Reset selected transactions to 'Not Processed'"
)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "amount",
        "description",
        "normalized_description",
        "payee",
        "category",
        "classification_type",
        "worksheet",
        "business_percentage",
        "confidence",
        "reasoning",  # Classification reasoning
        "payee_reasoning",  # Payee lookup reasoning
        "classification_method",
        "payee_extraction_method",
    )
    list_filter = (
        ClientFilter,
        "transaction_date",
        "classification_type",
        "worksheet",
        "confidence",
        "category",
        "source",
        "transaction_type",
        "classification_method",
        "payee_extraction_method",
    )
    search_fields = (
        "description",
        "normalized_description",
        "category",
        "source",
        "transaction_type",
        "account_number",
        "payee",
        "reasoning",
        "payee_reasoning",
        "business_context",
        "questions",
        "classification_type",
        "worksheet",
    )
    readonly_fields = (
        "transaction_date",
        "amount",
        "description",
        "normalized_description",
        "payee",
        "category",
        "classification_type",
        "worksheet",
        "business_percentage",
        "confidence",
        "business_context",
        "classification_method",
        "payee_extraction_method",
        "reasoning",
        "payee_reasoning",
    )
    actions = ["reset_processing_status"]  # Add the new action

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions["reset_processing_status"] = (
            reset_processing_status,
            "reset_processing_status",
            reset_processing_status.short_description,
        )
        # Add an action for each agent
        for agent in Agent.objects.all():
            action_name = f'process_with_{agent.name.lower().replace(" ", "_")}'
            action_function = self._create_agent_action(agent)
            action_function.short_description = f"Process with {agent.name}"
            actions[action_name] = (
                action_function,
                action_name,
                action_function.short_description,
            )

        return actions

    def _create_agent_action(self, agent):
        def process_with_agent(modeladmin, request, queryset):
            try:
                for transaction in queryset:
                    logger.info(
                        f"Processing transaction {transaction.id} with agent {agent.name}"
                    )
                    response = call_agent(agent.name, transaction)
                    logger.info(f"Agent response: {response}")

                    # Map response fields to database fields
                    update_fields = {
                        "normalized_description": response.get(
                            "normalized_description"
                        ),
                        "payee": response.get("payee"),
                        "confidence": response.get("confidence"),
                        "reasoning": response.get("reasoning"),
                        "payee_reasoning": (
                            response.get("reasoning")
                            if "payee" in agent.name.lower()
                            else None
                        ),
                        "transaction_type": response.get("transaction_type"),
                        "questions": response.get("questions"),
                        "classification_type": response.get("classification_type"),
                        "worksheet": response.get("worksheet"),
                        "business_percentage": response.get("business_percentage"),
                        "payee_extraction_method": (
                            "AI+Search" if "payee" in agent.name.lower() else "AI"
                        ),
                        "classification_method": "AI",
                        "business_context": response.get("business_context"),
                        "category": response.get("category"),
                    }

                    # Clean up fields
                    update_fields = {
                        k: v for k, v in update_fields.items() if v is not None
                    }

                    # For payee lookups, only update payee-related fields
                    if "payee" in agent.name.lower():
                        update_fields = {
                            k: v
                            for k, v in update_fields.items()
                            if k
                            in [
                                "normalized_description",
                                "payee",
                                "confidence",
                                "payee_reasoning",
                                "transaction_type",
                                "questions",
                                "payee_extraction_method",
                            ]
                        }
                    else:
                        # For classification, ensure personal expenses have correct worksheet and category
                        if update_fields.get("classification_type") == "personal":
                            update_fields["worksheet"] = "Personal"
                            update_fields["category"] = "Personal"
                            # Add detailed reasoning for personal expenses
                            if "reasoning" not in update_fields:
                                update_fields["reasoning"] = (
                                    "Transaction classified as personal expense based on description and amount"
                                )

                    logger.info(
                        f"Update fields for transaction {transaction.id}: {update_fields}"
                    )

                    # Update the transaction
                    rows_updated = Transaction.objects.filter(id=transaction.id).update(
                        **update_fields
                    )
                    logger.info(
                        f"Updated {rows_updated} rows for transaction {transaction.id}"
                    )

                    # Verify the update
                    updated_tx = Transaction.objects.get(id=transaction.id)
                    logger.info(
                        f"Transaction {transaction.id} after update: payee={updated_tx.payee}, classification_type={updated_tx.classification_type}, worksheet={updated_tx.worksheet}, confidence={updated_tx.confidence}, category={updated_tx.category}"
                    )

                messages.success(
                    request,
                    f"Successfully processed {queryset.count()} transactions with {agent.name}",
                )
            except Exception as e:
                logger.error(
                    f"Error processing transactions with {agent.name}: {str(e)}",
                    exc_info=True,
                )
                messages.error(
                    request,
                    f"Error processing transactions with {agent.name}: {str(e)}",
                )

        return process_with_agent

    def get_urls(self):
        urls = super().get_urls()
        return urls


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "url")
    search_fields = ("provider", "model")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "llm")
    search_fields = ("name", "purpose", "llm__name")
    filter_horizontal = ("tools",)


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "module_path", "created_at", "updated_at")
    search_fields = ("name", "description", "module_path")
    readonly_fields = ("created_at", "updated_at")

    def discover_tools(self, request):
        try:
            call_command("discover_tools")
            messages.success(request, "Successfully discovered and registered tools")
        except Exception as e:
            messages.error(request, f"Error discovering tools: {str(e)}")
        return HttpResponseRedirect("../")  # Redirect back to the tool list

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("discover/", self.discover_tools, name="discover_tools"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_discover_tools"] = True
        return super().changelist_view(request, extra_context)


@admin.register(IRSWorksheet)
class IRSWorksheetAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "is_active")
    search_fields = ("name", "description")
    list_filter = ("is_active",)


@admin.register(IRSExpenseCategory)
class IRSExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "worksheet", "line_number", "is_active")
    search_fields = ("name", "description", "line_number")
    list_filter = ("worksheet", "is_active")
    ordering = ("worksheet", "line_number")


@admin.register(BusinessExpenseCategory)
class BusinessExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "category_name",
        "business",
        "worksheet",
        "parent_category",
        "is_active",
    )
    search_fields = ("category_name", "description")
    list_filter = ("business", "worksheet", "is_active", "tax_year")
    ordering = ("business", "category_name")
