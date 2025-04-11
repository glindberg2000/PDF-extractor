import os
import importlib
import inspect
from pathlib import Path
from .models import Tool


def discover_tools():
    """
    Discover and register tools from the tools directory.
    Returns a list of discovered tool information.
    """
    # Get the project root directory (two levels up from this file)
    project_root = Path(__file__).parent.parent.parent
    tools_dir = project_root / "tools"

    if not tools_dir.exists():
        print(f"Tools directory not found at {tools_dir}")
        return []

    discovered_tools = []

    # Walk through all subdirectories in tools
    for root, dirs, files in os.walk(tools_dir):
        for file in files:
            # Skip test files, __init__.py, and any file with 'test' in the name
            if (
                file.endswith(".py")
                and not file.startswith("__")
                and not file.endswith("test.py")
                and "test" not in file.lower()
            ):

                # Get the module path
                rel_path = Path(root).relative_to(tools_dir)
                module_path = f"tools.{rel_path}.{file[:-3]}"

                try:
                    # Import the module
                    module = importlib.import_module(module_path)

                    # Check if it has a search function
                    if hasattr(module, "search"):
                        # Get the docstring for description
                        description = module.__doc__ or "No description provided"

                        # Get the schema if defined
                        schema = getattr(module, "SCHEMA", None)

                        discovered_tools.append(
                            {
                                "name": file[:-3],  # Remove .py extension
                                "description": description.strip(),
                                "module_path": module_path,
                                "schema": schema,
                            }
                        )
                except ImportError as e:
                    print(f"Import error for {module_path}: {e}")
                except Exception as e:
                    print(f"Error processing {module_path}: {e}")

    return discovered_tools


def register_tools():
    """
    Register discovered tools in the database.
    Creates new tools and updates existing ones.
    """
    discovered_tools = discover_tools()

    for tool_info in discovered_tools:
        # Get or create the tool
        tool, created = Tool.objects.update_or_create(
            name=tool_info["name"],
            defaults={
                "description": tool_info["description"],
                "module_path": tool_info["module_path"],
                "schema": tool_info["schema"],
                "is_active": True,
            },
        )

        if created:
            print(f"Registered new tool: {tool.name}")
        else:
            print(f"Updated existing tool: {tool.name}")


def get_available_tools():
    """
    Get a list of available tools with their status.
    """
    tools = []
    for tool in Tool.objects.all():
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "is_active": tool.is_active,
                "module_path": tool.module_path,
                "has_code": bool(tool.code),
                "has_schema": bool(tool.schema),
            }
        )
    return tools
