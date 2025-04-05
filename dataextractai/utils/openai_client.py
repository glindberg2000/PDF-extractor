"""OpenAI client wrapper for consistent API access."""

import os
from openai import OpenAI
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Wrapper for OpenAI API access."""

    def __init__(self, model_type: str = "precise"):
        """Initialize OpenAI client.

        Args:
            model_type: Either 'fast' or 'precise' to determine which model to use
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)

        # Set model based on type
        self.model = os.getenv(
            "OPENAI_MODEL_PRECISE" if model_type == "precise" else "OPENAI_MODEL_FAST",
            "gpt-4-turbo-preview",  # Default to latest model if env vars not set
        )

    def complete(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Get completion from OpenAI API.

        Args:
            prompt: The prompt to send to the API
            max_tokens: Optional maximum number of tokens to generate

        Returns:
            The generated text response
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant focused on business transaction analysis.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise
