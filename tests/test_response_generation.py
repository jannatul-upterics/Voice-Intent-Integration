"""
Unit tests for Response Generation Module.
"""

import datetime
import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from response_generator import ResponseGenerator


class TestResponseGenerator(unittest.TestCase):

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

    def test_complete_booking_response(self):
        """Verify complete booking produces a natural confirmation text."""
        intent_data = {
            "intent": "booking",
            "party_size": 4,
            "date": "2026-09-25",
            "time": "20:00",
            "food_preference": {"vegetarian": 1},
            "seating_preference": {"window": 4},
            "celebration_requirement": {"birthday": 1},
            "summary": "Customer wants a table for 4 on Friday at 8 PM."
        }
        customer_text = "Table for 4 this Friday at 8 PM for a birthday under Sarah. One person is vegetarian."
        response = self.generator.generate_response(intent_data, customer_text)

        self.assertIn("4 guests", response)
        self.assertIn("8 PM", response)
        self.assertIn("Friday, September 25th", response)
        self.assertIn("1 vegetarian meal", response)
        self.assertIn("window", response)
        self.assertIn("birthday", response)
        self.assertIn("Sarah", response)
        # Check text is clean for TTS
        self.assertNotIn("*", response)
        self.assertNotIn("`", response)

    def test_incomplete_booking_missing_time(self):
        """Verify missing time prompts specifically for time."""
        intent_data = {
            "intent": "booking",
            "party_size": 2,
            "date": "2026-09-25",
            "time": None,
            "food_preference": {},
            "summary": "Customer wants a table for 2 on Friday."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("What time", response)
        self.assertIn("2 guests", response)

    def test_incomplete_booking_missing_date(self):
        """Verify missing date prompts specifically for date."""
        intent_data = {
            "intent": "booking",
            "party_size": 2,
            "date": None,
            "time": "19:30",
            "food_preference": {},
            "summary": "Customer wants a table for 2 at 7:30 PM."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("Which date", response)
        self.assertIn("7:30 PM", response)

    def test_incomplete_booking_missing_party_size(self):
        """Verify missing party size prompts specifically for guest count."""
        intent_data = {
            "intent": "booking",
            "party_size": None,
            "date": "2026-09-25",
            "time": "19:00",
            "food_preference": {},
            "summary": "Customer wants a table on Friday at 7 PM."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("How many guests", response)

    def test_incomplete_booking_missing_all(self):
        """Verify completely empty booking prompts for all details."""
        intent_data = {
            "intent": "booking",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": {},
            "summary": "Customer wants to book."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("How many guests", response)
        self.assertIn("date and time", response)

    def test_invalid_party_size_zero_or_negative(self):
        """Verify invalid non-positive guest count prompts for correction."""
        intent_data = {
            "intent": "booking",
            "party_size": 0,
            "date": "2026-09-25",
            "time": "20:00",
            "food_preference": {},
            "summary": "Customer requested 0 people."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("at least one guest", response)

    def test_invalid_party_size_very_large(self):
        """Verify very large party size directs to events manager."""
        intent_data = {
            "intent": "booking",
            "party_size": 45,
            "date": "2026-09-25",
            "time": "20:00",
            "food_preference": {},
            "summary": "Customer wants 45 people."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("large parties", response)

    def test_invalid_date_in_past(self):
        """Verify dates in the past are rejected with polite explanation."""
        past_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        intent_data = {
            "intent": "booking",
            "party_size": 2,
            "date": past_date,
            "time": "20:00",
            "food_preference": {},
            "summary": "Customer wants past date."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("already passed", response)

    def test_inquiry_hours(self):
        """Verify operating hours inquiry produces informative response."""
        intent_data = {
            "intent": "inquiry",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": {},
            "summary": "Customer is inquiring about restaurant hours."
        }
        response = self.generator.generate_response(intent_data, "What are your opening hours?")
        self.assertIn("open", response.lower())
        self.assertIn("lunch", response.lower())
        self.assertIn("dinner", response.lower())

    def test_inquiry_dietary(self):
        """Verify dietary inquiry produces reassuring response."""
        intent_data = {
            "intent": "inquiry",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": {},
            "summary": "Customer is inquiring about vegan and gluten free options."
        }
        response = self.generator.generate_response(intent_data, "Do you have vegan options?")
        self.assertIn("vegan", response.lower())
        self.assertIn("gluten-free", response.lower())

    def test_modification_intent(self):
        """Verify modification requests prompt for booking reference and acknowledge changes."""
        intent_data = {
            "intent": "modification",
            "party_size": 6,
            "date": "2026-09-26",
            "time": "20:30",
            "food_preference": {},
            "summary": "Customer wants to change reservation to 6 guests at 8:30 PM."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("update your booking", response.lower())
        self.assertIn("6 guests", response)
        self.assertIn("confirmation number", response.lower())

    def test_cancellation_intent(self):
        """Verify cancellation request acknowledges date and prompts for verification."""
        intent_data = {
            "intent": "cancellation",
            "party_size": None,
            "date": "2026-09-25",
            "time": None,
            "food_preference": {},
            "summary": "Customer wants to cancel reservation."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("cancel your reservation", response.lower())
        self.assertIn("September 25th", response)
        self.assertIn("name", response.lower())

    def test_unclear_or_empty_speech(self):
        """Verify degraded or empty speech produces polite clarification prompt."""
        intent_data = {
            "intent": "unknown",
            "is_empty_or_unclear": True,
            "summary": "No speech detected in audio file."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("unable to hear or understand", response.lower())

    def test_unsupported_request(self):
        """Verify off-topic/unsupported request explains available capabilities."""
        intent_data = {
            "intent": "unsupported",
            "summary": "Customer asking for car repair."
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("unable to assist with that request", response.lower())
        self.assertIn("table bookings", response.lower())


if __name__ == "__main__":
    unittest.main()
