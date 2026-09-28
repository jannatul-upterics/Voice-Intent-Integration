"""
Intent Classification Adapter Module.

Acts as an abstraction and decoupling layer between the integration project
and the existing intent-classification subsystem.

Does not rewrite or duplicate intent classification logic.
Dynamically interfaces with the existing extract_booking_info / classify_intent
functions from Customer-Intent-Classification, providing error isolation, input
sanitization, and output preservation for the integration layer.
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import config
from sanitizer import mask_sensitive_data

logger = logging.getLogger("IntentClassificationAdapter")


# ---------------------------------------------------------------------------
# Integration-Level Exceptions
# ---------------------------------------------------------------------------

class IntentClassificationError(Exception):
    """Base exception for all intent classification integration errors."""
    pass


class InvalidCustomerTextError(IntentClassificationError):
    """Raised when customer text is empty, malformed, or unprocessable."""
    pass


class IntentClassificationConfigError(IntentClassificationError):
    """Raised when the intent-classification project or configuration is missing."""
    pass


class IntentClassificationAPIError(IntentClassificationError):
    """Raised when the underlying LLM/intent API encounters an error."""
    pass


class NetworkOrAPIError(IntentClassificationError):
    """Raised when network connectivity or external API fails."""
    pass


# ---------------------------------------------------------------------------
# Intent Classification Adapter Class
# ---------------------------------------------------------------------------

class IntentClassificationAdapter:
    """
    Adapter that delegates natural-language customer text classification and slot
    extraction to the existing intent-classification implementation.
    """

    UNCLEAR_PATTERNS = [
        r"\[no speech detected.*\]",
        r"\[unclear.*\]",
        r"\[music.*\]",
        r"\[inaudible.*\]",
        r"\[blank_audio.*\]",
        r"^\s*$",
        r"^[.\s,-]+$",
    ]

    def __init__(
        self,
        intent_project_dir: Optional[Path] = None,
        mock_mode: bool = False,
    ):
        """
        Initialize the adapter.

        Args:
            intent_project_dir: Path to the existing intent-classification directory.
                               Defaults to config.INTENT_CLASSIFICATION_DIR.
            mock_mode: If True, returns mock classification without invoking external APIs.
        """
        self.intent_project_dir = intent_project_dir or config.INTENT_CLASSIFICATION_DIR
        self.mock_mode = mock_mode
        self._classifier_func = None

        if not self.mock_mode:
            self._ensure_project_accessible()

    def _ensure_project_accessible(self) -> None:
        """
        Verify that the intent-classification project exists and is accessible.
        Adds its directory to sys.path so its internal modules can be imported.
        """
        if not self.intent_project_dir or not self.intent_project_dir.exists():
            raise IntentClassificationConfigError(
                f"Intent-classification project directory not found at: '{self.intent_project_dir}'. "
                "Please verify the folder exists in the parent directory or set INTENT_CLASSIFICATION_DIR in .env."
            )

        proj_dir_str = str(self.intent_project_dir.resolve())
        if proj_dir_str not in sys.path:
            sys.path.insert(0, proj_dir_str)
            logger.debug("Added intent-classification directory to sys.path: %s", proj_dir_str)

    def _get_classifier_func(self) -> Any:
        """
        Lazily import the extraction function from the existing project.
        """
        if self._classifier_func is not None:
            return self._classifier_func

        try:
            from intent_classifier import extract_booking_info
            self._classifier_func = extract_booking_info
            return self._classifier_func
        except ImportError as err:
            raise IntentClassificationConfigError(
                f"Failed to import extract_booking_info from intent-classification project: {err}. "
                "Ensure dependencies are installed: pip install -r requirements.txt"
            ) from err

    def is_empty_or_unclear(self, text: Optional[str]) -> bool:
        """
        Check if transcribed text is empty, whitespace-only, or degraded speech.
        """
        if not text:
            return True
        stripped = text.strip()
        if not stripped:
            return True
        lower = stripped.lower()
        return any(re.search(pat, lower) for pat in self.UNCLEAR_PATTERNS)

    def classify(
        self,
        customer_text: str,
        base_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Classify customer text and extract reservation parameters using the
        existing intent-classification implementation.

        Args:
            customer_text: The transcribed customer speech string.
            base_date: Optional base calendar date for relative date calculations.

        Returns:
            Dict[str, Any]: Preserved output format containing:
                - intent: "booking", "inquiry", "cancellation", "modification", or "unknown"
                - party_size: int or None
                - date: str ("YYYY-MM-DD") or None
                - time: str ("HH:MM") or None
                - food_preference: dict of dietary tags to counts (e.g., {"vegetarian": 1})
                - summary: str
                - any auxiliary preferences (seating_preference, accessibility_requirement, etc.)

        Raises:
            IntentClassificationError or subclass: On API, configuration, or processing error.
        """
        # Step 1: Handle empty or unclear text gracefully
        is_empty = not customer_text or not str(customer_text).strip()
        if self.is_empty_or_unclear(customer_text):
            logger.warning("Empty or unclear customer text provided: '%s'", customer_text)
            return {
                "intent": "unknown",
                "party_size": None,
                "date": None,
                "time": None,
                "food_preference": {},
                "summary": "No speech or discernible request was detected in the audio.",
                "is_empty": is_empty,
                "is_empty_or_unclear": True,
            }

        clean_text = customer_text.strip()
        logger.info("Classifying customer text: \"%s\"", clean_text)

        # Step 2: Handle offline mock simulation mode
        if self.mock_mode:
            logger.info("  [Mock] Returning simulated intent classification result.")
            return {
                "intent": "booking",
                "party_size": 4,
                "date": "2026-09-25",
                "time": "20:00",
                "food_preference": {},
                "summary": "Customer wants to book a table for 4 people tonight at 8 PM."
            }

        # Step 3: Invoke existing intent classifier
        classifier_func = self._get_classifier_func()

        try:
            result = classifier_func(clean_text, base_date=base_date)
        except Exception as err:
            err_type = type(err).__name__
            safe_msg = mask_sensitive_data(str(err))
            logger.error("Intent classifier call encountered an exception (%s): %s", err_type, safe_msg)
            if any(net in err_type or net in safe_msg for net in ("Connect", "Timeout", "APIConnection", "RateLimit", "Network")):
                raise NetworkOrAPIError(f"Network error during intent classification: {safe_msg}") from err
            raise IntentClassificationAPIError(f"Intent classification call failed: {safe_msg}") from err

        # Step 4: Check for error returned by the classifier
        if isinstance(result, dict) and "error" in result:
            err_msg = mask_sensitive_data(str(result["error"]))
            logger.error("Intent classifier returned an error: %s", err_msg)
            if "GROQ_API_KEY" in err_msg or "API key" in err_msg:
                raise IntentClassificationConfigError("API key configuration error.")
            if any(net in err_msg for net in ("Connect", "Timeout", "APIConnection", "RateLimit", "Network")):
                raise NetworkOrAPIError(f"Network error: {err_msg}")
            raise IntentClassificationAPIError(f"Intent classification failed: {err_msg}")

        # Step 5: Preserve and return the exact output format
        # Ensure mandatory schema fields are present
        preserved_output: Dict[str, Any] = {
            "intent": result.get("intent", "booking"),
            "party_size": result.get("party_size"),
            "date": result.get("date"),
            "time": result.get("time"),
            "food_preference": result.get("food_preference", {}),
            "summary": result.get("summary", ""),
        }

        # Preserve any auxiliary extracted fields (seating_preference, celebration_requirement, etc.)
        for key, val in result.items():
            if key not in preserved_output and key != "error":
                preserved_output[key] = val

        logger.info("Classification completed: intent='%s', party_size=%s, date=%s, time=%s",
                    preserved_output["intent"], preserved_output["party_size"],
                    preserved_output["date"], preserved_output["time"])

        return preserved_output

    def safe_classify(
        self,
        customer_text: str,
        base_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Classifies customer text with complete error immunity.
        Never raises exceptions; on failure, logs technical details and returns
        a structured fallback intent dictionary so the conversation can proceed.
        """
        try:
            return self.classify(customer_text, base_date=base_date)
        except NetworkOrAPIError as err:
            logger.error("safe_classify caught network error: %s", err)
            return {
                "intent": "unknown",
                "party_size": None,
                "date": None,
                "time": None,
                "food_preference": {},
                "summary": "External service connection failure during intent classification.",
                "error_type": "network_error",
                "is_error": True,
            }
        except Exception as err:
            logger.error("safe_classify caught classification failure: %s", err, exc_info=True)
            return {
                "intent": "unknown",
                "party_size": None,
                "date": None,
                "time": None,
                "food_preference": {},
                "summary": "Intent classification failed.",
                "error_type": "classification_failed",
                "is_error": True,
            }
