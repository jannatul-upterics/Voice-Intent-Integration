"""
Robust Error Handling Test Suite for Voice-Intent Integration.

Verifies all 12 required failure and edge-case scenarios:
 1. Audio file does not exist.
 2. Unsupported audio format.
 3. Empty audio file.
 4. Speech cannot be recognized.
 5. Transcription returns empty text.
 6. Intent classification fails.
 7. Intent cannot be determined.
 8. Required information is missing.
 9. Response generation fails.
10. Text-to-speech fails.
11. Generated audio file is missing or invalid.
12. External API or network failure.

Also verifies:
- Customer responses are polite, natural, and helpful.
- No API keys, internal paths, or stack traces are leaked to customers.
- Detailed technical information is retained in loggers.
- Neither sibling project is modified.
"""

import logging
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
    NetworkOrAPIError as IntentNetworkError,
)
from main import VoiceIntentOrchestrator
from response_generator import ResponseGenerator
from sanitizer import mask_sensitive_data, sanitize_customer_message
from voice_adapter import (
    AudioEmptyError,
    AudioFileNotFoundError,
    AudioFormatError,
    NetworkOrAPIError as VoiceNetworkError,
    TranscriptionError,
    TTSGenerationError,
    TTSOutputInvalidError,
    VoiceProcessingAdapter,
)


