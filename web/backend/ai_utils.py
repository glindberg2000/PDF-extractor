from typing import List
import os
import json
import logging
import traceback
from openai import OpenAI

logger = logging.getLogger(__name__)


async def generate_categories(business_description: str) -> list:
    """
    Generate expense categories using OpenAI API based on business description.
    Returns a list of dictionaries with category names and descriptions.
    """
    try:
        logger.info("Starting category generation")
        openai_client = OpenAI()

        response = openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": """You are a financial categorization expert. 
                    Generate relevant expense categories for the given business description. 
                    Return a JSON array of objects with 'name' and 'description' fields.
                    Example: [{"name": "Office Supplies", "description": "Expenses for office materials and supplies"}]""",
                },
                {
                    "role": "user",
                    "content": f"Generate expense categories for a business with this description: {business_description}",
                },
            ],
            temperature=0.7,
            max_tokens=150,
        )

        # Parse categories from response
        try:
            categories = json.loads(response.choices[0].message.content)
            logger.info(f"Successfully generated {len(categories)} categories")
            return categories
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {str(e)}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            raise ValueError("Invalid response format from OpenAI API")

    except Exception as e:
        logger.error(f"Error in generate_categories: {str(e)}")
        logger.error(traceback.format_exc())
        # Return default categories if AI generation fails
        return [
            {"name": "Income", "description": "All income sources"},
            {"name": "Expenses", "description": "General business expenses"},
            {"name": "Transfers", "description": "Money transfers between accounts"},
            {"name": "Other", "description": "Miscellaneous transactions"},
        ]
