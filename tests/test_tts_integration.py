"""
Unit and integration tests for Text-to-Speech (TTS) integration stage.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from voice_adapter import (
    TTSEmptyInputError,
    TTSGenerationError,
    VoiceProcessingAdapter,
)
from main import VoiceIntentOrchestrator


class TestTTSIntegration(unittest.TestCase):

    def setUp(self):
        self.adapter = VoiceProcessingAdapter()

    def test_empty_text_rejection(self):
        """Verify empty or whitespace-only text raises TTSEmptyInputError."""
        with self.assertRaises(TTSEmptyInputError):
            self.adapter.synthesize_speech("")

        with self.assertRaises(TTSEmptyInputError):
            self.adapter.synthesize_speech("    ")

    def test_mock_speech_synthesis(self):
        """Verify mock TTS produces expected audio file without network calls."""
        class MockClient:
            pass

        mock_adapter = VoiceProcessingAdapter(mock_client=MockClient())
        test_out = config.RESPONSES_DIR / "test_mock_tts.mp3"
        try:
            result_path = mock_adapter.synthesize_speech("Hello world", output_path=test_out)
            self.assertTrue(result_path.exists())
            self.assertGreater(result_path.stat().st_size, 0)
        finally:
            if test_out.exists():
                test_out.unlink()

    def test_live_speech_synthesis(self):
        """Verify existing voice-processing TTS synthesizes response text into valid audio file."""
        test_out = config.RESPONSES_DIR / "test_live_tts.mp3"
        try:
            result_path = self.adapter.synthesize_speech(
                text="Your table for four guests has been confirmed. Thank you.",
                output_path=test_out,
            )
            self.assertTrue(result_path.exists())
            self.assertGreater(result_path.stat().st_size, 1000)  # File size should be > 1KB
        finally:
            if test_out.exists():
                test_out.unlink()

    def test_orchestrator_text_to_audio_flow(self):
        """Verify full orchestrator text -> intent -> response -> TTS pipeline."""
        orchestrator = VoiceIntentOrchestrator(mock_mode=True)
        test_audio_out = config.RESPONSES_DIR / "test_flow_tts.mp3"
        try:
            result = orchestrator.process_text(
                customer_text="Table for two tonight at 8 PM",
                output_audio_path=test_audio_out,
                generate_audio=True,
            )
            self.assertEqual(result["status"], "success")
            self.assertIsNotNone(result["response_text"])
            self.assertIsNotNone(result["audio_output"])
            self.assertTrue(Path(result["audio_output"]).exists())
        finally:
            if test_audio_out.exists():
                test_audio_out.unlink()


if __name__ == "__main__":
    unittest.main()
