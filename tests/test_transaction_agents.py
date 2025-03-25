"""Tests for transaction processing agents."""

import pytest
from dataextractai.agents.transaction_agents import (
    TransactionNormalizationAgent,
    BusinessClassificationAgent,
    process_transaction,
)


@pytest.mark.parametrize("model_type", ["fast", "balanced", "precise"])
def test_transaction_normalization(model_type):
    """Test the transaction normalization agent with different model types."""
    agent = TransactionNormalizationAgent(model_type)
    description = "POS DEBIT 1234*UBER *EATS SAN FRANCISCO CA"

    result, confidence = agent.normalize_transaction(description)

    assert isinstance(result, dict)
    assert "normalized_description" in result
    assert "payee" in result
    assert "transaction_type" in result
    assert "confidence" in result
    assert "original_context" in result
    assert "questions" in result
    assert 0 <= confidence <= 1
    assert agent.model_type == model_type


@pytest.mark.parametrize("model_type", ["fast", "balanced", "precise"])
def test_business_classification(model_type):
    """Test the business classification agent with different model types."""
    agent = BusinessClassificationAgent(model_type)
    normalized_transaction = {
        "normalized_description": "Uber Eats - Food Delivery",
        "payee": "Uber Eats",
        "transaction_type": "Purchase",
        "confidence": 0.95,
        "original_context": "Food delivery service in San Francisco",
        "questions": [],
    }

    client_context = {
        "business_type": "Consulting",
        "industry": "Technology",
        "typical_expenses": ["Meals and Entertainment", "Travel", "Software"],
    }

    result, confidence = agent.classify_transaction(
        normalized_transaction, client_context
    )

    assert isinstance(result, dict)
    assert "classification" in result
    assert "category" in result
    assert "confidence" in result
    assert "business_context" in result
    assert "reasoning" in result
    assert "questions" in result
    assert 0 <= confidence <= 1
    assert agent.model_type == model_type


@pytest.mark.parametrize("model_type", ["fast", "balanced", "precise"])
def test_full_transaction_processing(model_type):
    """Test the complete transaction processing pipeline with different model types."""
    description = "POS DEBIT 1234*UBER *EATS SAN FRANCISCO CA"
    client_context = {
        "business_type": "Consulting",
        "industry": "Technology",
        "typical_expenses": ["Meals and Entertainment", "Travel", "Software"],
    }

    result = process_transaction(description, client_context, model_type=model_type)

    assert isinstance(result, dict)
    assert "normalized_description" in result
    assert "payee" in result
    assert "classification" in result
    assert "category" in result
    assert "overall_confidence" in result
    assert "needs_review" in result
    assert "model_type" in result
    assert "precise_review_used" in result
    assert 0 <= result["overall_confidence"] <= 1
    assert isinstance(result["needs_review"], bool)
    assert result["model_type"] == model_type


def test_precise_review():
    """Test that low confidence transactions trigger precise review."""
    description = "POS DEBIT 1234*UBER *EATS SAN FRANCISCO CA"
    client_context = {
        "business_type": "Consulting",
        "industry": "Technology",
        "typical_expenses": ["Meals and Entertainment", "Travel", "Software"],
    }

    # Test with precise review enabled
    result_with_review = process_transaction(
        description, client_context, model_type="fast", use_precise_for_review=True
    )
    assert "precise_review_used" in result_with_review

    # Test with precise review disabled
    result_without_review = process_transaction(
        description, client_context, model_type="fast", use_precise_for_review=False
    )
    assert not result_without_review["precise_review_used"]
