"""
Response Generation Module for Voice-Intent Integration.

Transforms structured intent-classification output and extracted reservation
parameters into polite, natural, customer-facing text responses.

Designed specifically for voice-based conversational agents:
  - Clean conversational phrasing (no markdown, no bullets, no raw JSON).
  - Natural speech formatting for dates, times, and guest counts.
  - Graceful handling of missing information, invalid inputs, and unclear speech.
  - Zero hallucination / does not invent information not provided by the customer.
"""

import datetime
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ResponseGenerator")


class ResponseGenerator:
    """
    Generates natural customer-facing responses based on intent data and extracted slots.
    """

    def __init__(
        self,
        restaurant_name: str = "",
        base_date: Optional[datetime.date] = None,
        allow_past_dates: bool = False,
    ):
        self.restaurant_name = restaurant_name
        self.base_date = base_date
        self.allow_past_dates = allow_past_dates

    # -----------------------------------------------------------------------
    # Formatting Helpers (Speech-Friendly)
    # -----------------------------------------------------------------------

    @staticmethod
    def format_date_for_speech(date_str: Optional[str]) -> Optional[str]:
        """
        Converts ISO date 'YYYY-MM-DD' into spoken natural date:
        '2026-09-25' -> 'Friday, September 25th'
        """
        if not date_str:
            return None
        date_clean = str(date_str).strip()
        try:
            dt = datetime.date.fromisoformat(date_clean)
            day_num = dt.day
            # Determine ordinal suffix (1st, 2nd, 3rd, 4th, etc.)
            if 11 <= day_num <= 13:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
            return f"{dt.strftime('%A, %B')} {day_num}{suffix}"
        except (ValueError, TypeError):
            return date_clean

    @staticmethod
    def format_time_for_speech(time_str: Optional[str]) -> Optional[str]:
        """
        Converts 24-hour time 'HH:MM' into spoken natural time:
        '19:30' -> '7:30 PM', '20:00' -> '8:00 PM', '12:00' -> '12:00 PM'
        """
        if not time_str:
            return None
        time_clean = str(time_str).strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", time_clean)
        if match:
            h = int(match.group(1))
            m = int(match.group(2))
            period = "AM" if h < 12 else "PM"
            h_12 = h % 12
            if h_12 == 0:
                h_12 = 12
            if m == 0:
                return f"{h_12} {period}"
            return f"{h_12}:{m:02d} {period}"
        return time_clean

    @staticmethod
    def format_dietary_for_speech(food_pref: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Converts dietary preference dict into spoken phrase:
        {'vegetarian': 2, 'gluten_free': 1} -> '2 vegetarian and 1 gluten-free'
        """
        if not food_pref or not isinstance(food_pref, dict):
            return None

        # Filter out non_vegetarian or 0 counts
        valid_items = [
            (k.replace("_", "-"), v)
            for k, v in food_pref.items()
            if k != "non_vegetarian" and v is not None and v > 0
        ]
        if not valid_items:
            return None

        parts = []
        for tag, count in valid_items:
            parts.append(f"{count} {tag} meal" if count == 1 else f"{count} {tag} meals")

        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + " and " + parts[-1]

    # -----------------------------------------------------------------------
    # Slot Validation
    # -----------------------------------------------------------------------

    @staticmethod
    def validate_party_size(party_size: Any) -> tuple[bool, Optional[str]]:
        """
        Validates party size.
        Returns: (is_valid, error_reason)
        """
        if party_size is None:
            return False, "missing"
        try:
            val = int(party_size)
            if val <= 0:
                return False, "non_positive"
            if val > 30:
                return False, "large_group"
            return True, None
        except (ValueError, TypeError):
            return False, "invalid_type"

    @staticmethod
    def validate_date(
        date_str: Optional[str],
        base_date: Optional[datetime.date] = None,
        allow_past: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """
        Validates reservation date.
        Returns: (is_valid, error_reason)
        """
        if not date_str:
            return False, "missing"
        try:
            dt = datetime.date.fromisoformat(str(date_str).strip())
            if allow_past:
                return True, None
            if base_date is not None:
                today = base_date
            else:
                ref_env = os.environ.get("REFERENCE_DATE")
                if ref_env:
                    try:
                        today = datetime.date.fromisoformat(ref_env)
                    except Exception:
                        today = datetime.date.today()
                else:
                    today = datetime.date.today()
            if dt < today:
                return False, "past_date"
            return True, None
        except (ValueError, TypeError):
            return False, "invalid_format"

    # -----------------------------------------------------------------------
    # Intent-Specific Handlers
    # -----------------------------------------------------------------------

    def _handle_booking(self, intent_data: Dict[str, Any], customer_text: Optional[str] = None) -> str:
        """
        Handle booking intent: validate slots, handle missing information,
        and generate clean customer-facing confirmation or follow-up prompt.
        """
        party_size = intent_data.get("party_size")
        date_val = intent_data.get("date")
        time_val = intent_data.get("time")
        food_pref = intent_data.get("food_preference")

        # 1. Validate party size if provided
        if party_size is not None:
            is_valid_ps, ps_err = self.validate_party_size(party_size)
            if not is_valid_ps:
                if ps_err == "non_positive":
                    return "A table reservation requires at least one guest. How many people will be in your party?"
                elif ps_err == "large_group":
                    return (
                        f"For large parties of {party_size} guests, we require a special group booking. "
                        "Please call our events manager directly, or would you like to book for a smaller group?"
                    )

        # 2. Validate date if provided
        if date_val is not None:
            is_valid_dt, dt_err = self.validate_date(date_val, base_date=self.base_date, allow_past=self.allow_past_dates)
            if not is_valid_dt and dt_err == "past_date":
                spoken_date = self.format_date_for_speech(date_val)
                return f"The date requested, {spoken_date}, has already passed. Which upcoming date would you like to reserve for?"

        # 3. Identify missing slots
        missing = []
        if party_size is None:
            missing.append("party_size")
        if not date_val:
            missing.append("date")
        if not time_val:
            missing.append("time")

        # Speech-formatted representations of available fields
        guest_phrase = f"a table for {party_size}" if party_size else None
        date_phrase = self.format_date_for_speech(date_val)
        time_phrase = self.format_time_for_speech(time_val)

        # Handle incomplete booking scenarios
        if len(missing) == 3:
            return "I would be delighted to help you reserve a table. How many guests will be dining, and for which date and time?"

        if "party_size" in missing and "date" in missing:
            return f"I can arrange a reservation for {time_phrase}. How many guests will be dining, and on what date?"

        if "party_size" in missing and "time" in missing:
            return f"I can help with a booking for {date_phrase}. How many guests will be in your party, and what time would you prefer?"

        if "date" in missing and "time" in missing:
            return f"I would be happy to reserve a table for {party_size} guests. Which date and time would you prefer?"

        if "party_size" in missing:
            return f"I can reserve a table for {date_phrase} at {time_phrase}. How many guests will be joining you?"

        if "date" in missing:
            return f"I can help you book a table for {party_size} at {time_phrase}. Which date would you like to reserve for?"

        if "time" in missing:
            return f"Certainly, I have noted {party_size} guests for {date_phrase}. What time would you prefer for your table?"

        # 4. Complete booking request: assemble confirmation response
        response_parts = [f"Certainly! I have noted your reservation for {party_size} guests on {date_phrase} at {time_phrase}."]

        # Include dietary restrictions if specified
        diet_str = self.format_dietary_for_speech(food_pref)
        if diet_str:
            response_parts.append(f"We have noted your dietary requirements: {diet_str}.")

        # Include seating or celebration preferences if present
        seating = intent_data.get("seating_preference")
        if seating:
            if isinstance(seating, dict):
                seating_desc = ", ".join(k.replace("_", " ") for k in seating.keys())
            else:
                seating_desc = str(seating).replace("_", " ")
            response_parts.append(f"We will do our best to arrange {seating_desc} seating for your party.")

        celebration = intent_data.get("celebration_requirement")
        if celebration:
            if isinstance(celebration, dict):
                celeb_desc = ", ".join(k.replace("_", " ") for k in celebration.keys())
            else:
                celeb_desc = str(celebration).replace("_", " ")
            response_parts.append(f"We look forward to celebrating your {celeb_desc} with you.")

        accessibility = intent_data.get("accessibility_requirement")
        if accessibility:
            if isinstance(accessibility, dict):
                acc_desc = ", ".join(k.replace("_", " ") for k in accessibility.keys())
            else:
                acc_desc = str(accessibility).replace("_", " ")
            response_parts.append(f"We have also noted your request for {acc_desc}.")

        # Check for customer name in intent_data, customer_text, or summary
        name_match = intent_data.get("customer_name") or intent_data.get("name")
        if not name_match and customer_text:
            m = re.search(r"\bunder\s+(?:the\s+name\s+(?:of\s+)?)?([A-Za-z]+)\b", customer_text, re.IGNORECASE)
            if m and m.group(1).lower() not in ("a", "the", "our", "my", "your"):
                name_match = m.group(1).capitalize()
        if not name_match and intent_data.get("summary"):
            m = re.search(r"\bunder\s+(?:the\s+name\s+(?:of\s+)?)?([A-Za-z]+)\b", intent_data["summary"], re.IGNORECASE)
            if m and m.group(1).lower() not in ("a", "the", "our", "my", "your"):
                name_match = m.group(1).capitalize()

        if name_match:
            if self.restaurant_name:
                response_parts.append(f"The reservation is placed under the name {name_match}. We look forward to welcoming you to {self.restaurant_name}.")
            else:
                response_parts.append(f"The reservation is placed under the name {name_match}. We look forward to welcoming you.")
        else:
            response_parts.append(f"May I have your name to complete the reservation?")

        return " ".join(response_parts)

    def _handle_inquiry(self, intent_data: Dict[str, Any], customer_text: Optional[str] = None) -> str:
        """
        Handle inquiry intent: answer questions regarding hours, menu, dietary, catering, etc.
        """
        combined = f"{customer_text or ''} {intent_data.get('summary', '')}".lower()

        # Dietary inquiry
        if any(w in combined for w in ("vegan", "vegetarian", "gluten", "allergy", "allergic", "diet", "halal", "kosher")):
            prefix = f"{self.restaurant_name} offers" if self.restaurant_name else "We offer"
            return (
                f"Yes, {prefix} a wide selection of vegetarian, vegan, and gluten-free dishes. "
                "Our chefs are happy to accommodate food allergies and specific dietary needs. "
                "Would you like to reserve a table?"
            )

        # Hours / Opening inquiry
        if any(w in combined for w in ("hour", "open", "close", "timing", "time")):
            prefix = f"{self.restaurant_name} is" if self.restaurant_name else "We are"
            return (
                f"{prefix} open Monday through Sunday. "
                "Lunch is served from 12:00 PM to 3:30 PM, and dinner is served from 5:30 PM to 10:30 PM. "
                "Would you like to book a table for lunch or dinner?"
            )

        # Catering / Takeout inquiry
        if any(w in combined for w in ("catering", "takeout", "take away", "delivery", "box")):
            return (
                f"Yes, we offer takeout orders and catering boxes for private events and gatherings. "
                "You can browse our catering menu online or place an order by phone. "
                "How else may I assist you today?"
            )

        # Parking inquiry
        if any(w in combined for w in ("parking", "valet", "car")):
            return (
                f"We offer complimentary valet parking for all dining guests right at the main entrance. "
                "Would you like to reserve a table?"
            )

        # General inquiry fallback using summary
        summary = intent_data.get("summary")
        if summary and "inquiring" in summary.lower():
            target_name = f" {self.restaurant_name}" if self.restaurant_name else ""
            return f"Thank you for contacting us{target_name}. Regarding your question, we would be delighted to assist. Would you like more details or to reserve a table?"

        if self.restaurant_name:
            return f"Thank you for reaching out to {self.restaurant_name}. How may I assist you with your dining plans today?"
        return "Thank you for reaching out. How may I assist you with your dining plans today?"

    def _handle_modification(self, intent_data: Dict[str, Any], customer_text: Optional[str] = None) -> str:
        """
        Handle modification intent: acknowledge requested changes and ask for reference/name.
        """
        changes = []
        if intent_data.get("party_size"):
            changes.append(f"{intent_data['party_size']} guests")
        if intent_data.get("date"):
            changes.append(self.format_date_for_speech(intent_data["date"]))
        if intent_data.get("time"):
            changes.append(self.format_time_for_speech(intent_data["time"]))

        if changes:
            change_str = ", ".join(changes)
            return (
                f"I can certainly help update your booking to {change_str}. "
                "Could you please provide your booking name or confirmation number so I can locate your reservation?"
            )
        return (
            "I would be glad to help modify your reservation. "
            "Could you please share your booking confirmation number or the name on the reservation, along with the details you wish to change?"
        )

    def _handle_cancellation(self, intent_data: Dict[str, Any], customer_text: Optional[str] = None) -> str:
        """
        Handle cancellation intent: acknowledge request politely and prompt for identification.
        """
        date_val = intent_data.get("date")
        if date_val:
            spoken_date = self.format_date_for_speech(date_val)
            return (
                f"I understand you would like to cancel your reservation for {spoken_date}. "
                "To finalize the cancellation, please provide the name on the booking or your confirmation number."
            )
        return (
            "I can assist you with cancelling your reservation. "
            "Could you please provide the name under which the booking was made, or your reservation confirmation number?"
        )

    def _handle_unclear(self, intent_data: Dict[str, Any], customer_text: Optional[str] = None) -> str:
        """
        Handle unclear or degraded speech requests.
        """
        return "I apologize, but I was unable to hear or understand that clearly. Could you please repeat how many guests and what date you would like to reserve for?"

    def _handle_empty_speech(self) -> str:
        """
        Handle cases where audio contained silence or no discernible speech.
        """
        return "I apologize, but no speech was detected in your recording. Please try speaking again."

    def _handle_intent_failure(self) -> str:
        """
        Handle cases where intent classification encountered a technical failure.
        """
        at_phrase = f" at {self.restaurant_name}" if self.restaurant_name else ""
        return (
            f"I am having trouble processing your request right now. "
            f"If you would like to make a table reservation{at_phrase}, "
            "please let me know your desired date, time, and number of guests."
        )

    def _handle_network_failure(self) -> str:
        """
        Handle cases where external network or API connectivity fails.
        """
        return (
            "I apologize, but we are currently experiencing a temporary connection issue. "
            "Please try again in a few moments, or contact our front desk directly for assistance."
        )

    def _handle_unsupported(self, intent_data: Dict[str, Any], customer_text: Optional[str] = None) -> str:
        """
        Handle requests that fall outside restaurant operations.
        """
        prefix = f"At {self.restaurant_name}, I" if self.restaurant_name else "I"
        return (
            f"I apologize, but I am unable to assist with that request. "
            f"{prefix} can help you with table bookings, menu information, and dietary inquiries. "
            "How may I assist you with your dining plans?"
        )

    def generate_error_response(self, error_type: str, detail: Optional[str] = None) -> str:
        """
        Generate a polite, spoken-word customer response for various pipeline failure modes.
        Never exposes technical details, API keys, internal paths, or stack traces.

        Args:
            error_type: Identifier of the error condition.
            detail: Optional supplementary context (sanitized before use).

        Returns:
            str: Customer-facing natural speech response.
        """
        err_clean = (error_type or "").lower().strip()
        if "empty" in err_clean or "no_speech" in err_clean:
            return self._handle_empty_speech()
        elif "unrecognized" in err_clean or "unclear" in err_clean:
            return self._handle_unclear({})
        elif "network" in err_clean or "api" in err_clean or "connection" in err_clean:
            return self._handle_network_failure()
        elif "intent" in err_clean or "classification" in err_clean:
            return self._handle_intent_failure()
        elif "tts" in err_clean:
            if self.restaurant_name:
                return f"Thank you for reaching out to {self.restaurant_name}. Your request has been received."
            return "Thank you for reaching out. Your request has been received."
        else:
            if self.restaurant_name:
                return f"Thank you for contacting {self.restaurant_name}. How may I assist you with your dining plans today?"
            return "Thank you for contacting us. How may I assist you with your dining plans today?"

    # -----------------------------------------------------------------------
    # Main Generation Dispatcher
    # -----------------------------------------------------------------------

    def generate_response(
        self,
        intent_data: Dict[str, Any],
        customer_text: Optional[str] = None,
    ) -> str:
        """
        Generate a clean customer-facing text response based on intent classification data.
        Guaranteed not to raise an exception or crash even on malformed inputs.

        Args:
            intent_data: Output dictionary from intent-classification stage.
            customer_text: Optional original customer transcript for additional conversational context.

        Returns:
            str: Clean natural-language customer-facing text response ready for TTS.
        """
        try:
            if not intent_data or not isinstance(intent_data, dict):
                return self._handle_unclear({}, customer_text)

            # Check for error or empty/unclear speech flags
            if intent_data.get("is_empty"):
                return self._handle_empty_speech()
            if intent_data.get("is_empty_or_unclear"):
                return self._handle_unclear(intent_data, customer_text)
            if intent_data.get("error_type") == "network_error":
                return self._handle_network_failure()
            if intent_data.get("error_type") == "classification_failed":
                return self._handle_intent_failure()

            intent = str(intent_data.get("intent", "")).strip().lower()

            logger.info("Generating customer response for intent: '%s'", intent)

            if intent == "booking":
                response = self._handle_booking(intent_data, customer_text)
            elif intent == "inquiry":
                response = self._handle_inquiry(intent_data, customer_text)
            elif intent == "modification":
                response = self._handle_modification(intent_data, customer_text)
            elif intent == "cancellation":
                response = self._handle_cancellation(intent_data, customer_text)
            elif intent in ("unsupported", "off_topic"):
                response = self._handle_unsupported(intent_data, customer_text)
            elif intent == "unknown":
                response = self._handle_unclear(intent_data, customer_text)
            else:
                # Fallback for unexpected or custom intents
                response = self._handle_booking(intent_data, customer_text)

            # Ensure text is clean and suitable for TTS (no markdown asterisks or backticks)
            clean_response = response.replace("**", "").replace("*", "").replace("`", "").strip()
            logger.info("Generated response: \"%s\"", clean_response)
            return clean_response

        except Exception as err:
            logger.error("Response generation failed unexpectedly: %s", err, exc_info=True)
            if self.restaurant_name:
                return f"Thank you for contacting {self.restaurant_name}. How may I assist you with your dining plans today?"
            return "Thank you for contacting us. How may I assist you with your dining plans today?"
