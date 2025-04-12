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
from django.contrib import admin
import openai
import jsonschema
from tools.vendor_lookup import search
import html
import re

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


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "amount",
        "description",
        "normalized_data__normalized_name",
        "normalized_data__normalized_description",
        "normalized_data__transaction_type",
        "agent_used",
    )
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

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Remove default delete action if it exists
        if "delete_selected" in actions:
            del actions["delete_selected"]

        # Add dynamic actions for each agent
        for agent in Agent.objects.all():
            action = create_agent_action(agent)
            action_name = f"process_with_{agent.name.lower().replace(' ', '_')}"
            action.__name__ = action_name
            action.short_description = f"Process with {agent.name}"
            actions[action_name] = (action, action_name, action.short_description)

        return actions

    def normalized_data__normalized_name(self, obj):
        return (
            obj.normalized_data.normalized_name
            if hasattr(obj, "normalized_data")
            else None
        )

    normalized_data__normalized_name.short_description = "Vendor"

    def normalized_data__normalized_description(self, obj):
        return (
            obj.normalized_data.normalized_description
            if hasattr(obj, "normalized_data")
            else None
        )

    normalized_data__normalized_description.short_description = "Business Type"

    def normalized_data__transaction_type(self, obj):
        return (
            obj.normalized_data.transaction_type
            if hasattr(obj, "normalized_data")
            else None
        )

    normalized_data__transaction_type.short_description = "Transaction Type"

    def agent_used(self, obj):
        if hasattr(obj, "normalized_data") and obj.normalized_data.justification:
            agent_name = obj.normalized_data.justification.split(" - ")[0]
            tools_used = obj.normalized_data.tools_used.get("tools", [])
            if tools_used:
                return f"{agent_name} (with {', '.join(tools_used)})"
            return agent_name
        return None

    agent_used.short_description = "Agent Used"

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


# Process transactions with an agent
def process_with_agent(agent, request, queryset):
    """
    Process transactions using the specified agent.
    The agent's prompt and tools determine how the transactions are processed.
    """
    try:
        # Verify agent has access to required tools
        if not agent.tools.filter(name="brave_search").exists():
            messages.error(
                request,
                f"Agent '{agent.name}' needs access to the brave_search tool. Please add it through the admin interface.",
            )
            return
    except Exception as e:
        messages.error(request, f"Error checking agent tools: {str(e)}")
        return

    success_count = 0
    error_count = 0

    for transaction in queryset:
        try:
            logger.info(
                f"Processing transaction {transaction.id} with agent {agent.name}"
            )
            logger.info(
                f"Agent {agent.name} has access to tools: {[tool.name for tool in agent.tools.all()]}"
            )

            # Make a single LLM call with structured output and tool access
            client = openai.OpenAI()
            conversation = [
                {"role": "system", "content": agent.prompt},
                {"role": "user", "content": transaction.description},
            ]

            tools_used = set()  # Track which tools were used

            while True:
                response = client.chat.completions.create(
                    model=agent.llm.model,
                    messages=conversation,
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "brave_search",
                                "description": "Search for information about a vendor using Brave Search",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "The search query to look up vendor information",
                                        }
                                    },
                                    "required": ["query"],
                                },
                            },
                        }
                    ],
                    tool_choice="auto",
                )

                message = response.choices[0].message
                logger.info(f"Raw LLM response content: {message.content}")

                # Add assistant's message to conversation
                conversation.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": message.tool_calls,
                    }
                )

                # If no tool calls, we're done
                if not message.tool_calls:
                    break

                # Handle tool calls
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "brave_search":
                        tools_used.add("brave_search")
                        # Execute the search
                        args = json.loads(tool_call.function.arguments)
                        logger.info(f"Executing search with query: {args['query']}")
                        search_results = search(args["query"])

                        # Format results for the LLM
                        tool_response = [
                            {
                                "title": result.title,
                                "description": result.description,
                                "url": result.url if result.url else "",
                            }
                            for result in search_results
                        ]

                        logger.info(f"Search results: {tool_response}")

                        # Send results back to LLM
                        conversation.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": json.dumps(tool_response),
                            }
                        )

            # Parse the final response
            try:
                result = json.loads(message.content)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {message.content}")
                error_count += 1
                continue

            # Create or update normalized data
            normalized_data, created = NormalizedVendorData.objects.get_or_create(
                transaction=transaction
            )

            # Update fields
            normalized_data.normalized_name = result["payee"]
            normalized_data.normalized_description = result["normalized_description"]
            normalized_data.transaction_type = result["transaction_type"]
            normalized_data.justification = f"{agent.name} - {result['reasoning']}"
            normalized_data.tools_used = {"tools": list(tools_used)}  # Store tools used
            normalized_data.save()

            success_count += 1
            logger.info(f"Successfully processed transaction {transaction.id}")

        except Exception as e:
            logger.error(f"Error processing transaction {transaction.id}: {str(e)}")
            error_count += 1

    messages.success(
        request,
        f"Agent '{agent.name}' completed processing {success_count} transactions. {error_count} errors occurred.",
    )


# Create a dynamic action for each agent
def create_agent_action(agent):
    def agent_action(modeladmin, request, queryset):
        process_with_agent(agent, request, queryset)

    return agent_action
