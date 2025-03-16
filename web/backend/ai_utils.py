from typing import List
import os
import json
import openai


async def generate_categories(business_description: str) -> str:
    """Generate categories based on business description using OpenAI."""
    try:
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")

        openai.api_key = api_key

        prompt = f"""
        Given the following business description, generate a list of 5-10 relevant transaction categories.
        These categories should be specific to the business type and common transactions they might have.
        
        Business Description: {business_description}
        
        Return ONLY a JSON array of category names. Example: ["Category1", "Category2", "Category3"]
        """

        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial categorization expert.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=200,
        )

        # Extract the category list from the response
        categories = response.choices[0].message.content.strip()

        # Validate that it's proper JSON
        json.loads(categories)

        return categories

    except Exception as e:
        print(f"Error in generate_categories: {e}")
        # Return default categories if OpenAI call fails
        default_categories = ["Income", "Expenses", "Transfers", "Other"]
        return json.dumps(default_categories)
