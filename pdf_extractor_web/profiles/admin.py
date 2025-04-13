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

# Load environment variables
load_dotenv()


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


def call_agent(agent, description):
    """Generic function to call any agent"""
    prompt = agent.prompt
    llm_config = agent.llm

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
        "max_tokens": 150,
        "temperature": 0.7,
    }

    # Make the API call
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()

    # Extract the content from the response
    content = result["choices"][0]["message"]["content"]
    try:
        # Parse the content as JSON
        result = json.loads(content)
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Response parsing failed: {e}")


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
            response = call_agent(agent, transaction.description)

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


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "amount",
        "description",
        "payee",
        "confidence",
        "normalized_description",
        "transaction_type",
        "category",
    )
    list_filter = (
        ClientFilter,
        "transaction_date",
        "category",
        "source",
        "transaction_type",
        "confidence",
    )
    search_fields = (
        "description",
        "category",
        "source",
        "transaction_type",
        "account_number",
        "payee",
        "normalized_description",
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
                    response = call_agent(agent, transaction.description)

                    # Update transaction with the response
                    update_fields = {
                        "normalized_description": response.get(
                            "normalized_description"
                        ),
                        "payee": response.get("payee"),
                        "confidence": response.get("confidence", "low"),
                        "reasoning": response.get("reasoning"),
                        "business_context": response.get("business_context"),
                        "questions": response.get("questions"),
                    }

                    # Remove None values
                    update_fields = {
                        k: v for k, v in update_fields.items() if v is not None
                    }

                    # Update the transaction
                    Transaction.objects.filter(id=transaction.id).update(
                        **update_fields
                    )

                messages.success(
                    request,
                    f"Successfully processed {queryset.count()} transactions with {agent.name}",
                )
            except Exception as e:
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
