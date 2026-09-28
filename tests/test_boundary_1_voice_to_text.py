"""
Boundary 1 Tests: Audio file → voice-processing → text.

Tests the first integration boundary:
- Feeding customer audio file to VoiceProcessingAdapter.
- Calling existing SpeechToTextService from Audio-Conversation-Voice-Response.
- Returning transcribed customer text without altering existing STT logic.
- Verifying both successful transcriptions and all failure/edge cases.
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
    AudioEmptyError,
    AudioFileNotFoundError,
    AudioFormatError,
    NetworkOrAPIError,
    TranscriptionError,
    VoiceProcessingAdapter,
    VoiceProcessingError,
)


class TestBoundary1VoiceToText(unittest.TestCase):
    """Integration Boundary 1: Audio file -> voice-processing -> text."""

    def setUp(self):
        self.adapter = VoiceProcessingAdapter()

    # -----------------------------------------------------------------------
    # Success Cases
    # -----------------------------------------------------------------------
    def test_successful_mock_transcription(self):
        """Verify successful transcription returns string from existing service interface."""
        class MockClient:
            class Audio:
                class Transcriptions:
                    def create(self, *args, **kwargs):
                        class Result:
                            text = "Table for four on Friday at 8 PM under Sarah."
                        return Result()
                transcriptions = Transcriptions()
            audio = Audio()

        mock_adapter = VoiceProcessingAdapter(mock_client=MockClient())
        test_audio = config.AUDIO_DIR / "b1_mock_sample.wav"
        test_audio.write_bytes(b"[MOCK RIFF WAV DATA]")

        try:
            transcript = mock_adapter.transcribe(test_audio)
            self.assertIsInstance(transcript, str)
            self.assertEqual(transcript, "Table for four on Friday at 8 PM under Sarah.")
        finally:
            if test_audio.exists():
                test_audio.unlink()

    def test_successful_live_audio_transcription(self):
        """Verify real recorded customer audio is accurately transcribed via existing service."""
        sample_audio = config.AUDIO_DIR / "sample_customer_audio.wav"
        if not sample_audio.exists():
            self.skipTest("Sample customer audio file not present in audio/ directory.")

        transcript = self.adapter.transcribe(sample_audio)
        self.assertIsInstance(transcript, str)
        self.assertGreater(len(transcript), 20)
        # Verify content from the actual customer audio
        self.assertIn("birthday", transcript.lower())
        self.assertIn("sarah", transcript.lower())

    def test_supported_audio_formats(self):
        """Verify supported audio formats (.wav, .mp3, .m4a, .flac, .ogg) are accepted."""
        for ext in config.SUPPORTED_AUDIO_EXTENSIONS:
            dummy_file = config.AUDIO_DIR / f"test_format{ext}"
            dummy_file.write_bytes(b"[AUDIO SAMPLE BYTES]")
            try:
                validated = self.adapter.validate_audio(dummy_file)
                self.assertEqual(validated.suffix.lower(), ext)
            finally:
                if dummy_file.exists():
                    dummy_file.unlink()

    # -----------------------------------------------------------------------
    # Failure Cases & Edge Cases
    # -----------------------------------------------------------------------
    def test_missing_audio_file(self):
        """Verify missing audio file raises AudioFileNotFoundError."""
        missing = config.AUDIO_DIR / "non_existent_audio_file.wav"
        with self.assertRaises(AudioFileNotFoundError):
            self.adapter.transcribe(missing)

    def test_unsupported_audio_format(self):
        """Verify unsupported format (.txt, .pdf, .xyz) raises AudioFormatError."""
        bad_file = config.AUDIO_DIR / "unsupported_audio.xyz"
        bad_file.write_text("not an audio file")
        try:
            with self.assertRaises(AudioFormatError):
                self.adapter.transcribe(bad_file)
        finally:
            if bad_file.exists():
                bad_file.unlink()

    def test_empty_audio_file(self):
        """Verify 0-byte audio file raises AudioEmptyError."""
        empty_file = config.AUDIO_DIR / "empty_0_bytes.wav"
        empty_file.write_bytes(b"")
        try:
            with self.assertRaises(AudioEmptyError):
                self.adapter.transcribe(empty_file)
        finally:
            if empty_file.exists():
                empty_file.unlink()

    def test_directory_provided_instead_of_file(self):
        """Verify passing a directory path raises VoiceProcessingError."""
        with self.assertRaises(VoiceProcessingError):
            self.adapter.validate_audio(config.AUDIO_DIR)

    def test_unrecognized_or_empty_speech(self):
        """Verify unrecognized speech patterns return normalized empty string for graceful handling."""
        unclear_samples = [
            "[no speech detected in audio file]",
            "[unclear audio]",
            "[music]",
            "[blank_audio]",
            "   ",
            "...",
        ]
        for pattern in unclear_samples:
            self.assertTrue(
                self.adapter.is_unrecognized_or_empty(pattern),
                f"Pattern '{pattern}' should be detected as unrecognized/empty."
            )

    def test_network_or_api_failure_handling(self):
        """Verify network or remote connection errors are mapped to NetworkOrAPIError."""
        dummy_audio = config.AUDIO_DIR / "b1_net_fail.wav"
        dummy_audio.write_bytes(b"[AUDIO BYTES]")

        try:
            with patch.object(
                self.adapter,
                "_get_stt_service",
                return_value=MagicMock(transcribe=MagicMock(side_effect=Exception("APIConnectionError: Failed to connect to api.groq.com"))),
            ):
                with self.assertRaises(NetworkOrAPIError):
                    self.adapter.transcribe(dummy_audio)
        finally:
            if dummy_audio.exists():
                dummy_audio.unlink()

    def test_stt_transcription_exception_handling(self):
        """Verify unexpected STT failures raise TranscriptionError."""
        dummy_audio = config.AUDIO_DIR / "b1_stt_fail.wav"
        dummy_audio.write_bytes(b"[AUDIO BYTES]")

        try:
            with patch.object(
                self.adapter,
                "_get_stt_service",
                return_value=MagicMock(transcribe=MagicMock(side_effect=RuntimeError("Whisper model segmentation fault"))),
            ):
                with self.assertRaises(TranscriptionError):
                    self.adapter.transcribe(dummy_audio)
        finally:
            if dummy_audio.exists():
                dummy_audio.unlink()


if __name__ == "__main__":
    unittest.main()
