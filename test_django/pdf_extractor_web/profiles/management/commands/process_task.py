import json
import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
from profiles.models import ProcessingTask, Agent
from ...admin import call_agent


class TaskLogger:
    def __init__(self, log_file):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, level, message, **kwargs):
        entry = {
            "timestamp": timezone.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")


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
                agent = Agent.objects.filter(name__icontains="payee").first()
            else:  # classification
                agent = Agent.objects.filter(name__icontains="classify").first()

            if not agent:
                raise ValueError(f"No agent found for task type {task.task_type}")

            logger.log("info", f"Using agent: {agent.name}")

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
                    )

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
                    transaction.objects.filter(id=transaction.id).update(
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
                    )

                # Update task progress
                task.processed_count = idx
                task.error_count = error_count
                task.error_details = error_details
                task.save()

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
            logger.log("error", f"Task failed: {str(e)}", error=str(e))
            if "task" in locals():
                task.status = "failed"
                task.error_details = {"error": str(e)}
                task.save()
