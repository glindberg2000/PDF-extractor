from dataextractai.agents.client_profile_manager import ClientProfileManager

# Initialize the profile manager for Gene
manager = ClientProfileManager("Gene")

# Create/update profile with real estate focus
profile = manager.create_or_update_profile(
    business_type="Real Estate Photography",
    business_description="Professional real estate photography and virtual tour service specializing in property marketing, virtual tours, and high-quality photography for real estate listings. Provides comprehensive visual marketing solutions for real estate agents and property sellers.",
    custom_categories=[
        "Photography Services",
        "Virtual Tours",
        "Marketing",
        "Real Estate Services",
    ],
)

print("Profile updated successfully:", profile)
