from django.core.management.base import BaseCommand
from tools import discover_tools


class Command(BaseCommand):
    help = "Discover and register tools from the tools directory"

    def handle(self, *args, **options):
        self.stdout.write("Discovering tools...")
        discover_tools()
        self.stdout.write(
            self.style.SUCCESS("Successfully discovered and registered tools")
        )
