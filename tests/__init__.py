"""
Unit and integration tests package for voice-intent-integration.
"""

import os

# Ensure all automated test runners (pytest, unittest, etc.) have a consistent
# reference date for relative calendar calculations matching pre-recorded test audio.
os.environ.setdefault("REFERENCE_DATE", "2026-09-25")
