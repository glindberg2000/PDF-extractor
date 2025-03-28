"""Client profile manager for handling business context and categorization."""

import os
import json
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Get model configurations from environment
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
OPENAI_MODEL_PRECISE = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")


class ClientProfileManager:
    """Manages client business profiles and transaction categorization."""

    def __init__(self, client_name: str):
        self.client_name = client_name
        self.client_dir = os.path.join("data", "clients", client_name)
        self.profile_file = os.path.join(self.client_dir, "business_profile.json")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def create_or_update_profile(
        self,
        business_type: str,
        business_description: str,
        custom_categories: Optional[List[str]] = None,
    ) -> Dict:
        """Create or update a client's business profile using AI."""
        # Load existing profile if it exists
        existing_profile = self._load_profile()

        # Prepare profile data
        profile_data = {
            "business_type": business_type,
            "business_description": business_description,
            "custom_categories": custom_categories or [],
            "last_updated": None,
        }

        # Generate AI-enhanced profile
        enhanced_profile = self._enhance_profile_with_ai(profile_data)

        # Merge with existing profile if it exists
        if existing_profile:
            enhanced_profile = self._merge_profiles(existing_profile, enhanced_profile)

        # Save the enhanced profile
        self._save_profile(enhanced_profile)

        return enhanced_profile

    def _enhance_profile_with_ai(self, profile_data: Dict) -> Dict:
        """Use AI to enhance the business profile with categories and context."""
        prompt = f"""As a business analysis expert, please enhance this business profile:

Business Type: {profile_data['business_type']}
Description: {profile_data['business_description']}
Custom Categories: {', '.join(profile_data['custom_categories']) if profile_data['custom_categories'] else 'None'}

Please provide:
1. A comprehensive list of typical expense categories for this business type
2. Common transaction patterns and descriptions to expect
3. Industry-specific insights and considerations
4. Suggested category hierarchy
5. Any additional business context that would help with transaction categorization

Return the response as a JSON object with the following structure:
{{
    "business_type": "string",
    "business_description": "string",
    "custom_categories": ["string"],
    "ai_generated_categories": ["string"],
    "common_patterns": ["string"],
    "industry_insights": "string",
    "category_hierarchy": {{
        "main_categories": ["string"],
        "subcategories": {{
            "category_name": ["string"]
        }}
    }},
    "business_context": "string",
    "last_updated": "timestamp"
}}"""

        response = self.client.chat.completions.create(
            model=OPENAI_MODEL_PRECISE,  # Use precise model for profile enhancement
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analysis expert specializing in expense categorization and transaction analysis.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        enhanced_profile = json.loads(response.choices[0].message.content)

        # Merge with original profile data
        enhanced_profile.update(
            {
                "business_type": profile_data["business_type"],
                "business_description": profile_data["business_description"],
                "custom_categories": profile_data["custom_categories"],
            }
        )

        return enhanced_profile

    def _merge_profiles(self, existing: Dict, enhanced: Dict) -> Dict:
        """Merge existing profile with enhanced profile, preserving important custom data."""
        merged = existing.copy()

        # Update with enhanced data
        merged.update(
            {
                "ai_generated_categories": enhanced["ai_generated_categories"],
                "common_patterns": enhanced["common_patterns"],
                "industry_insights": enhanced["industry_insights"],
                "category_hierarchy": enhanced["category_hierarchy"],
                "business_context": enhanced["business_context"],
                "last_updated": enhanced["last_updated"],
            }
        )

        # Preserve custom categories
        merged["custom_categories"] = list(
            set(
                existing.get("custom_categories", [])
                + enhanced.get("custom_categories", [])
            )
        )

        return merged

    def _load_profile(self) -> Optional[Dict]:
        """Load the client's business profile from file."""
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading profile: {e}")
        return None

    def _save_profile(self, profile: Dict) -> None:
        """Save the client's business profile to file."""
        try:
            with open(self.profile_file, "w") as f:
                json.dump(profile, f, indent=2)
            logger.info(f"Saved business profile for {self.client_name}")
        except Exception as e:
            logger.error(f"Error saving profile: {e}")

    def generate_categorization_prompt(self) -> str:
        """Generate a prompt for transaction categorization based on the business profile."""
        profile = self._load_profile()
        if not profile:
            logger.error("No business profile found")
            return ""

        prompt = f"""As a transaction categorization expert for {profile['business_type']}, please categorize this transaction:

Transaction Description: {{description}}
Amount: {{amount}}
Date: {{date}}

Business Context:
{profile['business_description']}

Industry Insights:
{profile['industry_insights']}

Available Categories:
{json.dumps(profile['category_hierarchy'], indent=2)}

Please provide:
1. Main Category: The primary category for this transaction
2. Subcategory: The specific subcategory (if applicable)
3. Confidence Score: 0-1 indicating certainty in the categorization
4. Reasoning: Explanation for the categorization
5. Business Context: How this relates to the client's business
6. Questions: Any questions that would help clarify the categorization

Return the response as a JSON object with the following structure:
{{
    "main_category": "string",
    "subcategory": "string",
    "confidence": float,
    "reasoning": "string",
    "business_context": "string",
    "questions": ["string"]
}}"""

        return prompt