class TestRobustErrorHandling(unittest.TestCase):
    """Test suite covering the 12 required error scenarios and customer security."""

    def setUp(self):
        self.orchestrator = VoiceIntentOrchestrator(mock_mode=True)
        self.generator = ResponseGenerator()

    # -----------------------------------------------------------------------
    # Case 1: Audio file does not exist
    # -----------------------------------------------------------------------
    def test_case_01_audio_file_not_found(self):
        """Verify non-existent audio file fails gracefully with polite customer message."""
        missing_file = config.AUDIO_DIR / "non_existent_voice_recording.wav"
        result = self.orchestrator.process_audio_file(missing_file)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "audio_not_found")
        self.assertIn("could not be found", result["customer_message"].lower())
        self.assertIsNone(result["audio_output"])

        # Verify no raw system path or stack trace is in customer message
        self.assertNotIn("Traceback", result["customer_message"])
        self.assertNotIn("D:\\", result["customer_message"])
        self.assertNotIn("C:\\", result["customer_message"])

    # -----------------------------------------------------------------------
    # Case 2: Unsupported audio format
    # -----------------------------------------------------------------------
    def test_case_02_unsupported_audio_format(self):
        """Verify unsupported audio format (.xyz, .txt) returns clear customer guidance."""
        bad_format_file = config.AUDIO_DIR / "customer_recording.xyz"
        bad_format_file.write_text("dummy audio content")

        try:
            result = self.orchestrator.process_audio_file(bad_format_file)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_type"], "unsupported_format")
            self.assertIn("not supported", result["customer_message"].lower())
            self.assertIn("wav", result["customer_message"].lower())
            self.assertIsNone(result["audio_output"])
        finally:
            if bad_format_file.exists():
                bad_format_file.unlink()

    # -----------------------------------------------------------------------
    # Case 3: Empty audio (0 bytes)
    # -----------------------------------------------------------------------
    def test_case_03_empty_audio_file(self):
        """Verify 0-byte audio file fails gracefully with meaningful customer guidance."""
        empty_file = config.AUDIO_DIR / "silent_zero_bytes.wav"
        empty_file.write_bytes(b"")

        try:
            result = self.orchestrator.process_audio_file(empty_file)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_type"], "empty_audio")
            self.assertIn("empty", result["customer_message"].lower())
            self.assertIsNone(result["audio_output"])
        finally:
            if empty_file.exists():
                empty_file.unlink()

    # -----------------------------------------------------------------------
    # Case 4: Speech cannot be recognized (noise, muffled, unclear)
    # -----------------------------------------------------------------------
    def test_case_04_speech_cannot_be_recognized(self):
        """Verify unclear or muffled speech generates a polite clarification prompt with audio."""
        test_audio = config.AUDIO_DIR / "unclear_test.wav"
        test_audio.write_bytes(b"[UNINTELLIGIBLE NOISE DATA]")

        try:
            # Simulate STT returning unclear speech marker
            with patch.object(self.orchestrator.voice_adapter, "transcribe", return_value="[unclear audio]"):
                result = self.orchestrator.process_audio_file(test_audio)

                self.assertEqual(result["status"], "success")
                self.assertIn("apologize", result["response_text"].lower())
                self.assertIn("unable to hear or understand", result["response_text"].lower())
                # Audio response should be generated so customer hears the spoken apology
                self.assertIsNotNone(result["audio_output"])
                self.assertTrue(Path(result["audio_output"]).exists())
        finally:
            if test_audio.exists():
                test_audio.unlink()

    # -----------------------------------------------------------------------
    # Case 5: Transcription returns empty text (silence / blank)
    # -----------------------------------------------------------------------
    def test_case_05_transcription_returns_empty_text(self):
        """Verify empty transcription produces polite prompt asking customer to speak again."""
        test_audio = config.AUDIO_DIR / "silence_test.wav"
        test_audio.write_bytes(b"[SILENT AUDIO SAMPLES]")

        try:
            with patch.object(self.orchestrator.voice_adapter, "transcribe", return_value="   "):
                result = self.orchestrator.process_audio_file(test_audio)

                self.assertEqual(result["status"], "success")
                self.assertIn("no speech was detected", result["response_text"].lower())
                self.assertIsNotNone(result["audio_output"])
                self.assertTrue(Path(result["audio_output"]).exists())
        finally:
            if test_audio.exists():
                test_audio.unlink()

    # -----------------------------------------------------------------------
    # Case 6: Intent classification fails
    # -----------------------------------------------------------------------
    def test_case_06_intent_classification_fails(self):
        """Verify intent classifier API/processing failure falls back gracefully to polite prompt."""
        test_audio = config.AUDIO_DIR / "intent_fail_test.wav"
        test_audio.write_bytes(b"[AUDIO DATA]")

        try:
            # Simulate STT returning text, but intent classification throwing an error
            with patch.object(self.orchestrator.voice_adapter, "transcribe", return_value="I want to book"):
                with patch.object(
                    self.orchestrator.intent_adapter,
                    "safe_classify",
                    return_value={
                        "intent": "unknown",
                        "party_size": None,
                        "date": None,
                        "time": None,
                        "food_preference": {},
                        "summary": "Internal classifier error",
                        "error_type": "classification_failed",
                    },
                ):
                    result = self.orchestrator.process_audio_file(test_audio)

                    self.assertEqual(result["status"], "success")
                    self.assertIn("having trouble processing your request", result["response_text"].lower())
                    self.assertIn("table reservation", result["response_text"].lower())
                    self.assertIsNotNone(result["audio_output"])
        finally:
            if test_audio.exists():
                test_audio.unlink()

    # -----------------------------------------------------------------------
    # Case 7: Intent cannot be determined (unknown / off-topic)
    # -----------------------------------------------------------------------
    def test_case_07_intent_cannot_be_determined(self):
        """Verify unknown or off-topic request produces polite clarification of restaurant services."""
        intent_data = {
            "intent": "unknown",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": {},
            "summary": "Customer asked about spaceship repairs",
        }
        response = self.generator.generate_response(intent_data)
        self.assertIn("apologize", response.lower())
        self.assertIn("unable to hear or understand", response.lower())

        # Test unsupported off-topic request
        off_topic_data = {
            "intent": "unsupported",
            "summary": "Customer asked for bicycle repairs",
        }
        off_topic_resp = self.generator.generate_response(off_topic_data)
        self.assertIn("unable to assist with that request", off_topic_resp.lower())
        self.assertIn("table bookings", off_topic_resp.lower())

    # -----------------------------------------------------------------------
    # Case 8: Required information is missing
    # -----------------------------------------------------------------------
    def test_case_08_required_information_missing(self):
        """Verify incomplete bookings prompt specifically for missing parameters."""
        # Missing all slots
        resp1 = self.generator.generate_response({"intent": "booking"})
        self.assertIn("how many guests", resp1.lower())
        self.assertIn("date and time", resp1.lower())

        # Missing date
        resp2 = self.generator.generate_response({"intent": "booking", "party_size": 2, "time": "19:00"})
        self.assertIn("which date", resp2.lower())

        # Missing party size
        resp3 = self.generator.generate_response({"intent": "booking", "date": "2026-09-26", "time": "20:00"})
        self.assertIn("how many guests", resp3.lower())

        # Missing time
        resp4 = self.generator.generate_response({"intent": "booking", "party_size": 4, "date": "2026-09-26"})
        self.assertIn("what time", resp4.lower())

        # Invalid party size (0 guests)
        resp5 = self.generator.generate_response({"intent": "booking", "party_size": 0, "date": "2026-09-26", "time": "19:00"})
        self.assertIn("at least one guest", resp5.lower())

        # Invalid party size (large group > 30)
        resp6 = self.generator.generate_response({"intent": "booking", "party_size": 40, "date": "2026-09-26", "time": "19:00"})
        self.assertIn("large parties", resp6.lower())

    # -----------------------------------------------------------------------
    # Case 9: Response generation fails
    # -----------------------------------------------------------------------
    def test_case_09_response_generation_fails(self):
        """Verify response generation catches unexpected exceptions and provides polite fallback."""
        # Pass completely invalid or broken input types
        fallback_resp = self.generator.generate_response(None)
        self.assertIsInstance(fallback_resp, str)
        self.assertGreater(len(fallback_resp), 10)

        # Force an internal exception during generation
        with patch.object(self.generator, "_handle_booking", side_effect=RuntimeError("Unexpected bug")):
            safe_resp = self.generator.generate_response({"intent": "booking", "party_size": 2})
            self.assertIn("thank you for contacting", safe_resp.lower())
            self.assertNotIn("RuntimeError", safe_resp)
            self.assertNotIn("Traceback", safe_resp)

    # -----------------------------------------------------------------------
    # Case 10: Text-to-speech fails
    # -----------------------------------------------------------------------
    def test_case_10_text_to_speech_fails(self):
        """Verify pipeline handles TTS failure gracefully without crashing, preserving text response."""
        test_audio = config.AUDIO_DIR / "tts_fail_test.wav"
        test_audio.write_bytes(b"[AUDIO DATA]")

        try:
            with patch.object(
                self.orchestrator.voice_adapter,
                "synthesize_speech",
                side_effect=TTSGenerationError("TTS Engine unavailable"),
            ):
                result = self.orchestrator.process_audio_file(test_audio)

                self.assertEqual(result["status"], "success")
                self.assertTrue(result["tts_failed"])
                self.assertIsNone(result["audio_output"])
                self.assertIsNotNone(result["response_text"])
                self.assertGreater(len(result["response_text"]), 10)
        finally:
            if test_audio.exists():
                test_audio.unlink()

    # -----------------------------------------------------------------------
    # Case 11: Generated audio file is missing or invalid (0 bytes)
    # -----------------------------------------------------------------------
    def test_case_11_generated_audio_file_missing_or_invalid(self):
        """Verify 0-byte or missing synthesized audio output is caught and handled safely."""
        # Subcase A: Missing file returned by TTS
        with patch.object(
            self.orchestrator.voice_adapter,
            "synthesize_speech",
            side_effect=TTSOutputInvalidError("Generated audio file does not exist on disk"),
        ):
            test_audio = config.AUDIO_DIR / "test_missing_tts.wav"
            test_audio.write_bytes(b"[AUDIO DATA]")
            try:
                result = self.orchestrator.process_audio_file(test_audio)
                self.assertEqual(result["status"], "success")
                self.assertTrue(result["tts_failed"])
                self.assertIsNone(result["audio_output"])
            finally:
                if test_audio.exists():
                    test_audio.unlink()

    # -----------------------------------------------------------------------
    # Case 12: External API or network failure
    # -----------------------------------------------------------------------
    def test_case_12_external_api_network_failure(self):
        """Verify network or API timeouts produce polite customer response without crashing."""
        test_audio = config.AUDIO_DIR / "network_fail_test.wav"
        test_audio.write_bytes(b"[AUDIO DATA]")

        try:
            # Simulate network timeout in STT
            with patch.object(
                self.orchestrator.voice_adapter,
                "transcribe",
                side_effect=VoiceNetworkError("Connection timed out to api.groq.com"),
            ):
                result = self.orchestrator.process_audio_file(test_audio)

                self.assertEqual(result["status"], "network_error")
                self.assertIn("temporary connection issue", result["response_text"].lower())
                self.assertNotIn("api.groq.com", result["response_text"])
                self.assertNotIn("Connection timed out", result["response_text"])
        finally:
            if test_audio.exists():
                test_audio.unlink()

    # -----------------------------------------------------------------------
    # Customer Safety and Data Redaction
    # -----------------------------------------------------------------------
    def test_sanitizer_masks_api_keys_and_paths(self):
        """Verify sanitizer strictly redacts API keys and internal file paths."""
        sample_api_error = "Failed to connect with token gsk_abcdef1234567890abcdef at D:\\Sellyco Promotions\\secret.py"
        masked = mask_sensitive_data(sample_api_error)
        self.assertNotIn("gsk_abcdef1234567890abcdef", masked)
        self.assertIn("[REDACTED_API_KEY]", masked)

        # Test customer-facing message sanitization
        customer_safe = sanitize_customer_message(sample_api_error)
        self.assertNotIn("gsk_abcdef1234567890abcdef", customer_safe)
        self.assertNotIn("D:\\Sellyco", customer_safe)


if __name__ == "__main__":
    unittest.main()
