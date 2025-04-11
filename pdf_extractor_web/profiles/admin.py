from django.contrib import admin
from .models import (
    BusinessProfile,
    ClientExpenseCategory,
    Transaction,
    LLMConfig,
    Agent,
    Tool,
    NormalizedVendorData,
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
import types
from .tool_discovery import discover_tools, register_tools, get_available_tools

# Load environment variables
load_dotenv()

logger = logging.getLogger("profiles")


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("client_id", "business_type")
    search_fields = ("client_id", "business_description")


@admin.register(ClientExpenseCategory)
class ClientExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name", "client", "category_type", "tax_year", "worksheet")
    list_filter = ("category_type", "tax_year", "worksheet")
    search_fields = ("category_name", "description")


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


def call_payee_agent(description):
    logger.info(f"Calling payee agent for description: {description}")

    # Retrieve the Payee Extractor agent
    payee_agent = Agent.objects.get(name="Payee Extractor")
    prompt = payee_agent.prompt  # Use the prompt from the database
    llm_config = payee_agent.llm

    logger.debug(f"Using LLM config: {llm_config.provider} - {llm_config.model}")
    logger.debug(f"Using prompt: {prompt}")

    # Build the API call using the LLM configuration
    url = llm_config.url
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": description},
        ],
        "max_tokens": 250,  # Increased for more detailed responses
        "temperature": 0.7,
    }

    logger.debug(f"Sending request to LLM with payload: {payload}")

    # Make the API call
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()

    logger.debug(f"Received LLM response: {result}")

    # Extract the content from the response
    content = result["choices"][0]["message"]["content"]
    try:
        # Parse the content as JSON
        result = json.loads(content)
        logger.debug(f"Parsed JSON response: {result}")

        # Adjust the schema to match the actual response format
        response_schema = {
            "type": "object",
            "properties": {
                "payee": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "reasoning": {"type": "string"},
                "needs_search": {"type": "boolean"},
                "transaction_type": {"type": "string"},
                "normalized_description": {"type": "string"},
                "original_context": {"type": "string"},
                "questions": {"type": "string"},
            },
            "required": [
                "payee",
                "confidence",
                "reasoning",
                "needs_search",
                "transaction_type",
                "normalized_description",
                "original_context",
                "questions",
            ],
        }

        # Validate the response
        validate(instance=result, schema=response_schema)
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Response validation failed: {e}")
        raise ValueError(f"Response validation failed: {e}")

    # Map confidence string to numerical value
    confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
    confidence_str = result.get("confidence", "low").lower()
    confidence = confidence_map.get(
        confidence_str, 0.3
    )  # Default to low confidence if unknown value

    # If the LLM indicates it needs to search for vendor information
    vendor_description = result.get("normalized_description", "")
    if result.get("needs_search", False):
        try:
            # Get the Brave Search tool
            brave_tool = Tool.objects.get(name="brave_search")
            # Import the tool module
            module = __import__(brave_tool.module_path, fromlist=["search"])
            # Perform the search
            search_results = module.search(result["payee"])
            if search_results:
                # Use the first result's description
                vendor_description = search_results[0].get("description", "")
                logger.info(
                    f"Found vendor description from search: {vendor_description}"
                )
        except Exception as e:
            logger.error(f"Error using Brave Search tool: {e}")
            vendor_description = "Unable to retrieve vendor description"

    # If no search was performed or it failed, use the normalized description
    if not vendor_description:
        vendor_description = result.get(
            "normalized_description", f"Business transaction with {result['payee']}"
        )

    logger.info(f"Extracted payee: {result.get('payee')} with confidence: {confidence}")

    # Map the response to the expected fields
    return {
        "normalized_name": result.get("payee"),
        "normalized_description": vendor_description,
        "justification": result.get("reasoning"),
        "confidence": confidence,
        "transaction_type": result.get("transaction_type"),
        "original_context": result.get("original_context"),
        "questions": result.get("questions"),
    }


def extract_payee(modeladmin, request, queryset):
    for transaction in queryset:
        logger.info(f"Processing transaction: {transaction.description}")
        response = call_payee_agent(transaction.description)
        logger.info(f"LLM response: {response}")

        normalized_data, created = NormalizedVendorData.objects.update_or_create(
            transaction=transaction,
            defaults={
                "normalized_name": response["normalized_name"],
                "normalized_description": response["normalized_description"],
                "justification": response["justification"],
                "confidence": response["confidence"],
            },
        )
        logger.info(
            f"{'Created' if created else 'Updated'} NormalizedVendorData for transaction {transaction.id}"
        )
        logger.info(f"Stored data: {normalized_data.__dict__}")
    messages.success(request, "Payee extraction completed for selected transactions.")


