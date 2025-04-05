"""Business rules manager with AI assistance."""

import logging
from typing import Dict, List, Optional, Any
from ..db.client_db import ClientDB
from ..utils.openai_client import OpenAIClient
import json

logger = logging.getLogger(__name__)


class BusinessRulesManager:
    """Manages business rules with AI assistance."""

    def __init__(self, client_name: str, model_type: str = "precise"):
        """Initialize the business rules manager.

        Args:
            client_name: Name of the client
            model_type: Type of model to use ('fast' or 'precise')
        """
        self.client_name = client_name
        self.db = ClientDB()
        self.ai_client = OpenAIClient(model_type)

    def analyze_and_generate_rules(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze transactions and generate business rules.

        This method:
        1. Groups similar transactions
        2. Identifies patterns
        3. Generates rules based on patterns
        4. Validates rules against existing data
        5. Saves high-confidence rules

        Args:
            transactions: List of transaction dictionaries

        Returns:
            List of generated rules
        """
        # Prepare transaction data for analysis
        analysis_data = self._prepare_analysis_data(transactions)

        # Generate AI prompt for rule analysis
        prompt = self._generate_analysis_prompt(analysis_data)

        # Get AI response
        response = self.ai_client.complete(prompt)

        # Parse and validate rules from AI response
        rules = self._parse_rules_from_response(response)

        # Validate rules against transaction data
        validated_rules = self._validate_rules(rules, transactions)

        # Save valid rules
        for rule in validated_rules:
            self.db.save_business_rule(self.client_name, rule)

        return validated_rules

    def _prepare_analysis_data(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare transaction data for AI analysis."""
        # Group transactions by various criteria
        analysis = {
            "by_payee": {},
            "by_category": {},
            "by_amount_range": {},
            "patterns": {
                "recurring_amounts": [],
                "similar_descriptions": [],
                "category_correlations": [],
            },
        }

        for txn in transactions:
            # Group by payee
            payee = txn.get("payee")
            if payee:
                if payee not in analysis["by_payee"]:
                    analysis["by_payee"][payee] = []
                analysis["by_payee"][payee].append(txn)

            # Group by category
            category = txn.get("base_category")
            if category:
                if category not in analysis["by_category"]:
                    analysis["by_category"][category] = []
                analysis["by_category"][category].append(txn)

            # Group by amount range
            amount = txn.get("amount", 0)
            range_key = f"{int(amount/100)*100}-{int(amount/100)*100 + 99}"
            if range_key not in analysis["by_amount_range"]:
                analysis["by_amount_range"][range_key] = []
            analysis["by_amount_range"][range_key].append(txn)

        return analysis

    def _generate_analysis_prompt(self, analysis_data: Dict[str, Any]) -> str:
        """Generate AI prompt for rule analysis."""
        prompt = """Please analyze the following transaction patterns and generate business rules. 
        Focus on:
        1. Category patterns (e.g., all fast food should be 50% business)
        2. Payee patterns (e.g., specific vendors always business-related)
        3. Amount patterns (e.g., transactions over $1000 need review)
        4. Composite patterns (combinations of the above)

        For each rule, provide:
        - Rule type (category/payee/amount/composite)
        - Conditions for matching
        - Actions to take
        - Confidence level
        - Reasoning

        Transaction Analysis Data:
        """

        prompt += json.dumps(analysis_data, indent=2)

        return prompt

    def _parse_rules_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse and structure rules from AI response."""
        try:
            # Parse the JSON response into structured rules
            rules_data = json.loads(response)

            structured_rules = []
            for rule in rules_data:
                structured_rule = {
                    "rule_type": rule["type"],
                    "rule_name": rule["name"],
                    "rule_description": rule["description"],
                    "conditions": rule["conditions"],
                    "actions": rule["actions"],
                    "priority": rule.get("priority", 0),
                    "ai_generated": True,
                    "ai_confidence": rule["confidence"],
                    "ai_reasoning": rule["reasoning"],
                }
                structured_rules.append(structured_rule)

            return structured_rules

        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON")
            return []
        except KeyError as e:
            logger.error(f"Missing required field in rule: {e}")
            return []

    def _validate_rules(
        self, rules: List[Dict[str, Any]], transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate generated rules against transaction data."""
        validated_rules = []

        for rule in rules:
            # Test rule against transactions
            matches = 0
            total_applicable = 0

            for txn in transactions:
                if self._rule_applies_to_transaction(rule, txn):
                    total_applicable += 1
                    if self._rule_matches_existing_classification(rule, txn):
                        matches += 1

            # Calculate accuracy
            accuracy = matches / total_applicable if total_applicable > 0 else 0

            # Accept rules with high accuracy or strong AI confidence
            if (accuracy >= 0.9) or (
                accuracy >= 0.7 and rule["ai_confidence"] == "high"
            ):
                validated_rules.append(rule)

        return validated_rules

    def _rule_applies_to_transaction(
        self, rule: Dict[str, Any], transaction: Dict[str, Any]
    ) -> bool:
        """Check if a rule's conditions apply to a transaction."""
        conditions = rule["conditions"]

        for condition in conditions:
            field = condition["field"]
            operator = condition["operator"]
            value = condition["value"]

            if field not in transaction:
                return False

            txn_value = transaction[field]

            if operator == "equals":
                if txn_value != value:
                    return False
            elif operator == "contains":
                if value not in str(txn_value):
                    return False
            elif operator == "greater_than":
                if not (isinstance(txn_value, (int, float)) and txn_value > value):
                    return False
            elif operator == "less_than":
                if not (isinstance(txn_value, (int, float)) and txn_value < value):
                    return False

        return True

    def _rule_matches_existing_classification(
        self, rule: Dict[str, Any], transaction: Dict[str, Any]
    ) -> bool:
        """Check if a rule's actions match existing transaction classification."""
        actions = rule["actions"]

        for action in actions:
            field = action["field"]
            value = action["value"]

            if field in transaction and transaction[field] != value:
                return False

        return True

    def apply_rules_to_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all applicable rules to a transaction.

        Rules are applied in priority order. Higher priority rules can override
        lower priority rules.
        """
        # Get active rules
        rules = self.db.get_business_rules(self.client_name, active_only=True)

        # Sort by priority (highest first)
        rules.sort(key=lambda x: x["priority"], reverse=True)

        modified_transaction = transaction.copy()

        for rule in rules:
            if self._rule_applies_to_transaction(rule, transaction):
                # Apply rule actions
                for action in rule["actions"]:
                    field = action["field"]
                    value = action["value"]
                    modified_transaction[field] = value

        return modified_transaction

    def get_rule_suggestions(self, transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get suggested rules for a transaction.

        This is useful during review to suggest new rules based on
        manual changes made to transactions.
        """
        # Prepare single transaction for analysis
        analysis_data = self._prepare_analysis_data([transaction])

        # Generate focused prompt for rule suggestions
        prompt = """Please analyze this transaction and suggest business rules that could be applied to similar transactions.
        Consider:
        1. The payee and similar payees
        2. The category and related categories
        3. The transaction amount and similar amounts
        4. Any combinations of these factors

        Transaction Data:
        """

        prompt += json.dumps(transaction, indent=2)

        # Get AI suggestions
        response = self.ai_client.complete(prompt)

        # Parse and return suggested rules
        return self._parse_rules_from_response(response)
