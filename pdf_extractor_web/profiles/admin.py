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


def call_agent(agent, description, transaction_id=None):
    """Generic function to call any agent"""
    # Get the agent's configuration
    llm = agent.llm
    prompt = (
        "You are an expert in business expense classification and tax preparation. Your role is to:\n\n"
        "1. Analyze transactions and determine if they are business or personal expenses\n"
        "2. For business expenses, determine the appropriate worksheet (6A, Vehicle, HomeOffice, or Personal)\n"
        "3. Provide detailed reasoning for your decisions\n"
        "4. Flag any transactions that need additional review\n\n"
        "Consider these factors:\n"
        "- Business type and description\n"
        "- Industry context\n"
        "- Transaction patterns\n"
        "- Amount and frequency\n"
        "- Business rules and patterns\n\n"
        "IMPORTANT RULES:\n"
        "- Personal expenses MUST use 'Personal' as the worksheet\n"
        "- Business expenses must NEVER use 'Personal' as the worksheet\n"
        "- For business expenses, use '6A' for general business expenses\n"
        "- Use 'Vehicle' for vehicle-related expenses\n"
        "- Use 'HomeOffice' for home office expenses\n"
        "- DO NOT use 'None' or any other value not in the list above\n\n"
        "Return your analysis in this exact JSON format:\n"
        "{\n"
        '    "classification_type": "business" or "personal",\n'
        '    "worksheet": "6A" or "Vehicle" or "HomeOffice" or "Personal",\n'
        '    "irs_category": "Name of IRS category if business",\n'
        '    "confidence": "high" or "medium" or "low",\n'
        '    "reasoning": "Detailed explanation of your decision",\n'
        '    "questions": "Any questions or uncertainties about this classification"\n'
        "}\n\n"
        "IMPORTANT: Your response must be a valid JSON object."
    )
    tool_definitions = []

    # Prepare tools for the API call with proper schema
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

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Get business profile information if available
    business_context = ""
    try:
        if transaction_id:
            transaction = Transaction.objects.get(id=transaction_id)
            if transaction.client:
                business = transaction.client
                business_context = (
                    f"\nBusiness Context:\n"
                    f"- Business Type: {business.business_type}\n"
                    f"- Description: {business.business_description}\n"
                    f"- Common Expenses: {business.common_expenses}\n"
                    f"- Industry Keywords: {business.industry_keywords}\n"
                    f"- Category Patterns: {business.category_patterns}\n"
                )
    except Transaction.DoesNotExist:
        pass

    # Prepare the API request payload
    payload = {
        "model": llm.model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"{description}{business_context}"},
        ],
        "response_format": {"type": "json_object"},
        "tools": tool_definitions if tool_definitions else None,
    }

    # Log the complete API request
    logger.info("\n=== API Request ===")
    logger.info(f"Model: {llm.model}")
    logger.info(f"Prompt: {prompt}")
    logger.info(f"Description: {description}")
    logger.info(f"Business Context: {business_context}")
    if tool_definitions:
        logger.info(f"Tools: {json.dumps(tool_definitions, indent=2)}")

    try:
        # Make the API call
        response = client.chat.completions.create(**payload)
        logger.info("\n=== API Response ===")
        logger.info(f"Response: {response}")

        # Check if we got a tool call
        if response.choices[0].message.tool_calls:
            logger.info("Tool call detected, executing...")
            tool_call = response.choices[0].message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            logger.info(f"Tool call: {tool_name} with args: {tool_args}")

            # Execute the tool
            if tool_name == "brave_search":
                from tools.vendor_lookup.brave_search import brave_search

                search_results = brave_search(tool_args["query"])
                logger.info(f"Search results: {json.dumps(search_results, indent=2)}")

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

                # Get final response
                response = client.chat.completions.create(**payload)
                logger.info(f"Final response after tool: {response}")

        # Get the final content
        if not response.choices or not response.choices[0].message.content:
            logger.error("No content in final API response")
            raise ValueError("No content in final API response")

        content = response.choices[0].message.content
        logger.info(f"Final content: {content}")

        result = json.loads(content)
        logger.info(f"Parsed result: {json.dumps(result, indent=2)}")
        return result

    except Exception as e:
        logger.error(f"Error in call_agent: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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
            response = call_agent(agent, transaction.description, transaction.id)

            # Update transaction with the response
            update_fields = {
                "normalized_description": response.get("normalized_description"),
                "payee": response.get("payee"),
                "confidence": response.get("confidence", "low"),
                "reasoning": response.get("reasoning"),
                "business_context": response.get("business_context"),
                "questions": response.get("questions"),
            }

            # Remove None values
            update_fields = {k: v for k, v in update_fields.items() if v is not None}

            # Update the transaction
            Transaction.objects.filter(id=transaction.id).update(**update_fields)

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
        "business_context",
        "classification_method",
        "payee_extraction_method",
        "reasoning",
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
    )

    def get_actions(self, request):
        actions = super().get_actions(request)

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
                    response = call_agent(
                        agent, transaction.description, transaction.id
                    )
                    logger.info(f"Agent response: {response}")

                    # Map response fields to database fields
                    update_fields = {
                        "normalized_description": response.get(
                            "Normalized Description"
                        ),
                        "payee": response.get("Payee"),
                        "confidence": response.get("confidence", "low"),
                        "reasoning": response.get("reasoning"),
                        "transaction_type": response.get("Transaction Type"),
                        "questions": response.get("Questions"),
                        "classification_type": response.get("classification_type"),
                        "worksheet": response.get("worksheet", "6A"),
                        "business_percentage": (
                            100
                            if response.get("classification_type") == "business"
                            else 0
                        ),
                        "payee_extraction_method": (
                            "AI+Search" if response.get("needs_search", False) else "AI"
                        ),
                        "classification_method": "AI",
                        "business_context": response.get("business_context"),
                        "category": response.get("irs_category"),
                    }

                    # Validate and correct worksheet value
                    worksheet = update_fields.get("worksheet", "")
                    if worksheet == "None" or not worksheet:
                        if update_fields.get("classification_type") == "personal":
                            update_fields["worksheet"] = "Personal"
                        else:
                            update_fields["worksheet"] = "6A"
                        logger.warning(
                            f"Corrected invalid worksheet value '{worksheet}' to '{update_fields['worksheet']}'"
                        )

                    # Log the update fields
                    logger.info(
                        f"Update fields for transaction {transaction.id}: {update_fields}"
                    )

                    # Remove None values
                    update_fields = {
                        k: v for k, v in update_fields.items() if v is not None
                    }
                    logger.info(f"Cleaned update fields: {update_fields}")

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
    list_display = ("name", "description", "module_path")
    search_fields = ("name", "description", "module_path")


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
