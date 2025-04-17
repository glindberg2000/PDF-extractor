import os
import importlib
from django.conf import settings
from profiles.models import Tool


def discover_tools():
    """Discover and register tools from the tools directory."""
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")

    # Get all Python modules in the tools directory
    for root, dirs, files in os.walk(tools_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                # Get the module path relative to the tools directory
                rel_path = os.path.relpath(root, tools_dir)
                if rel_path == ".":
                    module_path = f"tools.{file[:-3]}"
                else:
                    module_path = f'tools.{rel_path.replace(os.sep, ".")}.{file[:-3]}'

                try:
                    # Import the module
                    module = importlib.import_module(module_path)

                    # Check if the module has the required attributes
                    if hasattr(module, "name") and hasattr(module, "description"):
                        # Create or update the tool in the database
                        Tool.objects.update_or_create(
                            name=module.name,
                            defaults={
                                "description": module.description,
                                "module_path": module_path,
                            },
                        )
                except Exception as e:
                    print(f"Error loading tool {module_path}: {str(e)}")
