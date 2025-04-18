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
    ProcessingTask,
)
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render, get_object_or_404
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
from datetime import datetime
from django.urls import reverse

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
2. Use the search tool to gather comprehensive vendor information
3. Synthesize all information into a clear, normalized description
4. Return a final response in the exact JSON format specified

IMPORTANT RULES:
1. Make as many search calls as needed to gather complete information
2. Synthesize all information into a clear, normalized response
3. NEVER use the raw transaction description in your final response
4. Format the response exactly as specified"""

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
1. Make as many search calls as needed to gather complete information
2. Synthesize all information into a clear, normalized response
3. NEVER use the raw transaction description in your final response
4. Include the type of business and what was purchased in the normalized_description
5. Reference all search results used in the reasoning field
6. NEVER include store numbers, locations, or other non-standard elements in the payee field
7. Normalize the payee name to its standard business name (e.g., 'Lowe's' not 'LOWE'S #1636')
8. ALWAYS provide a final JSON response after gathering all necessary information"""

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
            search_count = 0
            max_searches = 3

            # Handle tool calls and final response
            while (
                response.choices
                and response.choices[0].message.tool_calls
                and not tool_call_made
                and search_count < max_searches
            ):
                tool_call = response.choices[0].message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Tool call: {tool_name} with args: {tool_args}")

                # Dynamically import and execute the tool
                try:
                    # Get the tool object from the database
                    tool = Tool.objects.get(name=tool_name)
                    # Import the tool module dynamically
                    module_path = tool.module_path
                    module_name = module_path.split(".")[-1]
                    module = __import__(module_path, fromlist=[module_name])
                    # Get the tool function - use search_web for searxng_search tool
                    if tool_name == "searxng_search":
                        tool_function = getattr(module, "search_web")
                    else:
                        tool_function = getattr(module, module_name)

                    # Execute the tool
                    search_results = tool_function(tool_args["query"])
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

                    search_count += 1
                    if search_count >= max_searches:
                        # Add a message emphasizing the need for a final JSON response
                        payload["messages"].append(
                            {
                                "role": "user",
                                "content": "Maximum search limit reached. Now provide your final response in the exact JSON format specified.",
                            }
                        )
                        tool_call_made = True

                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {str(e)}")
                    raise

                # Get next response
                response = client.chat.completions.create(**payload)
                logger.info(f"Response after tool: {response}")

            # If we've made all allowed searches, force a final response
            if search_count >= max_searches and not tool_call_made:
                payload["messages"].append(
                    {
                        "role": "user",
                        "content": "Maximum search limit reached. Now provide your final response in the exact JSON format specified.",
                    }
                )
                response = client.chat.completions.create(**payload)
                logger.info(f"Final response after max searches: {response}")

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
        payee_extraction_method="None",
        classification_method="None",
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
    actions = [
        "reset_processing_status",
        "batch_payee_lookup",
        "batch_classify",
    ]  # Add new actions

    def batch_payee_lookup(self, request, queryset):
        """Create a batch processing task for payee lookup."""
        if not queryset:
            messages.error(request, "No transactions selected.")
            return

        # Group transactions by client
        client_transactions = {}
        for transaction in queryset:
            if transaction.client_id not in client_transactions:
                client_transactions[transaction.client_id] = {
                    "client": transaction.client,
                    "transactions": [],
                }
            client_transactions[transaction.client_id]["transactions"].append(
                transaction
            )

        # Create a task for each client's transactions
        for client_id, data in client_transactions.items():
            task = ProcessingTask.objects.create(
                task_type="payee_lookup",
                client=data["client"],
                transaction_count=len(data["transactions"]),
                status="pending",
                task_metadata={
                    "description": f"Batch payee lookup for {len(data['transactions'])} transactions"
                },
            )
            task.transactions.add(*data["transactions"])
            messages.success(
                request,
                f"Created payee lookup task for client {client_id} with {len(data['transactions'])} transactions",
            )

    batch_payee_lookup.short_description = "Create batch payee lookup task"

    def batch_classify(self, request, queryset):
        """Create a batch processing task for classification."""
        if not queryset:
            messages.error(request, "No transactions selected.")
            return

        # Group transactions by client
        client_transactions = {}
        for transaction in queryset:
            if transaction.client_id not in client_transactions:
                client_transactions[transaction.client_id] = {
                    "client": transaction.client,
                    "transactions": [],
                }
            client_transactions[transaction.client_id]["transactions"].append(
                transaction
            )

        # Create a task for each client's transactions
        for client_id, data in client_transactions.items():
            task = ProcessingTask.objects.create(
                task_type="classification",
                client=data["client"],
                transaction_count=len(data["transactions"]),
                status="pending",
                task_metadata={
                    "description": f"Batch classification for {len(data['transactions'])} transactions"
                },
            )
            task.transactions.add(*data["transactions"])
            messages.success(
                request,
                f"Created classification task for client {client_id} with {len(data['transactions'])} transactions",
            )

    batch_classify.short_description = "Create batch classification task"

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions["reset_processing_status"] = (
            reset_processing_status,
            "reset_processing_status",
            reset_processing_status.short_description,
        )
        # Keep existing agent-specific actions
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


