"""
Boundary 2 Tests: Text → intent-classification → intent.

Tests the second integration boundary:
- Feeding transcribed customer text into IntentClassificationAdapter.
- Calling existing extract_booking_info from Customer-Intent-Classification.
- Preserving the exact output schema from the existing project.
- Handling empty text, unclear speech, and classification/network failures.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from intent_adapter import (
    IntentClassificationAdapter,
    IntentClassificationAPIError,
    IntentClassificationError,
    NetworkOrAPIError,
)


class TestBoundary2TextToIntent(unittest.TestCase):
    """Integration Boundary 2: Text -> intent-classification -> intent."""

    def setUp(self):
        self.adapter = IntentClassificationAdapter()

    # -----------------------------------------------------------------------
    # Success Cases: Schema Preservation across Intents
    # -----------------------------------------------------------------------
    def test_schema_preservation_booking(self):
        """Verify classifier output preserves all mandatory fields for booking intent."""
        result = self.adapter.classify("Table for 2 people tomorrow at 7 PM")
        mandatory_fields = ["intent", "party_size", "date", "time", "food_preference", "summary"]
        for field in mandatory_fields:
            self.assertIn(field, result, f"Mandatory field '{field}' must be present in output.")

        self.assertEqual(result["intent"], "booking")
        self.assertEqual(result["party_size"], 2)
        self.assertEqual(result["time"], "19:00")
        self.assertIsInstance(result["food_preference"], dict)
        self.assertIsInstance(result["summary"], str)

    def test_inquiry_intent_classification(self):
        """Verify inquiry intent is classified correctly and preserves schema."""
        result = self.adapter.classify("What time do you open for dinner and do you have parking?")
        self.assertEqual(result["intent"], "inquiry")
        self.assertIn("summary", result)
        self.assertIsInstance(result["summary"], str)

    def test_cancellation_intent_classification(self):
        """Verify cancellation intent is classified correctly."""
        result = self.adapter.classify("I need to cancel my table reservation for Friday night")
        self.assertEqual(result["intent"], "cancellation")
        self.assertIn("summary", result)

    def test_modification_intent_classification(self):
        """Verify modification intent is classified correctly."""
        result = self.adapter.classify("Can we change our reservation from 4 guests to 6 guests at 8 PM?")
        self.assertEqual(result["intent"], "modification")
        self.assertIn("summary", result)

    def test_auxiliary_slots_preservation(self):
        """Verify optional/auxiliary entities (seating, celebration) are preserved."""
        result = self.adapter.classify("Book a table for 4 near the window for my anniversary dinner")
        self.assertEqual(result["intent"], "booking")
        # Check if auxiliary extracted attributes from the classifier are retained
        if "seating_preference" in result:
            self.assertIn("window", str(result["seating_preference"]).lower())

    def test_mock_classification_mode(self):
        """Verify offline mock mode returns valid preserved schema without external API calls."""
        mock_adapter = IntentClassificationAdapter(mock_mode=True)
        res = mock_adapter.classify("Book a table for four")
        self.assertEqual(res["intent"], "booking")
        self.assertEqual(res["party_size"], 4)
        self.assertIn("summary", res)

    # -----------------------------------------------------------------------
    # Failure Cases: Empty Text, Degraded Speech, API Failures
    # -----------------------------------------------------------------------
    def test_empty_text_handling(self):
        """Verify empty and whitespace strings return graceful unknown intent without crashing."""
        for empty_val in ["", "   ", "\t\n", None]:
            self.assertTrue(self.adapter.is_empty_or_unclear(empty_val))
            res = self.adapter.classify(empty_val)
            self.assertEqual(res["intent"], "unknown")
            self.assertIsNone(res["party_size"])
            self.assertTrue(res.get("is_empty_or_unclear"))
            self.assertIn("summary", res)

    def test_degraded_speech_handling(self):
        """Verify audio degradation markers return unknown intent gracefully."""
        unclear_texts = [
            "[no speech detected]",
            "[unclear audio]",
            "[music playing]",
            "...",
            "---",
        ]
        for unclear in unclear_texts:
            self.assertTrue(self.adapter.is_empty_or_unclear(unclear))
            res = self.adapter.classify(unclear)
            self.assertEqual(res["intent"], "unknown")

    def test_classifier_api_failure_raised(self):
        """Verify API exceptions in raw classify() are wrapped as IntentClassificationAPIError."""
        with patch.object(
            self.adapter,
            "_get_classifier_func",
            return_value=MagicMock(side_effect=RuntimeError("Groq LLM 500 Internal Server Error")),
        ):
            with self.assertRaises(IntentClassificationAPIError):
                self.adapter.classify("Book a table for 2")

    def test_classifier_network_failure_handling(self):
        """Verify network errors in classify() are wrapped as NetworkOrAPIError."""
        with patch.object(
            self.adapter,
            "_get_classifier_func",
            return_value=MagicMock(side_effect=Exception("APIConnectionError: Connection reset by peer")),
        ):
            with self.assertRaises(NetworkOrAPIError):
                self.adapter.classify("Book a table for 2")

    def test_safe_classify_error_immunity(self):
        """Verify safe_classify() never raises exceptions even on severe API or network crashes."""
        with patch.object(
            self.adapter,
            "_get_classifier_func",
            return_value=MagicMock(side_effect=RuntimeError("Fatal remote server crash")),
        ):
            safe_res = self.adapter.safe_classify("Book a table for 2")
            self.assertEqual(safe_res["intent"], "unknown")
            self.assertTrue(safe_res.get("is_error"))
            self.assertEqual(safe_res.get("error_type"), "classification_failed")

    def test_safe_classify_network_immunity(self):
        """Verify safe_classify() handles network drops cleanly."""
        with patch.object(
            self.adapter,
            "_get_classifier_func",
            return_value=MagicMock(side_effect=Exception("APIConnectionError: DNS resolution failed")),
        ):
            safe_res = self.adapter.safe_classify("Book a table for 2")
            self.assertEqual(safe_res["intent"], "unknown")
            self.assertTrue(safe_res.get("is_error"))
            self.assertEqual(safe_res.get("error_type"), "network_error")


if __name__ == "__main__":
    unittest.main()