def force_vendor_lookup(modeladmin, request, queryset):
    try:
        # Get the Brave Search tool
        brave_tool = Tool.objects.get(name="brave_search", is_active=True)
    except Tool.DoesNotExist:
        messages.error(
            request,
            "Brave Search tool not found or is inactive. Please add it through the admin interface.",
        )
        return

    for transaction in queryset:
        try:
            # Get the normalized data if it exists
            normalized_data = transaction.normalized_data
            try:
                # Execute the tool
                search_results = brave_tool.execute(normalized_data.normalized_name)
                if search_results:
                    # Update the description with the search result
                    normalized_data.normalized_description = search_results[0].get(
                        "description", ""
                    )
                    normalized_data.save()
                    logger.info(
                        f"Updated vendor description for {normalized_data.normalized_name}"
                    )
            except Exception as e:
                logger.error(f"Error executing Brave Search tool: {e}")
                messages.error(request, f"Error executing Brave Search tool: {e}")
                return
        except NormalizedVendorData.DoesNotExist:
            messages.warning(
                request, f"No normalized data found for transaction {transaction.id}"
            )
        except Exception as e:
            logger.error(
                f"Error looking up vendor for transaction {transaction.id}: {e}"
            )
            messages.error(
                request,
                f"Error looking up vendor for transaction {transaction.id}: {e}",
            )
    messages.success(request, "Vendor lookups completed for selected transactions.")


