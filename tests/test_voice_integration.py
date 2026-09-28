"""
Tests for Voice-Processing Integration Stage.
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
    AudioEmptyError,
    AudioFileNotFoundError,
    AudioFormatError,
    VoiceProcessingAdapter,
    VoiceProcessingConfigError,
)


class TestVoiceProcessingIntegration(unittest.TestCase):

    def setUp(self):
        self.adapter = VoiceProcessingAdapter()

    def test_voice_processing_project_detected(self):
        """Verify the sibling voice-processing project is detected and accessible."""
        self.assertIsNotNone(config.VOICE_PROCESSING_DIR)
        self.assertTrue(config.VOICE_PROCESSING_DIR.exists())
        self.assertTrue(self.adapter.voice_project_dir.exists())

    def test_missing_audio_file(self):
        """Verify non-existent audio file raises AudioFileNotFoundError gracefully."""
        non_existent = config.AUDIO_DIR / "non_existent_recording.wav"
        with self.assertRaises(AudioFileNotFoundError):
            self.adapter.transcribe(non_existent)

    def test_unsupported_audio_format(self):
        """Verify unsupported format (.txt, .xyz) raises AudioFormatError gracefully."""
        dummy_file = config.AUDIO_DIR / "test_unsupported.txt"
        dummy_file.write_text("Hello world")
        try:
            with self.assertRaises(AudioFormatError):
                self.adapter.transcribe(dummy_file)
        finally:
            if dummy_file.exists():
                dummy_file.unlink()

    def test_empty_audio_file(self):
        """Verify 0-byte audio file raises AudioEmptyError gracefully."""
        empty_file = config.AUDIO_DIR / "empty_test.wav"
        empty_file.write_bytes(b"")
        try:
            with self.assertRaises(AudioEmptyError):
                self.adapter.transcribe(empty_file)
        finally:
            if empty_file.exists():
                empty_file.unlink()

    def test_mock_transcription(self):
        """Verify offline mock transcription returns expected text."""
        class MockClient:
            class Audio:
                class Transcriptions:
                    def create(self, *args, **kwargs):
                        class Result:
                            text = "Table for two tomorrow at 7 PM please."
                        return Result()
                transcriptions = Transcriptions()
            audio = Audio()

        mock_adapter = VoiceProcessingAdapter(mock_client=MockClient())
        sample_file = config.AUDIO_DIR / "mock_test.wav"
        sample_file.write_bytes(b"[RIFF MOCK AUDIO DATA]")
        try:
            text = mock_adapter.transcribe(sample_file)
            self.assertEqual(text, "Table for two tomorrow at 7 PM please.")
        finally:
            if sample_file.exists():
                sample_file.unlink()

    def test_live_transcription_with_sample_recording(self):
        """Verify real recorded customer audio is successfully transcribed via existing voice-processing."""
        sample_file = config.AUDIO_DIR / "sample_customer_audio.wav"
        if not sample_file.exists():
            self.skipTest("Sample customer audio file not present in audio/ directory.")

        text = self.adapter.transcribe(sample_file)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 10)
        # Verify key content transcribed from the recorded audio
        self.assertIn("birthday", text.lower())
        self.assertIn("friday", text.lower())


if __name__ == "__main__":
    unittest.main()
