"""
Boundary 3 Tests: Intent → response generation → response text.

Tests the third integration boundary:
- Receiving intent-classification dictionary and customer context.
- Generating clean, spoken-word customer-facing responses.
- Verifying all supported intents (booking, inquiry, modification, cancellation).
- Verifying handling of missing slots, invalid values, unclear speech, and generation exceptions.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from response_generator import ResponseGenerator


class TestBoundary3IntentToResponse(unittest.TestCase):
    """Integration Boundary 3: Intent -> response generation -> response text."""

    @classmethod
    def setUpClass(cls):
        cls._orig_ref = os.environ.get("REFERENCE_DATE")
        os.environ["REFERENCE_DATE"] = "2026-09-25"

    @classmethod
    def tearDownClass(cls):
        if cls._orig_ref is not None:
            os.environ["REFERENCE_DATE"] = cls._orig_ref
        else:
            os.environ.pop("REFERENCE_DATE", None)

    def setUp(self):
        self.generator = ResponseGenerator()

    # -----------------------------------------------------------------------
    # Success Cases: Response Phrasing & Natural Speech Formatting
    # -----------------------------------------------------------------------
    def test_complete_booking_response(self):
        """Verify complete booking generates confirmation with formatted date, time, party, and name."""
        intent_data = {
            "intent": "booking",
            "party_size": 4,
            "date": "2026-09-25",
            "time": "20:00",
            "customer_name": "Sarah",
            "food_preference": {"vegetarian": 1},
            "seating_preference": "window",
            "celebration_requirement": "birthday",
        }
        resp = self.generator.generate_response(intent_data)
        self.assertIn("4 guests", resp)
        self.assertIn("September 25th", resp)
        self.assertIn("8 PM", resp)
        self.assertIn("Sarah", resp)
        self.assertIn("vegetarian", resp)
        self.assertIn("window", resp)
        self.assertIn("birthday", resp)
        # Verify speech friendliness: no markdown asterisks or backticks
        self.assertNotIn("**", resp)
        self.assertNotIn("`", resp)

    def test_inquiry_hours_response(self):
        """Verify hours inquiry yields operating schedule and asks to book."""
        intent_data = {"intent": "inquiry", "summary": "Customer asking about operating hours"}
        resp = self.generator.generate_response(intent_data, customer_text="What are your hours?")
        self.assertIn("Monday through Sunday", resp)
        self.assertIn("lunch", resp.lower())
        self.assertIn("dinner", resp.lower())

    def test_inquiry_dietary_response(self):
        """Verify dietary inquiry informs customer about vegetarian, vegan, and gluten-free options."""
        intent_data = {"intent": "inquiry", "summary": "Customer asking about vegan options"}
        resp = self.generator.generate_response(intent_data, customer_text="Do you have vegan and gluten free dishes?")
        self.assertIn("vegetarian", resp.lower())
        self.assertIn("vegan", resp.lower())
        self.assertIn("gluten-free", resp.lower())

    def test_inquiry_parking_response(self):
        """Verify parking inquiry informs customer about valet services."""
        intent_data = {"intent": "inquiry", "summary": "Customer asking about parking"}
        resp = self.generator.generate_response(intent_data, customer_text="Is there parking available?")
        self.assertIn("valet parking", resp.lower())

    def test_modification_response(self):
        """Verify modification intent acknowledges requested changes and prompts for confirmation/name."""
        intent_data = {
            "intent": "modification",
            "party_size": 6,
            "date": "2026-09-26",
            "time": "20:30",
        }
        resp = self.generator.generate_response(intent_data)
        self.assertIn("6 guests", resp)
        self.assertIn("September 26th", resp)
        self.assertIn("8:30 PM", resp)
        self.assertIn("confirmation number", resp.lower())

    def test_cancellation_response(self):
        """Verify cancellation intent prompts for identification politely."""
        intent_data = {"intent": "cancellation", "date": "2026-09-25"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("cancel your reservation", resp.lower())
        self.assertIn("September 25th", resp)
        self.assertIn("confirmation number", resp.lower())

    # -----------------------------------------------------------------------
    # Failure Cases & Slot Discrepancies
    # -----------------------------------------------------------------------
    def test_missing_all_booking_slots(self):
        """Verify booking with no slots prompts for guests, date, and time."""
        intent_data = {"intent": "booking"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("how many guests", resp.lower())
        self.assertIn("date and time", resp.lower())

    def test_missing_date_slot(self):
        """Verify booking with party and time prompts specifically for date."""
        intent_data = {"intent": "booking", "party_size": 2, "time": "19:30"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("which date", resp.lower())

    def test_missing_party_size_slot(self):
        """Verify booking with date and time prompts specifically for party size."""
        intent_data = {"intent": "booking", "date": "2026-09-25", "time": "19:00"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("how many guests", resp.lower())

    def test_missing_time_slot(self):
        """Verify booking with party and date prompts specifically for time."""
        intent_data = {"intent": "booking", "party_size": 2, "date": "2026-09-25"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("what time", resp.lower())

    def test_invalid_party_size_zero(self):
        """Verify 0 guests generates clear prompt requiring at least one guest."""
        intent_data = {"intent": "booking", "party_size": 0, "date": "2026-09-25", "time": "19:00"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("at least one guest", resp.lower())

    def test_invalid_party_size_large_group(self):
        """Verify party size > 30 directs customer to events manager."""
        intent_data = {"intent": "booking", "party_size": 50, "date": "2026-09-25", "time": "19:00"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("large parties", resp.lower())
        self.assertIn("events manager", resp.lower())

    def test_invalid_past_date(self):
        """Verify past reservation dates inform customer and ask for upcoming date."""
        intent_data = {"intent": "booking", "party_size": 2, "date": "2026-09-10", "time": "19:00"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("has already passed", resp.lower())
        self.assertIn("which upcoming date", resp.lower())

    def test_unclear_or_empty_speech_flag(self):
        """Verify is_empty_or_unclear flag produces polite clarification request."""
        intent_data = {"intent": "unknown", "is_empty_or_unclear": True}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("unable to hear or understand", resp.lower())

    def test_empty_speech_flag(self):
        """Verify is_empty flag produces polite prompt stating no speech detected."""
        intent_data = {"intent": "unknown", "is_empty": True}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("no speech was detected", resp.lower())

    def test_unsupported_intent(self):
        """Verify unsupported requests produce polite boundary message."""
        intent_data = {"intent": "unsupported", "summary": "Customer asking about hotel rooms"}
        resp = self.generator.generate_response(intent_data)
        self.assertIn("unable to assist with that request", resp.lower())
        self.assertIn("table bookings", resp.lower())

    def test_generation_exception_graceful_fallback(self):
        """Verify unexpected internal exception during response generation falls back safely."""
        with patch.object(self.generator, "_handle_booking", side_effect=ValueError("Bug in generation")):
            safe_resp = self.generator.generate_response({"intent": "booking", "party_size": 2})
            self.assertIn("thank you for contacting", safe_resp.lower())
            self.assertNotIn("ValueError", safe_resp)
            self.assertNotIn("Traceback", safe_resp)


if __name__ == "__main__":
    unittest.main()