force_vendor_lookup.short_description = "Force vendor lookup"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "amount",
        "description",
        "get_normalized_name",
        "get_vendor_description",
        "get_transaction_type",
        "get_reasoning",
        "get_confidence",
        "get_questions",
        "file_path",
        "source",
        "transaction_type",
        "normalized_amount",
        "statement_start_date",
        "statement_end_date",
        "account_number",
        "transaction_id",
    )

    def get_normalized_name(self, obj):
        try:
            return obj.normalized_data.normalized_name
        except NormalizedVendorData.DoesNotExist:
            return "-"

    get_normalized_name.short_description = "Normalized Payee"

    def get_vendor_description(self, obj):
        try:
            return obj.normalized_data.normalized_description
        except NormalizedVendorData.DoesNotExist:
            return "-"

    get_vendor_description.short_description = "Vendor Description"

    def get_transaction_type(self, obj):
        try:
            return obj.normalized_data.transaction_type
        except NormalizedVendorData.DoesNotExist:
            return "-"

    get_transaction_type.short_description = "Transaction Type"

    def get_reasoning(self, obj):
        try:
            return obj.normalized_data.justification
        except NormalizedVendorData.DoesNotExist:
            return "-"

    get_reasoning.short_description = "Extraction Reasoning"

    def get_confidence(self, obj):
        try:
            return f"{obj.normalized_data.confidence:.2f}"
        except NormalizedVendorData.DoesNotExist:
            return "-"

    get_confidence.short_description = "Confidence"

    def get_questions(self, obj):
        try:
            return obj.normalized_data.questions
        except NormalizedVendorData.DoesNotExist:
            return "-"

    get_questions.short_description = "Questions"

    list_filter = (
        ClientFilter,
        "transaction_date",
        "category",
        "source",
        "transaction_type",
    )
    search_fields = (
        "description",
        "category",
        "source",
        "transaction_type",
        "account_number",
        "normalized_data__normalized_name",
        "normalized_data__normalized_description",
    )
    actions = [extract_payee, force_vendor_lookup]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "apply-agent/",
                self.admin_site.admin_view(self.apply_agent_view),
                name="apply-agent",
            ),
        ]
        return custom_urls + urls

    def apply_agent_view(self, request):
        # Placeholder for the view logic to select an agent and apply it
        messages.success(request, "Agent applied to selected transactions.")
        return render(request, "admin/apply_agent.html")

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Add dynamic actions for each agent
        for agent in Agent.objects.all():
            action = create_agent_action(agent)
            actions[action.__name__] = (
                action,
                action.__name__,
                action.short_description,
            )
        return actions


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
    list_display = ("name", "description", "is_active", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    actions = ["activate_tools", "deactivate_tools"]
    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        (
            "Implementation",
            {
                "fields": ("module_path", "code"),
                "description": "Either provide a module path or paste the tool code directly. If both are provided, module_path takes precedence.",
            },
        ),
        (
            "Schema",
            {
                "fields": ("schema",),
                "description": "Optional JSON schema for validating tool responses",
            },
        ),
    )

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "discover/",
                self.admin_site.admin_view(self.discover_tools_view),
                name="discover_tools",
            ),
        ]
        return custom_urls + urls

    def discover_tools_view(self, request):
        """View for discovering tools."""
        logger.info("Discovering tools...")
        try:
            # Log existing tools before discovery
            existing_tools = Tool.objects.all()
            logger.info(
                f"Existing tools before discovery: {list(existing_tools.values_list('name', flat=True))}"
            )

            # Discover and register tools
            register_tools()

            # Log tools after discovery
            all_tools = Tool.objects.all()
            logger.info(
                f"Tools after discovery: {list(all_tools.values_list('name', flat=True))}"
            )

            if all_tools.exists():
                self.message_user(
                    request, "Tools discovered and registered successfully."
                )
            else:
                self.message_user(
                    request,
                    "No tools were discovered. Please check the tools directory.",
                    level=messages.WARNING,
                )
        except Exception as e:
            logger.error(f"Error discovering tools: {e}")
            self.message_user(
                request, f"Error discovering tools: {str(e)}", level=messages.ERROR
            )

        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

    def activate_tools(self, request, queryset):
        """Activate selected tools."""
        logger.info(f"Activating {queryset.count()} tools...")
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} tools.")

    activate_tools.short_description = "Activate selected tools"
    activate_tools.allowed_permissions = ("change",)

    def deactivate_tools(self, request, queryset):
        """Deactivate selected tools."""
        logger.info(f"Deactivating {queryset.count()} tools...")
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} tools.")

    deactivate_tools.short_description = "Deactivate selected tools"
    deactivate_tools.allowed_permissions = ("change",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        logger.info(f"Available actions: {list(actions.keys())}")
        logger.info(f"User permissions: {request.user.get_all_permissions()}")

        # Add our custom actions
        actions["activate_tools"] = (
            self.activate_tools,
            "activate_tools",
            self.activate_tools.short_description,
        )
        actions["deactivate_tools"] = (
            self.deactivate_tools,
            "deactivate_tools",
            self.deactivate_tools.short_description,
        )

        return actions

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_discover_button"] = True
        return super().changelist_view(request, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        # Validate that either module_path or code is provided
        if not obj.module_path and not obj.code:
            raise ValidationError("Either module_path or code must be provided")

        # If code is provided, validate it can be executed
        if obj.code:
            try:
                # Test if the code can be executed
                test_module = types.ModuleType("test")
                exec(obj.code, test_module.__dict__)
                if not hasattr(test_module, "search"):
                    raise ValidationError(
                        "Tool code must implement a 'search' function"
                    )
            except Exception as e:
                raise ValidationError(f"Invalid tool code: {str(e)}")

        # If schema is provided, validate it's valid JSON schema
        if obj.schema:
            try:
                validate(instance={}, schema=obj.schema)
            except ValidationError as e:
                raise ValidationError(f"Invalid schema: {str(e)}")

        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return ("created_at", "updated_at")
        return ()


# Create a dynamic action for each agent
def create_agent_action(agent):
    def agent_action(modeladmin, request, queryset):
        for transaction in queryset:
            try:
                logger.info(
                    f"Processing transaction with agent {agent.name}: {transaction.description}"
                )
                response = call_payee_agent(transaction.description)
                logger.info(f"LLM response: {response}")

                normalized_data, created = (
                    NormalizedVendorData.objects.update_or_create(
                        transaction=transaction,
                        defaults={
                            "normalized_name": response["normalized_name"],
                            "normalized_description": response[
                                "normalized_description"
                            ],
                            "justification": response["justification"],
                            "confidence": response["confidence"],
                            "transaction_type": response.get("transaction_type"),
                            "original_context": response.get("original_context"),
                            "questions": response.get("questions"),
                        },
                    )
                )
                logger.info(
                    f"{'Created' if created else 'Updated'} NormalizedVendorData for transaction {transaction.id}"
                )
                logger.info(f"Stored data: {normalized_data.__dict__}")
            except Exception as e:
                logger.error(
                    f"Error processing transaction {transaction.id} with agent {agent.name}: {e}"
                )
                messages.error(
                    request, f"Error processing transaction {transaction.id}: {e}"
                )
        messages.success(
            request,
            f"Agent '{agent.name}' completed processing for selected transactions.",
        )

    agent_action.__name__ = f"agent_{agent.id}_action"
    agent_action.short_description = f"Process with {agent.name}"
    return agent_action
