from django.core.management.base import BaseCommand
from django.db.models import Q
from profiles.models import Transaction, Agent
from profiles.admin import call_agent
import logging
from datetime import datetime
import json
import os
from django.conf import settings
import time
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process transactions in batches with progress tracking"

    def add_arguments(self, parser):
        parser.add_argument(
            "--agent", type=str, required=True, help="Name of the agent to use"
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of transactions per batch",
        )
        parser.add_argument(
            "--status-file",
            type=str,
            default="batch_status.json",
            help="File to store progress",
        )
        parser.add_argument(
            "--filter", type=str, help='Filter transactions (e.g., "client_id=123")'
        )

    def handle(self, *args, **options):
        agent_name = options["agent"]
        batch_size = options["batch_size"]
        status_file = options["status_file"]
        filter_str = options["filter"]

        try:
            agent = Agent.objects.get(name=agent_name)
        except Agent.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Agent "{agent_name}" not found'))
            return

        # Initialize status
        status = {
            "start_time": datetime.now().isoformat(),
            "agent": agent_name,
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "current_batch": 0,
            "status": "running",
            "last_update": datetime.now().isoformat(),
            "errors": [],
        }

        # Save initial status
        self._save_status(status_file, status)

        try:
            # Build query
            query = Q()
            if filter_str:
                # Simple filter parsing (can be enhanced)
                field, value = filter_str.split("=")
                query = Q(**{field: value})

            # Get total count
            total_transactions = Transaction.objects.filter(query).count()
            status["total_transactions"] = total_transactions
            self._save_status(status_file, status)

            # Process in batches
            for i in range(0, total_transactions, batch_size):
                batch = Transaction.objects.filter(query)[i : i + batch_size]
                status["current_batch"] = i // batch_size + 1
                status["last_update"] = datetime.now().isoformat()

                for tx in batch:
                    try:
                        with transaction.atomic():
                            response = call_agent(agent.name, tx)

                            # Update transaction
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
                                "classification_type": response.get(
                                    "classification_type"
                                ),
                                "worksheet": response.get("worksheet"),
                                "payee_extraction_method": (
                                    "AI+Search"
                                    if "payee" in agent.name.lower()
                                    else "AI"
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

                            Transaction.objects.filter(id=tx.id).update(**update_fields)
                            status["successful"] += 1
                    except Exception as e:
                        status["failed"] += 1
                        status["errors"].append(
                            {
                                "transaction_id": tx.id,
                                "error": str(e),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        logger.error(f"Error processing transaction {tx.id}: {str(e)}")

                    status["total_processed"] += 1
                    self._save_status(status_file, status)

                # Add a small delay between batches to prevent overwhelming the system
                time.sleep(1)

            status["status"] = "completed"
            status["end_time"] = datetime.now().isoformat()
            self._save_status(status_file, status)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Batch processing completed. Success: {status["successful"]}, Failed: {status["failed"]}'
                )
            )

        except Exception as e:
            status["status"] = "error"
            status["error"] = str(e)
            self._save_status(status_file, status)
            self.stderr.write(
                self.style.ERROR(f"Error during batch processing: {str(e)}")
            )

    def _save_status(self, status_file, status):
        """Save status to file"""
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)
