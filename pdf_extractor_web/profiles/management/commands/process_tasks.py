from django.core.management.base import BaseCommand
from profiles.models import ProcessingTask, Transaction, Agent
from profiles.admin import call_agent
import logging
import traceback

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process pending tasks from the ProcessingTask queue"

    def handle(self, *args, **options):
        # Get all pending tasks
        pending_tasks = ProcessingTask.objects.filter(status="pending")

        self.stdout.write(f"Found {pending_tasks.count()} pending tasks")

        if not pending_tasks.exists():
            self.stdout.write(self.style.WARNING("No pending tasks found"))
            return

        for task in pending_tasks:
            try:
                self.stdout.write(
                    f"Processing task {task.task_id} of type {task.task_type}"
                )

                # Update status to processing
                task.status = "processing"
                task.save()

                # Get transaction IDs from metadata
                transaction_ids = task.task_metadata.get("transaction_ids", [])
                self.stdout.write(
                    f"Found {len(transaction_ids)} transactions to process"
                )

                transactions = Transaction.objects.filter(id__in=transaction_ids)
                self.stdout.write(
                    f"Retrieved {transactions.count()} transactions from database"
                )

                # Get the appropriate agent based on task type
                try:
                    # For payee lookup, use the agent with 'payee' in name and 'lookup' in purpose
                    if task.task_type == "payee_lookup":
                        agent = Agent.objects.get(
                            name__icontains="payee", purpose__icontains="lookup"
                        )
                    else:  # classification
                        agent = Agent.objects.get(
                            name__icontains="classify",
                            purpose__icontains="classify",
                        )
                    self.stdout.write(
                        f"Using agent: {agent.name} (purpose: {agent.purpose})"
                    )
                except Agent.DoesNotExist:
                    error_msg = f"No agent found for task type: {task.task_type}. Looking for agent with name containing 'classify' for classification tasks."
                    logger.error(error_msg)
                    self.stdout.write(self.style.ERROR(error_msg))
                    task.status = "failed"
                    task.error_details = {"agent_error": error_msg}
                    task.save()
                    continue
                except Agent.MultipleObjectsReturned:
                    error_msg = f"Multiple agents found for task type: {task.task_type}. Please specify a unique agent."
                    logger.error(error_msg)
                    self.stdout.write(self.style.ERROR(error_msg))
                    task.status = "failed"
                    task.error_details = {"agent_error": error_msg}
                    task.save()
                    continue

                # Process each transaction
                for transaction in transactions:
                    try:
                        self.stdout.write(
                            f"Processing transaction {transaction.id}: {transaction.description}"
                        )
                        response = call_agent(agent.name, transaction)

                        # Update transaction based on task type
                        if task.task_type == "payee_lookup":
                            update_fields = {
                                "normalized_description": response.get(
                                    "normalized_description"
                                ),
                                "payee": response.get("payee"),
                                "confidence": response.get("confidence"),
                                "payee_reasoning": response.get("reasoning"),
                                "transaction_type": response.get("transaction_type"),
                                "questions": response.get("questions"),
                                "payee_extraction_method": "AI+Search",
                            }
                        else:  # classification
                            update_fields = {
                                "classification_type": response.get(
                                    "classification_type"
                                ),
                                "worksheet": response.get("worksheet"),
                                "category": response.get("category"),
                                "confidence": response.get("confidence"),
                                "reasoning": response.get("reasoning"),
                                "questions": response.get("questions"),
                                "business_percentage": response.get(
                                    "business_percentage"
                                ),
                                "classification_method": "AI",
                            }

                        # Clean up fields (remove None values)
                        update_fields = {
                            k: v for k, v in update_fields.items() if v is not None
                        }
                        self.stdout.write(
                            f"Updating transaction with fields: {update_fields}"
                        )

                        # Update the transaction
                        Transaction.objects.filter(id=transaction.id).update(
                            **update_fields
                        )

                        # Update processed count
                        task.processed_count += 1
                        task.save()
                        self.stdout.write(
                            f"Successfully processed transaction {transaction.id}"
                        )

                    except Exception as e:
                        error_msg = (
                            f"Error processing transaction {transaction.id}: {str(e)}"
                        )
                        logger.error(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))
                        task.error_count += 1
                        task.error_details = task.error_details or {}
                        task.error_details[str(transaction.id)] = str(e)
                        task.save()

                # Mark task as completed
                task.status = "completed"
                task.save()

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully processed task {task.task_id}")
                )

            except Exception as e:
                error_msg = f"Error processing task {task.task_id}: {str(e)}"
                logger.error(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))
                task.status = "failed"
                task.error_details = task.error_details or {}
                task.error_details["task_error"] = str(e)
                task.save()
