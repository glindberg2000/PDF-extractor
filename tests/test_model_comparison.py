"""Test model comparison functionality."""

import pytest
from dataextractai.agents.transaction_agents import process_transaction


def test_model_comparison():
    """Test that both models process transactions and provide comparison data."""
    description = "POS DEBIT 1234*UBER *EATS SAN FRANCISCO CA"
    client_context = {
        "business_type": "Consulting",
        "industry": "Technology",
        "typical_expenses": ["Meals and Entertainment", "Travel", "Software"],
    }

    # Test with model comparison
    results = process_transaction(
        description=description, client_context=client_context, compare_models=True
    )

    # Verify both models provided results
    assert "fast" in results
    assert "precise" in results
    assert "comparison" in results

    # Verify fast model results
    fast_result = results["fast"]
    assert "normalized_description" in fast_result
    assert "payee" in fast_result
    assert "classification" in fast_result
    assert "category" in fast_result
    assert "overall_confidence" in fast_result
    assert "model_type" in fast_result
    assert fast_result["model_type"] == "fast"

    # Verify precise model results
    precise_result = results["precise"]
    assert "normalized_description" in precise_result
    assert "payee" in precise_result
    assert "classification" in precise_result
    assert "category" in precise_result
    assert "overall_confidence" in precise_result
    assert "model_type" in precise_result
    assert precise_result["model_type"] == "precise"

    # Verify comparison data
    comparison = results["comparison"]
    assert "confidence_difference" in comparison
    assert "classification_match" in comparison
    assert "category_match" in comparison
    assert "recommended_model" in comparison
    assert comparison["recommended_model"] in ["fast", "precise"]

    # Print results for manual inspection
    print("\nFast Model Results:")
    print(f"Normalized: {fast_result['normalized_description']}")
    print(f"Classification: {fast_result['classification']}")
    print(f"Category: {fast_result['category']}")
    print(f"Confidence: {fast_result['overall_confidence']}")

    print("\nPrecise Model Results:")
    print(f"Normalized: {precise_result['normalized_description']}")
    print(f"Classification: {precise_result['classification']}")
    print(f"Category: {precise_result['category']}")
    print(f"Confidence: {precise_result['overall_confidence']}")

    print("\nComparison:")
    print(f"Confidence Difference: {comparison['confidence_difference']}")
    print(f"Classification Match: {comparison['classification_match']}")
    print(f"Category Match: {comparison['category_match']}")
    print(f"Recommended Model: {comparison['recommended_model']}")
