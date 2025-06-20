import pytest


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing test collection and execution.
    """
    from dataextractai.parsers_core.autodiscover import autodiscover_parsers

    print("Populating parser registry for test session...")
    autodiscover_parsers()
    print("Parser registry populated.")
