"""Client profile manager for handling business context and categorization."""

import os
import json
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import logging
from datetime import datetime
from ..db.client_db import ClientDB

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
        self.db = ClientDB()  # Add database instance

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
        # Define fixed 6A categories
        SCHEDULE_6A_CATEGORIES = [
            "Advertising",
            "Car and truck expenses",
            "Commissions and fees",
            "Contract labor",
            "Depletion",
            "Employee benefit programs",
            "Insurance (other than health)",
            "Interest (mortgage/other)",
            "Legal and professional services",
            "Office expenses",
            "Pension and profit-sharing plans",
            "Rent or lease (vehicles/equipment/other)",
            "Repairs and maintenance",
            "Supplies",
            "Taxes and licenses",
            "Travel, meals, and entertainment",
            "Utilities",
            "Wages",
            "Other expenses",
        ]

        # First generate industry keywords
        industry_keywords = self._generate_industry_keywords(
            profile_data["business_type"], profile_data["business_description"]
        )

        # Log the generated keywords for debugging
        logger.debug(f"Generated industry keywords: {industry_keywords}")

        prompt = f"""As a business analysis expert, analyze this business profile focusing strictly on IRS Schedule 6A expense categories.

Business Type: {profile_data['business_type']}
Description: {profile_data['business_description']}
User-Defined Categories (to be classified under "Other expenses"): {', '.join(profile_data['custom_categories']) if profile_data['custom_categories'] else 'None'}

Using ONLY the following IRS Schedule 6A categories:
{json.dumps(SCHEDULE_6A_CATEGORIES, indent=2)}

Please provide:
1. Common transaction patterns and descriptions to expect for each relevant 6A category
2. Industry-specific insights for expense tracking and categorization
3. Business context to help with transaction classification
4. Mapping of user-defined categories to appropriate 6A categories (if possible) or confirmation they belong in "Other expenses"

Return the response as a JSON object with the following structure:
{{
    "business_type": "string",
    "business_description": "string",
    "custom_categories": ["string"],  // Original user-defined categories
    "category_patterns": {{  // ONLY for Schedule 6A categories and user-defined categories under Other expenses
        "category_name": ["pattern1", "pattern2", ...]
    }},
    "industry_insights": "string",
    "business_context": "string",
    "category_mapping": {{  // Maps user-defined categories to 6A categories where possible
        "user_category": "6A_category"
    }},
    "last_updated": "timestamp"
}}"""

        response = self.client.chat.completions.create(
            model=OPENAI_MODEL_PRECISE,
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analysis expert specializing in IRS Schedule 6A expense categorization. Strictly adhere to 6A categories and treat custom categories as subcategories of Other expenses unless they clearly map to a 6A category.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        enhanced_profile = json.loads(response.choices[0].message.content)

        # Create final profile with all components including keywords
        final_profile = {
            "business_type": profile_data["business_type"],
            "business_description": profile_data["business_description"],
            "custom_categories": profile_data["custom_categories"],
            "schedule_6a_categories": SCHEDULE_6A_CATEGORIES,  # Include fixed list for reference
            "industry_keywords": industry_keywords,  # Add generated keywords
            "category_patterns": enhanced_profile.get("category_patterns", {}),
            "industry_insights": enhanced_profile.get("industry_insights", ""),
            "business_context": enhanced_profile.get("business_context", ""),
            "category_mapping": enhanced_profile.get("category_mapping", {}),
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

        # Log the final profile for debugging
        logger.debug(
            f"Final profile with keywords: {final_profile.get('industry_keywords', {})}"
        )

        return final_profile

    def _generate_industry_keywords(
        self, business_type: str, business_description: str
    ) -> Dict[str, float]:
        """Generate industry-specific keywords and their weights based on business type and description."""
        prompt = f"""Analyze this business profile and generate a comprehensive list of industry-specific keywords with their importance weights.

Business Type: {business_type}
Description: {business_description}

Rules:
1. Generate at least 15-20 relevant keywords
2. Include terms from these categories:
   - Core services and products
   - Industry terminology
   - Business processes
   - Customer interactions
   - Market-specific terms
   - Location-specific terms if relevant
3. Weight scale:
   0.95 = Essential to business identity/core offering
   0.90 = Primary business activities
   0.85 = Common business elements
   0.80 = Supporting activities/terms
   0.75 = Related concepts/context

Return a JSON object mapping keywords to their weights. Each weight should be between 0.75 and 0.95.
The keywords should be highly specific to this business type and description."""

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL_PRECISE,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a business analysis expert that specializes in identifying industry-specific terminology and business patterns. Generate comprehensive, specific keywords that reflect all aspects of the given business type.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            result = json.loads(response.choices[0].message.content)

            # Validate weights are in correct range
            validated_keywords = {
                k: float(v)
                for k, v in result.items()
                if isinstance(v, (int, float)) and 0.75 <= float(v) <= 0.95
            }

            logger.info(
                f"Generated {len(validated_keywords)} industry keywords for {self.client_name}"
            )
            return validated_keywords

        except Exception as e:
            logger.error(f"Error generating industry keywords: {e}")
            return {}

    def _merge_profiles(self, existing: Dict, enhanced: Dict) -> Dict:
        """Merge existing profile with enhanced profile, preserving important custom data."""
        merged = existing.copy()

        # Update with enhanced data while preserving 6A structure
        merged.update(
            {
                "business_type": enhanced["business_type"],
                "business_description": enhanced["business_description"],
                "custom_categories": enhanced["custom_categories"],
                "schedule_6a_categories": enhanced["schedule_6a_categories"],
                "industry_keywords": enhanced.get(
                    "industry_keywords", {}
                ),  # Add industry keywords
                "category_patterns": enhanced.get("category_patterns", {}),
                "industry_insights": enhanced["industry_insights"],
                "business_context": enhanced["business_context"],
                "category_mapping": enhanced.get("category_mapping", {}),
                "last_updated": enhanced["last_updated"],
            }
        )

        # Log the merged profile for debugging
        logger.debug(
            f"Merged profile with keywords: {merged.get('industry_keywords', {})}"
        )

        return merged

    def _load_profile(self) -> Optional[Dict]:
        """Load the client's business profile from DB and file."""
        # Try DB first
        profile = self.db.load_profile(self.client_name)
        if profile:
            return profile

        # Fall back to file
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, "r") as f:
                    profile = json.load(f)
                # If we loaded from file, save to DB for next time
                self.db.save_profile(self.client_name, profile)
                return profile
            except Exception as e:
                logger.error(f"Error loading profile from file: {e}")
        return None

    def _save_profile(self, profile: Dict) -> None:
        """Save the client's business profile to both DB and file."""
        try:
            logger.debug(f"Starting to save profile for {self.client_name}")
            logger.debug(f"Profile data: {json.dumps(profile, indent=2)}")

            # Save to DB
            logger.debug("Saving to database...")
            self.db.save_profile(self.client_name, profile)
            logger.debug("Successfully saved to database")

            # Save to file as backup
            logger.debug(f"Saving to file: {self.profile_file}")
            os.makedirs(os.path.dirname(self.profile_file), exist_ok=True)
            with open(self.profile_file, "w") as f:
                json.dump(profile, f, indent=2)
            logger.debug("Successfully saved to file")

            logger.info(f"Saved business profile for {self.client_name}")
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            logger.exception("Full traceback:")

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

    def _migrate_profile_to_6a(self, profile: Dict) -> Dict:
        """Migrate an existing profile to the 6A-focused format."""
        # Define fixed 6A categories - these are immutable
        SCHEDULE_6A_CATEGORIES = [
            "Advertising",
            "Car and truck expenses",
            "Commissions and fees",
            "Contract labor",
            "Depletion",
            "Employee benefit programs",
            "Insurance (other than health)",
            "Interest (mortgage/other)",
            "Legal and professional services",
            "Office expenses",
            "Pension and profit-sharing plans",
            "Rent or lease (vehicles/equipment/other)",
            "Repairs and maintenance",
            "Supplies",
            "Taxes and licenses",
            "Travel, meals, and entertainment",
            "Utilities",
            "Wages",
            "Other expenses",
        ]

        # Start with basic profile info
        migrated = {
            "business_type": profile["business_type"],
            "business_description": profile["business_description"],
            "schedule_6a_categories": SCHEDULE_6A_CATEGORIES,
            "custom_categories": profile["custom_categories"],
            "industry_insights": profile.get("industry_insights", ""),
            "business_context": profile.get("business_context", ""),
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

        # ALL custom categories go under Other expenses, no exceptions
        category_mapping = {}
        for cat in profile["custom_categories"]:
            category_mapping[cat] = "Other expenses"
        migrated["category_mapping"] = category_mapping

        # Create patterns for 6A categories only
        # Keep these generic and focused on the core 6A definitions
        category_patterns = {
            "Advertising": [
                "advertising costs",
                "promotional materials",
                "marketing expenses",
            ],
            "Car and truck expenses": [
                "vehicle expenses",
                "mileage",
                "auto maintenance",
                "fuel costs",
            ],
            "Commissions and fees": [
                "commission payments",
                "service fees",
                "transaction fees",
            ],
            "Contract labor": [
                "contractor payments",
                "temporary labor",
                "freelance services",
            ],
            "Depletion": ["resource depletion", "asset depreciation"],
            "Employee benefit programs": [
                "employee benefits",
                "health insurance",
                "benefit programs",
            ],
            "Insurance (other than health)": [
                "business insurance",
                "liability coverage",
                "property insurance",
            ],
            "Interest (mortgage/other)": [
                "loan interest",
                "mortgage interest",
                "financing costs",
            ],
            "Legal and professional services": [
                "legal fees",
                "professional services",
                "consulting fees",
            ],
            "Office expenses": ["office supplies", "equipment", "general office costs"],
            "Pension and profit-sharing plans": [
                "retirement plans",
                "pension costs",
                "profit sharing",
            ],
            "Rent or lease": ["rental payments", "lease expenses", "equipment rentals"],
            "Repairs and maintenance": [
                "repairs",
                "maintenance costs",
                "upkeep expenses",
            ],
            "Supplies": ["business supplies", "materials", "consumables"],
            "Taxes and licenses": ["business licenses", "permit fees", "tax payments"],
            "Travel, meals, and entertainment": [
                "travel expenses",
                "business meals",
                "entertainment costs",
            ],
            "Utilities": ["utility bills", "service charges", "utility expenses"],
            "Wages": ["employee wages", "salary expenses", "payroll costs"],
            "Other expenses": [
                # User's custom categories
                "dues and subscriptions",
                "professional memberships",
                "specialized fees",
                "industry-specific costs",
                # Note: Each business's actual Other expenses will be their custom categories
            ],
        }

        migrated["category_patterns"] = category_patterns

        return migrated

    def migrate_existing_profile(self) -> None:
        """Migrate an existing profile to the new 6A-focused format."""
        try:
            # Load existing profile
            profile = self._load_profile()
            if not profile:
                logger.error("No profile found to migrate")
                return

            # Migrate to new format
            migrated = self._migrate_profile_to_6a(profile)

            # Save migrated profile
            self._save_profile(migrated)
            logger.info(f"Successfully migrated profile for {self.client_name}")

        except Exception as e:
            logger.error(f"Error migrating profile: {e}")
