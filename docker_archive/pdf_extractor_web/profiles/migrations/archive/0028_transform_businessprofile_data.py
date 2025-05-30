from django.db import migrations


def transform_businessprofile_data(apps, schema_editor):
    BusinessProfile = apps.get_model("profiles", "BusinessProfile")
    profiles = BusinessProfile.objects.all()

    for profile in profiles:
        if profile.business_type == "Real Estate Agent":
            profile.common_business_expenses = [
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
            profile.save()


def reverse_transform(apps, schema_editor):
    BusinessProfile = apps.get_model("profiles", "BusinessProfile")
    BusinessProfile.objects.all().update(common_business_expenses=[])


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0027_fix_transaction_fields"),
    ]

    operations = [
        migrations.RunPython(transform_businessprofile_data, reverse_transform),
    ]
