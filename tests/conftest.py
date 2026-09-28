"""
Pytest configuration and fixtures for Voice-Intent Integration tests.
"""

import os
import pytest

@pytest.fixture(autouse=True)
def set_test_reference_date():
    """
    Ensure automated tests have a consistent reference date for relative calendar
    calculations (e.g. 'this Friday') matching pre-recorded test audio and expected assertions.
    """
    orig_ref = os.environ.get("REFERENCE_DATE")
    os.environ["REFERENCE_DATE"] = "2026-09-25"
    yield
    if orig_ref is not None:
        os.environ["REFERENCE_DATE"] = orig_ref
    else:
        os.environ.pop("REFERENCE_DATE", None)
