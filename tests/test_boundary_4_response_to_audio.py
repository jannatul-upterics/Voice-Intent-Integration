"""
Boundary 4 Tests: Response text → TTS → audio file.

Tests the fourth integration boundary:
- Receiving customer-facing response text.
- Passing response text to TextToSpeechService from Audio-Conversation-Voice-Response.
- Generating a valid, non-empty playable .mp3 audio file in responses/.
- Verifying empty input rejection, file verification, network errors, and TTS failures.
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
from voice_adapter import (
    NetworkOrAPIError,
    TTSEmptyInputError,
    TTSGenerationError,
    TTSOutputInvalidError,
    VoiceProcessingAdapter,
)


class TestBoundary4ResponseToAudio(unittest.TestCase):
    """Integration Boundary 4: Response text -> TTS -> audio file."""

    def setUp(self):
        self.adapter = VoiceProcessingAdapter()

    # -----------------------------------------------------------------------
    # Success Cases
    # -----------------------------------------------------------------------
    def test_successful_mock_speech_synthesis(self):
        """Verify mock TTS produces valid .mp3 audio file on disk."""
        class MockClient:
            pass

        mock_adapter = VoiceProcessingAdapter(mock_client=MockClient())
        test_out = config.RESPONSES_DIR / "b4_mock_output.mp3"

        try:
            result_path = mock_adapter.synthesize_speech(
                text="Your table for four guests has been confirmed.",
                output_path=test_out,
            )
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path.suffix.lower(), ".mp3")
            self.assertGreater(result_path.stat().st_size, 0)
        finally:
            if test_out.exists():
                test_out.unlink()

    def test_successful_live_speech_synthesis(self):
        """Verify live TextToSpeechService synthesizes response text into valid audio file."""
        test_out = config.RESPONSES_DIR / "b4_live_output.mp3"
        sample_text = "Certainly! I have reserved a table for two guests on Friday at 7 PM."

        try:
            result_path = self.adapter.synthesize_speech(
                text=sample_text,
                output_path=test_out,
            )
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path.suffix.lower(), ".mp3")
            # A valid synthesized speech file of ~68 chars should exceed 1000 bytes
            self.assertGreater(result_path.stat().st_size, 1000)
        finally:
            if test_out.exists():
                test_out.unlink()

    def test_default_output_directory(self):
        """Verify omitting output_path automatically saves into config.RESPONSES_DIR."""
        class MockClient:
            pass

        mock_adapter = VoiceProcessingAdapter(mock_client=MockClient())
        result_path = mock_adapter.synthesize_speech("Testing default output path")
        try:
            self.assertEqual(result_path.parent.resolve(), config.RESPONSES_DIR.resolve())
            self.assertTrue(result_path.exists())
        finally:
            if result_path.exists():
                result_path.unlink()

    # -----------------------------------------------------------------------
    # Failure Cases & Edge Cases
    # -----------------------------------------------------------------------
    def test_empty_text_input_rejected(self):
        """Verify empty string raises TTSEmptyInputError."""
        with self.assertRaises(TTSEmptyInputError):
            self.adapter.synthesize_speech("")

    def test_whitespace_text_input_rejected(self):
        """Verify whitespace-only string raises TTSEmptyInputError."""
        with self.assertRaises(TTSEmptyInputError):
            self.adapter.synthesize_speech("      \t\n  ")

    def test_none_text_input_rejected(self):
        """Verify None text input raises TTSEmptyInputError."""
        with self.assertRaises(TTSEmptyInputError):
            self.adapter.synthesize_speech(None)

    def test_tts_service_generation_failure(self):
        """Verify TTS engine failure raises TTSGenerationError."""
        with patch.object(
            self.adapter,
            "_get_tts_service",
            return_value=MagicMock(synthesize_speech=MagicMock(side_effect=RuntimeError("Groq TTS internal error"))),
        ):
            with self.assertRaises(TTSGenerationError):
                self.adapter.synthesize_speech("Sample text for synthesis")

    def test_tts_network_failure(self):
        """Verify network connection timeout during TTS raises NetworkOrAPIError."""
        with patch.object(
            self.adapter,
            "_get_tts_service",
            return_value=MagicMock(synthesize_speech=MagicMock(side_effect=Exception("APIConnectionError: Failed to connect"))),
        ):
            with self.assertRaises(NetworkOrAPIError):
                self.adapter.synthesize_speech("Sample text for synthesis")

    def test_generated_audio_file_missing_on_disk(self):
        """Verify TTSOutputInvalidError is raised if the returned audio file does not exist."""
        ghost_path = config.RESPONSES_DIR / "ghost_file.mp3"
        with patch.object(
            self.adapter,
            "_get_tts_service",
            return_value=MagicMock(synthesize_speech=MagicMock(return_value=ghost_path)),
        ):
            with self.assertRaises(TTSOutputInvalidError):
                self.adapter.synthesize_speech("Sample text for synthesis")

    def test_generated_audio_file_zero_bytes(self):
        """Verify TTSOutputInvalidError is raised if the generated audio file has 0 bytes."""
        empty_mp3 = config.RESPONSES_DIR / "b4_empty.mp3"
        empty_mp3.write_bytes(b"")

        try:
            with patch.object(
                self.adapter,
                "_get_tts_service",
                return_value=MagicMock(synthesize_speech=MagicMock(return_value=empty_mp3)),
            ):
                with self.assertRaises(TTSOutputInvalidError):
                    self.adapter.synthesize_speech("Sample text for synthesis")
        finally:
            if empty_mp3.exists():
                empty_mp3.unlink()


if __name__ == "__main__":
    unittest.main()
