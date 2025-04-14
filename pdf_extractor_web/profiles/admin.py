from django.contrib import admin
from django.utils.html import format_html, format_html_join
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
    ClassificationOverride,
)
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
import json
from jsonschema import validate, ValidationError
import requests
import os
from dotenv import load_dotenv
from django.views.decorators.http import require_POST

# Load environment variables
load_dotenv()


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
        "response_format": {"type": "json_object"},  # Force JSON response
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
        print(f"Raw response content: {content}")  # Debug logging
        raise ValueError(f"Response parsing failed: {e}. Raw content: {content}")


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


def construct_classification_prompt(transaction, business_profile):
    """Construct a prompt for classifying a transaction using business profile data."""
    prompt = f"Transaction Details:\n"
    prompt += f"- Date: {transaction.transaction_date}\n"
    prompt += f"- Amount: ${transaction.amount}\n"
    prompt += f"- Payee: {transaction.payee}\n"
    prompt += f"- Description: {transaction.description}\n\n"

    prompt += f"Business Context:\n"
    if business_profile.business_type:
        prompt += f"- Type: {business_profile.business_type}\n"
    if business_profile.business_description:
        prompt += f"- Description: {business_profile.business_description}\n"

    # Add industry keywords if available
    if business_profile.industry_keywords:
        prompt += "\nIndustry Keywords:\n"
        for keyword in business_profile.industry_keywords:
            prompt += f"- {keyword}\n"

    # Add classification rules if available
    if business_profile.category_patterns:
        prompt += "\nClassification Rules:\n"
        for pattern, category in business_profile.category_patterns.items():
            prompt += f"- {pattern} -> {category}\n"

    # Add common business expenses if available
    if business_profile.common_expenses:
        prompt += "\nCommon Business Expenses:\n"
        for expense in business_profile.common_expenses:
            prompt += f"- {expense}\n"

    # Add custom business categories if available
    if business_profile.custom_categories:
        prompt += "\nCustom Business Categories:\n"
        for category in business_profile.custom_categories:
            prompt += f"- {category}\n"

    # Add any additional business info
    if business_profile.additional_info:
        prompt += "\nAdditional Business Information:\n"
        for key, value in business_profile.additional_info.items():
            prompt += f"- {key}: {value}\n"

    # Add the agent's prompt at the end
    agent = Agent.objects.get(name="Classify Agent")
    prompt += f"\n{agent.prompt}"

    return prompt


def classify_transactions(modeladmin, request, queryset):
    """Process selected transactions with the Classify Agent"""
    # Filter to only transactions with payee data
    transactions = queryset.filter(payee__isnull=False)
    if not transactions:
        messages.error(
            request,
            "No transactions with payee data selected. Please process payee data first.",
        )
        return HttpResponseRedirect(request.get_full_path())

    try:
        classify_agent = Agent.objects.get(name="Classify Agent")
        for transaction in transactions:
            business_profile = transaction.client
            prompt = construct_classification_prompt(transaction, business_profile)
            print(f"Classification prompt: {prompt}")  # Debug logging
            response = call_agent(classify_agent, prompt)
            print(f"Classification response: {response}")  # Debug logging

            # Create new classification
            TransactionClassification.objects.create(
                transaction=transaction,
                classification_type=response.get("classification_type", "unclassified"),
                worksheet=response.get("worksheet", "None"),
                confidence=response.get("confidence", "low"),
                reasoning=response.get("reasoning", ""),
                created_by=classify_agent.name,
                is_active=True,
            )

        messages.success(
            request,
            f"Successfully classified {transactions.count()} transactions",
        )
    except Agent.DoesNotExist:
        messages.error(request, "Classify Agent not found. Please create it first.")
    except Exception as e:
        messages.error(request, f"Error classifying transactions: {str(e)}")

    return HttpResponseRedirect(request.get_full_path())


