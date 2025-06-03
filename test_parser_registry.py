from dataextractai.parsers_core.autodiscover import autodiscover_parsers
from dataextractai.parsers_core.registry import ParserRegistry

if __name__ == "__main__":
    print("[TEST] Running autodiscover_parsers...")
    autodiscover_parsers()
    print("[TEST] Registered parsers:", ParserRegistry.list_parsers())