@admin.register(ProcessingTask)
class ProcessingTaskAdmin(admin.ModelAdmin):
    list_display = (
        "task_id",
        "task_type",
        "client",
        "status",
        "transaction_count",
        "processed_count",
        "error_count",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "task_type",
        "status",
        "client",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "task_id",
        "client__client_id",
        "error_details",
        "task_metadata",
    )
    readonly_fields = (
        "task_id",
        "created_at",
        "updated_at",
        "transaction_count",
        "processed_count",
        "error_count",
        "error_details",
        "task_metadata",
    )
    actions = ["retry_failed_tasks", "cancel_tasks", "run_task"]

    def run_task(self, request, queryset):
        """Execute the selected task and show progress."""
        if queryset.count() > 1:
            messages.error(request, "Please select only one task to run at a time.")
            return

        task = queryset.first()
        if task.status not in ["pending", "failed"]:
            messages.error(request, f"Task {task.task_id} is already {task.status}.")
            return

        # Update task status
        task.status = "processing"
        task.save()

        try:
            # Process transactions based on task type
            if task.task_type == "payee_lookup":
                agent = Agent.objects.filter(name__icontains="payee").first()
            else:  # classification
                agent = Agent.objects.filter(name__icontains="classify").first()

            if not agent:
                raise ValueError(f"No agent found for task type {task.task_type}")

            # Process each transaction
            total = task.transactions.count()
            success_count = 0
            error_count = 0
            error_details = {}

            for idx, transaction in enumerate(task.transactions.all(), 1):
                try:
                    # Call the agent
                    response = call_agent(agent.name, transaction)

                    # Update transaction with the response
                    update_fields = {
                        "normalized_description": response.get(
                            "normalized_description"
                        ),
                        "payee": response.get("payee"),
                        "confidence": response.get("confidence"),
                        "reasoning": response.get("reasoning"),
                        "payee_reasoning": (
                            response.get("reasoning")
                            if task.task_type == "payee_lookup"
                            else None
                        ),
                        "transaction_type": response.get("transaction_type"),
                        "questions": response.get("questions"),
                        "classification_type": response.get("classification_type"),
                        "worksheet": response.get("worksheet"),
                        "business_percentage": response.get("business_percentage"),
                        "payee_extraction_method": (
                            "AI+Search" if task.task_type == "payee_lookup" else None
                        ),
                        "classification_method": (
                            "AI" if task.task_type == "classification" else None
                        ),
                        "business_context": response.get("business_context"),
                        "category": response.get("category"),
                    }

                    # Clean up fields
                    update_fields = {
                        k: v for k, v in update_fields.items() if v is not None
                    }

                    # For payee lookups, only update payee-related fields
                    if task.task_type == "payee_lookup":
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
                        # For classification, ensure personal expenses have correct worksheet
                        if update_fields.get("classification_type") == "personal":
                            update_fields["worksheet"] = "Personal"
                            update_fields["category"] = "Personal"

                    # Update the transaction
                    Transaction.objects.filter(id=transaction.id).update(
                        **update_fields
                    )
                    success_count += 1

                except Exception as e:
                    error_count += 1
                    error_details[str(transaction.id)] = str(e)
                    logger.error(
                        f"Error processing transaction {transaction.id}: {str(e)}"
                    )

                # Update task progress
                task.processed_count = idx
                task.error_count = error_count
                task.error_details = error_details
                task.save()

            # Update final task status
            task.status = "completed" if error_count == 0 else "failed"
            task.save()

            messages.success(
                request,
                f"Task completed: {success_count} successful, {error_count} failed",
            )

        except Exception as e:
            task.status = "failed"
            task.error_details = {"error": str(e)}
            task.save()
            messages.error(request, f"Task failed: {str(e)}")

    run_task.short_description = "Run selected task"

    def retry_failed_tasks(self, request, queryset):
        """Retry failed processing tasks."""
        for task in queryset.filter(status="failed"):
            task.status = "pending"
            task.error_count = 0
            task.error_details = {}
            task.save()
            messages.success(request, f"Retrying task {task.task_id}")
        messages.success(
            request, f"Retried {queryset.filter(status='failed').count()} failed tasks"
        )

    retry_failed_tasks.short_description = "Retry failed tasks"

    def cancel_tasks(self, request, queryset):
        """Cancel selected processing tasks."""
        for task in queryset.filter(status__in=["pending", "processing"]):
            task.status = "failed"
            task.error_details = {
                "cancelled": True,
                "cancelled_at": str(datetime.now()),
            }
            task.save()
            messages.success(request, f"Cancelled task {task.task_id}")
        messages.success(
            request,
            f"Cancelled {queryset.filter(status__in=['pending', 'processing']).count()} tasks",
        )

    cancel_tasks.short_description = "Cancel selected tasks"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:task_id>/transactions/",
                self.admin_site.admin_view(self.view_task_transactions),
                name="profiles_processingtask_transactions",
            ),
        ]
        return custom_urls + urls

    def view_task_transactions(self, request, task_id):
        """View transactions associated with a processing task."""
        task = get_object_or_404(ProcessingTask, task_id=task_id)
        transactions = task.transactions.all()
        return render(
            request,
            "admin/processing_task_transactions.html",
            context={
                "task": task,
                "transactions": transactions,
                "title": f"Transactions for Task {task_id}",
                "opts": self.model._meta,
            },
        )
