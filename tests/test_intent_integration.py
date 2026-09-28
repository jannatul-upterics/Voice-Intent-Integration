"""
Tests for Intent-Classification Integration Stage and Full Audio-to-Intent Pipeline.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from intent_adapter import (
    IntentClassificationAdapter,
    IntentClassificationConfigError,
)
from main import VoiceIntentOrchestrator


class TestIntentClassificationIntegration(unittest.TestCase):

    def setUp(self):
        self.adapter = IntentClassificationAdapter()
        self.orchestrator = VoiceIntentOrchestrator()

    def test_intent_project_detected(self):
        """Verify the sibling intent-classification project is detected and accessible."""
        self.assertIsNotNone(config.INTENT_CLASSIFICATION_DIR)
        self.assertTrue(config.INTENT_CLASSIFICATION_DIR.exists())
        self.assertTrue(self.adapter.intent_project_dir.exists())

    def test_empty_and_unclear_text_handling(self):
        """Verify empty and degraded speech strings are gracefully handled."""
        test_cases = [
            "",
            "   ",
            "[No speech detected in audio file]",
            "[unclear audio]",
            "...",
        ]
        for empty_text in test_cases:
            self.assertTrue(
                self.adapter.is_empty_or_unclear(empty_text),
                f"Failed for case: '{empty_text}'"
            )
            result = self.adapter.classify(empty_text)
            self.assertEqual(result["intent"], "unknown")
            self.assertIsNone(result["party_size"])
            self.assertIn("summary", result)
            self.assertGreater(len(result["summary"]), 0)

    def test_mock_classification(self):
        """Verify mock mode returns preserved schema without network calls."""
        mock_adapter = IntentClassificationAdapter(mock_mode=True)
        result = mock_adapter.classify("Book a table for 4 at 8 PM")
        self.assertEqual(result["intent"], "booking")
        self.assertEqual(result["party_size"], 4)
        self.assertEqual(result["time"], "20:00")
        self.assertIn("summary", result)

    def test_output_schema_preservation(self):
        """Verify classifier output preserves all mandatory fields."""
        result = self.adapter.classify("Table for 2 people tomorrow at 7 PM")
        required_fields = ["intent", "party_size", "date", "time", "food_preference", "summary"]
        for field in required_fields:
            self.assertIn(field, result, f"Mandatory field '{field}' missing from output.")
        self.assertEqual(result["intent"], "booking")
        self.assertEqual(result["party_size"], 2)
        self.assertEqual(result["time"], "19:00")

    def test_inquiry_intent(self):
        """Verify inquiry intent is classified correctly."""
        result = self.adapter.classify("What are your opening hours and do you have a parking space?")
        self.assertEqual(result["intent"], "inquiry")
        self.assertIn("summary", result)

    def test_cancellation_intent(self):
        """Verify cancellation intent is classified correctly."""
        result = self.adapter.classify("Please cancel our table reservation for tonight")
        self.assertEqual(result["intent"], "cancellation")
        self.assertIn("summary", result)

    def test_full_pipeline_with_audio_file(self):
        """
        Verify end-to-end flow:
          Customer Audio -> Voice Processing -> Customer Text -> Intent Classification
        """
        sample_audio = config.AUDIO_DIR / "sample_customer_audio.wav"
        if not sample_audio.exists():
            self.skipTest("Sample customer audio file not present.")

        pipeline_result = self.orchestrator.process_audio_file(sample_audio)
        self.assertEqual(pipeline_result["status"], "success")
        self.assertIn("customer_text", pipeline_result)
        self.assertIn("intent_classification", pipeline_result)

        intent_data = pipeline_result["intent_classification"]
        self.assertEqual(intent_data["intent"], "booking")
        self.assertEqual(intent_data["party_size"], 10)
        self.assertEqual(intent_data["time"], "19:30")
        self.assertIn("Sarah", pipeline_result["customer_text"])


if __name__ == "__main__":
    unittest.main()
