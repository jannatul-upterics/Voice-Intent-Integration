"""
Standalone End-to-End Audio Test Runner for Voice-Intent Integration.

Executes all 10 realistic customer audio scenarios:
 1. Greeting
 2. New booking request
 3. Booking with guest count
 4. Booking with date and time
 5. Inquiry
 6. Modification request
 7. Cancellation request
 8. Incomplete request
 9. Unclear speech/request
10. Invalid or unsupported request

Enforces:
  Input is AUDIO ONLY
  → Correct Transcription
  → Correct Intent
  → Correct Extracted Information
  → Appropriate Response Text
  → Valid Response Audio File

Reports each stage separately and provides a final pass/fail summary table.
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tests.test_e2e_audio_pipeline import TestEndToEndAudioPipeline


def run_e2e_tests():
    """Run the 10 E2E audio test cases with stage reporting."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEndToEndAudioPipeline)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_e2e_tests())
