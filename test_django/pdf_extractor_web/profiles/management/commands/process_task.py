import json
import logging
import importlib.util
import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from profiles.models import ProcessingTask, Agent, Tool, Transaction
from ...admin import call_agent
import traceback

# Configure logging to output to console
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)
logger.addHandler(console_handler)


class TaskLogger:
    def __init__(self, log_file):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def log(self, level, message, **kwargs):
        # Create the log entry
        entry = {
            "timestamp": timezone.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs,
        }

        # Write to file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Also log to console
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"{message} {json.dumps(kwargs) if kwargs else ''}")


class Command(BaseCommand):
    help = "Process a batch processing task"

    def add_arguments(self, parser):
        parser.add_argument("task_id", type=str, help="UUID of the task to process")
        parser.add_argument(
            "--log-file", type=str, help="Path to the log file", required=True
        )

    def handle(self, *args, **options):
        task_id = options["task_id"]
        logger = TaskLogger(options["log_file"])

        try:
            # Get the task
            task = ProcessingTask.objects.get(task_id=task_id)
            logger.log("info", f"Starting task {task_id}", task_type=task.task_type)

            # Get the appropriate agent
            if task.task_type == "payee_lookup":
                # First try to get the agent from task metadata
                agent_id = task.task_metadata.get("agent_id")
                if agent_id:
                    agent = Agent.objects.get(id=agent_id)
                else:
                    # Fall back to getting the specific "Lookup Payee" agent
                    agent = Agent.objects.get(name="Lookup Payee")
            else:  # classification
                agent = Agent.objects.filter(name__icontains="classify").first()

            if not agent:
                raise ValueError(f"No agent found for task type {task.task_type}")

            logger.log("info", f"Using agent: {agent.name}")
            logger.log(
                "info", "Agent tools:", tools=[t.name for t in agent.tools.all()]
            )

            # Process each transaction
            total = task.transactions.count()
            success_count = 0
            error_count = 0
            error_details = {}

            for idx, transaction in enumerate(task.transactions.all(), 1):
                try:
                    logger.log(
                        "info",
                        f"Processing transaction {idx}/{total}",
                        transaction_id=transaction.id,
                        description=transaction.description,
                    )

                    # Call the agent using the exact same code path as admin.py
                    response = call_agent(agent.name, transaction)
                    logger.log("info", "Got response from agent", response=response)

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
                    logger.log(
                        "info",
                        "Transaction processed successfully",
                        transaction_id=transaction.id,
                        **update_fields,
                    )

                except Exception as e:
                    error_count += 1
                    error_details[str(transaction.id)] = str(e)
                    logger.log(
                        "error",
                        f"Error processing transaction: {str(e)}",
                        transaction_id=transaction.id,
                        error=str(e),
                        traceback=traceback.format_exc(),
                    )

                # Update task progress
                task.processed_count = idx
                task.error_count = error_count
                task.error_details = error_details
                task.save()
                logger.log(
                    "info",
                    "Updated task progress",
                    processed=idx,
                    total=total,
                    errors=error_count,
                )

            # Update final task status
            task.status = "completed" if error_count == 0 else "failed"
            task.save()

            logger.log(
                "info",
                "Task completed",
                success_count=success_count,
                error_count=error_count,
            )

        except Exception as e:
            logger.log(
                "error",
                f"Task failed: {str(e)}",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            if "task" in locals():
                task.status = "failed"
                task.error_details = {"error": str(e)}
                task.save()