classify_transactions.short_description = "Classify transactions with Classify Agent"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "amount",
        "get_compact_description",
        "get_compact_normalized_description",
        "payee",
        "get_classification_summary",
        "get_confidence_level",
        "transaction_type",
        "source",
    )
    list_filter = ("client", "transaction_date", "transaction_type", "source")
    search_fields = ("description", "normalized_description", "payee", "source")
    readonly_fields = (
        "transaction_date",
        "amount",
        "description",
        "normalized_description",
        "payee",
        "confidence",
        "reasoning",
        "business_context",
        "questions",
        "get_classification_details",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "transaction_date",
                    "amount",
                    "description",
                    "normalized_description",
                    "payee",
                    "transaction_type",
                    "source",
                ),
            },
        ),
        (
            "Processing Information",
            {
                "fields": (
                    "confidence",
                    "reasoning",
                    "business_context",
                    "questions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Classification",
            {
                "fields": ("get_classification_details",),
            },
        ),
    )

    def get_compact_description(self, obj):
        """Display description in a single line with ellipsis."""
        max_length = 50
        description = obj.description or ""
        if len(description) > max_length:
            return format_html(
                '<span title="{}">{}&hellip;</span>',
                description,
                description[:max_length],
            )
        return description

    get_compact_description.short_description = "Description"

    def get_compact_normalized_description(self, obj):
        """Display normalized description in a single line with ellipsis."""
        max_length = 50
        description = obj.normalized_description or ""
        if len(description) > max_length:
            return format_html(
                '<span title="{}">{}&hellip;</span>',
                description,
                description[:max_length],
            )
        return description

    get_compact_normalized_description.short_description = "Normalized Description"

    def get_classification_summary(self, obj):
        """Display a concise summary of the current classification."""
        current = obj.current_classification
        if not current:
            return "-"
        return format_html("{} ({})", current.classification_type, current.worksheet)

    get_classification_summary.short_description = "Classification"

    def get_confidence_level(self, obj):
        """Display confidence level with color coding."""
        current = obj.current_classification
        if not current:
            return "-"

        colors = {"high": "#28a745", "medium": "#ffc107", "low": "#dc3545"}
        color = colors.get(current.confidence.lower(), "#6c757d")

        return format_html(
            '<span style="color: {};">{}</span>', color, current.confidence
        )

    get_confidence_level.short_description = "Confidence"

    def get_classification_details(self, obj):
        """Display detailed classification information with override form."""
        current = obj.current_classification
        if not current:
            return format_html("<p>No classification available</p>")

        # Get classification history
        history = obj.classification_history.select_related("transaction")
        history_html = format_html_join(
            "\n",
            '<div style="margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px;">'
            "<strong>{}</strong> - {} ({}) by {}<br>"
            "<div style='margin-top: 5px;'>{}</div></div>",
            (
                (
                    h.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    h.classification_type,
                    h.worksheet,
                    h.created_by,
                    h.reasoning,
                )
                for h in history
            ),
        )

        # Get overrides
        overrides = obj.classification_overrides.all()
        overrides_html = (
            format_html_join(
                "\n",
                '<div style="margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px;">'
                "<strong>{}</strong> - Changed to {} ({}) by {}"
                "{}</div>",
                (
                    (
                        o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        o.new_classification_type,
                        o.new_worksheet,
                        o.created_by,
                        (
                            format_html(
                                "<br><div style='margin-top: 5px;'>Note: {}</div>",
                                o.notes,
                            )
                            if o.notes
                            else ""
                        ),
                    )
                    for o in overrides
                ),
            )
            if overrides.exists()
            else format_html("<p>No overrides yet.</p>")
        )

        # Get available worksheets
        worksheets = IRSWorksheet.objects.filter(is_active=True)
        worksheet_choices = [(w.name, w.name) for w in worksheets]

        # Get available categories based on worksheet
        categories = IRSExpenseCategory.objects.filter(
            worksheet__name=current.worksheet, is_active=True
        ).order_by("line_number")
        category_choices = [
            (c.name, f"{c.name} (Line {c.line_number})") for c in categories
        ]

        # Add business-specific categories if available
        if obj.client:
            business_categories = BusinessExpenseCategory.objects.filter(
                business=obj.client, worksheet__name=current.worksheet, is_active=True
            )
            category_choices.extend(
                [(c.category_name, c.category_name) for c in business_categories]
            )

        # Create override form
        override_form = format_html(
            """
            <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                <h4 style="margin-top: 0;">Override Classification</h4>
                <form id="override-form-{}" class="classification-override-form">
                    <div style="margin-bottom: 10px;">
                        <label style="display: block; margin-bottom: 5px;">New Classification Type:</label>
                        <select name="new_classification_type" style="width: 100%; padding: 5px;">
                            <option value="business">Business</option>
                            <option value="personal">Personal</option>
                        </select>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <label style="display: block; margin-bottom: 5px;">New Worksheet:</label>
                        <select name="new_worksheet" style="width: 100%; padding: 5px;">
                            {}
                        </select>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <label style="display: block; margin-bottom: 5px;">Category:</label>
                        <select name="category" style="width: 100%; padding: 5px;">
                            {}
                        </select>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <label style="display: block; margin-bottom: 5px;">Notes:</label>
                        <textarea name="notes" style="width: 100%; padding: 5px;"></textarea>
                    </div>
                    <button type="submit" style="background-color: #007bff; color: white; 
                            border: none; padding: 8px 15px; border-radius: 3px;">
                        Submit Override
                    </button>
                </form>
            </div>
            <script>
                (function() {{
                    document.getElementById('override-form-{}').addEventListener('submit', function(e) {{
                        e.preventDefault();
                        const formData = new FormData(e.target);
                        fetch('/admin/profiles/transaction/{}/override/', {{
                            method: 'POST',
                            body: formData,
                            headers: {{
                                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                            }}
                        }})
                        .then(response => response.json())
                        .then(data => {{
                            if (data.success) {{
                                location.reload();
                            }} else {{
                                alert('Error: ' + data.error);
                            }}
                        }});
                    }});
                }})();
            </script>
            """,
            obj.id,
            format_html_join(
                "\n",
                '<option value="{}">{}</option>',
                worksheet_choices,
            ),
            format_html_join(
                "\n",
                '<option value="{}">{}</option>',
                category_choices,
            ),
            obj.id,
            obj.id,
        )

        return format_html(
            """
            <div style="display: grid; grid-template-columns: 1fr; gap: 20px;">
                <div>
                    <h3 style="margin-top: 0;">Current Classification</h3>
                    <div style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                        <strong>Type:</strong> {}<br>
                        <strong>Worksheet:</strong> {}<br>
                        <strong>Category:</strong> {}<br>
                        <strong>Confidence:</strong> {}<br>
                        <strong>Created By:</strong> {} at {}<br>
                        <div style="margin-top: 10px;">
                            <strong>Reasoning:</strong><br>
                            {}
                        </div>
                    </div>
                    
                    <h3>Classification History</h3>
                    <div style="margin-bottom: 20px;">
                        {}
                    </div>
                    
                    <h3>Override History</h3>
                    <div style="margin-bottom: 20px;">
                        {}
                    </div>
                    
                    {}
                </div>
            </div>
            """,
            current.classification_type,
            current.worksheet,
            current.category or "Not set",
            current.confidence,
            current.created_by,
            current.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            current.reasoning,
            history_html,
            overrides_html,
            override_form,
        )

    get_classification_details.short_description = "Classification Details"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:transaction_id>/override/",
                self.admin_site.admin_view(self.override_classification),
                name="transaction-override",
            ),
        ]
        return custom_urls + urls

    @require_POST
    def override_classification(self, request, transaction_id):
        try:
            transaction = Transaction.objects.get(id=transaction_id)
            current_classification = transaction.current_classification

            if not current_classification:
                return JsonResponse(
                    {"success": False, "error": "No current classification to override"}
                )

            override = ClassificationOverride.objects.create(
                transaction=transaction,
                original_classification=current_classification,
                new_classification_type=request.POST.get("new_classification_type"),
                new_worksheet=request.POST.get("new_worksheet"),
                notes=request.POST.get("notes", ""),
                created_by=request.user.get_full_name() or request.user.username,
            )

            # Create a new classification based on the override
            new_classification = TransactionClassification.objects.create(
                transaction=transaction,
                classification_type=override.new_classification_type,
                worksheet=override.new_worksheet,
                confidence="high",  # Manual overrides are considered high confidence
                reasoning=f"Manual override by {override.created_by}. Notes: {override.notes}",
                created_by=override.created_by,
                is_active=True,  # This will automatically deactivate the current classification
            )

            messages.success(request, "Classification successfully overridden")
            return JsonResponse({"success": True})

        except Transaction.DoesNotExist:
            return JsonResponse({"success": False, "error": "Transaction not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})


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
    list_display = ("name", "description", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(IRSExpenseCategory)
class IRSExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "worksheet", "line_number", "is_active", "updated_at")
    list_filter = ("worksheet", "is_active")
    search_fields = ("name", "description", "line_number")
    ordering = ("worksheet", "line_number")


@admin.register(BusinessExpenseCategory)
class BusinessExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "category_name",
        "business",
        "worksheet",
        "parent_category",
        "tax_year",
        "is_active",
        "updated_at",
    )
    list_filter = ("worksheet", "business", "tax_year", "is_active")
    search_fields = ("category_name", "description", "business__client_id")
    ordering = ("business", "worksheet", "category_name")
    raw_id_fields = ("business", "worksheet", "parent_category")
