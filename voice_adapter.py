"""
Voice Processing Adapter Module.

Acts as an abstraction and decoupling layer between the integration project
and the existing voice-processing subsystem.

Does not re-implement or duplicate Speech-to-Text or Text-to-Speech logic.
Instead, it dynamically interfaces with the existing SpeechToTextService and
TextToSpeechService, providing robust error handling and isolation for the
integration layer.
"""

import logging
import os
import sys
import re
from pathlib import Path
from typing import Any, Optional, Union

import config
from sanitizer import mask_sensitive_data

logger = logging.getLogger("VoiceProcessingAdapter")


# ---------------------------------------------------------------------------
# Integration-Level Exceptions
# ---------------------------------------------------------------------------

class VoiceProcessingError(Exception):
    """Base exception for all voice-processing integration errors."""
    pass


class AudioFileNotFoundError(VoiceProcessingError):
    """Raised when the specified audio file cannot be found."""
    pass


class AudioFormatError(VoiceProcessingError):
    """Raised when the provided audio file has an unsupported extension."""
    pass


class AudioEmptyError(VoiceProcessingError):
    """Raised when the audio file exists but contains 0 bytes."""
    pass


class VoiceProcessingConfigError(VoiceProcessingError):
    """Raised when the voice-processing project or necessary configuration is missing."""
    pass


class TranscriptionError(VoiceProcessingError):
    """Raised when the speech-to-text service encounters a failure during transcription."""
    pass


class UnrecognizedSpeechError(VoiceProcessingError):
    """Raised when audio speech is unintelligible, muffled, silence, or unrecognized."""
    pass


class TTSError(VoiceProcessingError):
    """Base exception for Text-to-Speech synthesis errors."""
    pass


class TTSEmptyInputError(TTSError):
    """Raised when the text to synthesize is empty or whitespace-only."""
    pass


class TTSGenerationError(TTSError):
    """Raised when speech synthesis fails or cannot write the audio file."""
    pass


class TTSOutputInvalidError(TTSError):
    """Raised when generated audio file is missing or contains 0 bytes."""
    pass


class NetworkOrAPIError(VoiceProcessingError):
    """Raised when external speech API or network connection encounters a failure."""
    pass


# ---------------------------------------------------------------------------
# Voice Processing Adapter Class
# ---------------------------------------------------------------------------

class VoiceProcessingAdapter:
    """
    Adapter that delegates audio speech-to-text transcription and text-to-speech
    synthesis to the existing voice-processing implementation without modifying
    or duplicating its code.
    """

    def __init__(
        self,
        voice_project_dir: Optional[Path] = None,
        mock_client: Optional[Any] = None,
    ):
        """
        Initialize the adapter.

        Args:
            voice_project_dir: Path to the existing voice-processing project directory.
                               Defaults to config.VOICE_PROCESSING_DIR.
            mock_client: Optional mock client injected for testing/offline simulation.
        """
        self.voice_project_dir = voice_project_dir or config.VOICE_PROCESSING_DIR
        self.mock_client = mock_client
        self._stt_service = None
        self._tts_service = None

        self._ensure_project_accessible()

    def _ensure_project_accessible(self) -> None:
        """
        Verify that the voice-processing project exists and is accessible.
        Adds its directory to sys.path so its internal modules can be imported.
        """
        if not self.voice_project_dir or not self.voice_project_dir.exists():
            raise VoiceProcessingConfigError(
                f"Voice-processing project directory not found at: '{self.voice_project_dir}'. "
                "Please verify the folder exists in the parent directory or set VOICE_PROCESSING_DIR in .env."
            )

        # Inject project directory to sys.path if not already present
        proj_dir_str = str(self.voice_project_dir.resolve())
        if proj_dir_str not in sys.path:
            sys.path.insert(0, proj_dir_str)
            logger.debug("Added voice-processing directory to sys.path: %s", proj_dir_str)

    def _get_stt_service(self) -> Any:
        """
        Lazily import and initialize SpeechToTextService from the existing project.
        """
        if self._stt_service is not None:
            return self._stt_service

        try:
            from src.stt_service import SpeechToTextService
            if self.mock_client:
                self._stt_service = SpeechToTextService(client=self.mock_client)
            else:
                self._stt_service = SpeechToTextService()
            return self._stt_service
        except ImportError as err:
            raise VoiceProcessingConfigError(
                f"Failed to import SpeechToTextService from voice-processing project: {err}. "
                "Ensure dependencies are installed: pip install -r requirements.txt"
            ) from err

    def _get_tts_service(self) -> Any:
        """
        Lazily import and initialize TextToSpeechService from the existing project.
        """
        if self._tts_service is not None:
            return self._tts_service

        try:
            from src.tts_service import TextToSpeechService
            if self.mock_client:
                self._tts_service = TextToSpeechService(
                    client=self.mock_client,
                    output_dir=config.RESPONSES_DIR,
                )
            else:
                self._tts_service = TextToSpeechService(
                    output_dir=config.RESPONSES_DIR,
                )
            return self._tts_service
        except ImportError as err:
            raise VoiceProcessingConfigError(
                f"Failed to import TextToSpeechService from voice-processing project: {err}. "
                "Ensure dependencies are installed: pip install -r requirements.txt"
            ) from err

    def validate_audio(self, audio_path: Union[str, Path]) -> Path:
        """
        Validate input audio file existence, regular file status, extension, and size.

        Args:
            audio_path: Path to the customer audio file.

        Returns:
            Path: Resolved Path object.

        Raises:
            AudioFileNotFoundError: If the file does not exist.
            AudioFormatError: If the format is not in supported audio formats.
            AudioEmptyError: If the file is 0 bytes.
            VoiceProcessingError: If the path is empty or points to a directory.
        """
        if not audio_path or not str(audio_path).strip():
            raise VoiceProcessingError("Audio file path cannot be empty.")

        resolved = Path(audio_path).expanduser().resolve()

        if not resolved.exists():
            raise AudioFileNotFoundError(f"Audio file not found: '{resolved}'")

        if not resolved.is_file():
            raise VoiceProcessingError(f"Expected a file path, but found a directory: '{resolved}'")

        if resolved.suffix.lower() not in config.SUPPORTED_AUDIO_EXTENSIONS:
            supported = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
            raise AudioFormatError(
                f"Unsupported audio format '{resolved.suffix}'. Supported formats: {supported}"
            )

        if resolved.stat().st_size == 0:
            raise AudioEmptyError(f"Audio file is empty (0 bytes): '{resolved.name}'")

        return resolved

    @staticmethod
    def is_unrecognized_or_empty(text: Optional[str]) -> bool:
        """
        Check if speech-to-text output is empty, silence, or unintelligible.
        """
        if not text:
            return True
        stripped = text.strip()
        if not stripped:
            return True
        unclear_patterns = [
            r"\[no speech detected.*\]",
            r"\[unclear.*\]",
            r"\[music.*\]",
            r"\[inaudible.*\]",
            r"\[blank_audio.*\]",
            r"^\s*$",
            r"^[.\s,-]+$",
        ]
        lower = stripped.lower()
        return any(re.search(pat, lower) for pat in unclear_patterns)

    def transcribe(self, audio_path: Union[str, Path]) -> str:
        """
        Transcribe an audio file into customer text using the existing voice-processing system.

        Args:
            audio_path: Path to the customer audio file.

        Returns:
            str: Transcribed customer text (or empty string if speech is unrecognized/empty).

        Raises:
            AudioFileNotFoundError: If the audio file does not exist.
            AudioFormatError: If the format is unsupported.
            AudioEmptyError: If the file is 0 bytes.
            NetworkOrAPIError: On external API or network failure.
            VoiceProcessingError or subclass: On configuration or system errors.
        """
        # Step 1: Validate audio file input
        valid_path = self.validate_audio(audio_path)
        logger.info("Validated audio file: %s (%.2f KB)", valid_path.name, valid_path.stat().st_size / 1024)

        # Step 2: Acquire existing STT service
        stt = self._get_stt_service()

        # Step 3: Perform transcription via existing implementation
        try:
            logger.info("Delegating to voice-processing SpeechToTextService...")
            transcribed_text = stt.transcribe(valid_path)

            if self.is_unrecognized_or_empty(transcribed_text):
                logger.warning("Transcription resulted in empty or unrecognized speech.")
                return ""

            logger.info("Transcription completed successfully.")
            return str(transcribed_text).strip()

        except Exception as err:
            err_type = type(err).__name__
            safe_err_msg = mask_sensitive_data(str(err))
            logger.error("STT error occurred (%s): %s", err_type, safe_err_msg)

            # Map existing project's specific errors to integration exceptions
            if "AudioFileNotFound" in err_type:
                raise AudioFileNotFoundError(f"Audio file not found: {valid_path.name}") from err
            elif "UnsupportedFormat" in err_type:
                raise AudioFormatError(f"Unsupported format: {valid_path.suffix}") from err
            elif "InvalidAudio" in err_type or "Empty" in err_type:
                raise AudioEmptyError(f"Audio file is empty or invalid: {valid_path.name}") from err
            elif "ConfigurationError" in err_type:
                raise VoiceProcessingConfigError(
                    "Voice-processing configuration error. Please ensure GROQ_API_KEY is configured."
                ) from err
            elif any(net in err_type or net in safe_err_msg for net in ("Connect", "Timeout", "APIConnection", "RateLimit", "Network")):
                raise NetworkOrAPIError(f"Voice service network or API connection error: {safe_err_msg}") from err
            else:
                raise TranscriptionError(f"Speech-to-text transcription failed: {safe_err_msg}") from err

    def synthesize_speech(
        self,
        text: str,
        output_path: Optional[Union[str, Path]] = None,
        voice: Optional[str] = None,
    ) -> Path:
        """
        Synthesize speech from customer-facing response text using the existing
        Text-to-Speech service from the voice-processing project.
        Verifies that the generated audio file is written and non-empty.

        Args:
            text: Customer-facing text to convert to speech.
            output_path: Optional custom path to save the generated audio file.
            voice: Optional voice descriptor or language override.

        Returns:
            Path: Resolved Path object to the generated playable audio file (.mp3).

        Raises:
            TTSEmptyInputError: If text is empty or whitespace-only.
            TTSOutputInvalidError: If generated file is missing or 0 bytes.
            NetworkOrAPIError: On network or API connection error.
            TTSGenerationError: If speech synthesis fails.
        """
        if not text or not str(text).strip():
            raise TTSEmptyInputError("Cannot synthesize speech from empty or whitespace-only text.")

        clean_text = str(text).strip()
        logger.info("Delegating speech synthesis to voice-processing TextToSpeechService (%d chars)...", len(clean_text))

        # Check for mock client simulation
        if self.mock_client is not None:
            dest = Path(output_path).resolve() if output_path else (config.RESPONSES_DIR / "response_mock.mp3")
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Write valid MPEG frame placeholder for tests
            mock_audio = b"\xff\xfb\x90\x00" + (b"\x00" * 414)
            dest.write_bytes(mock_audio * 5)
            if not dest.exists() or dest.stat().st_size == 0:
                raise TTSOutputInvalidError("Generated mock audio file is missing or 0 bytes.")
            logger.info("  [Mock] Generated mock response audio at: %s", dest)
            return dest

        # Delegate to existing TextToSpeechService
        tts_service = self._get_tts_service()

        try:
            target_file = tts_service.synthesize_speech(
                text=clean_text,
                output_path=output_path,
            )
            resolved_target = Path(target_file).resolve()

            # Verify generated file existence and validity (Case 11)
            if not resolved_target.exists():
                raise TTSOutputInvalidError(f"Generated audio file does not exist on disk: {resolved_target.name}")
            if resolved_target.stat().st_size == 0:
                raise TTSOutputInvalidError(f"Generated audio file is invalid (0 bytes): {resolved_target.name}")

            logger.info("Speech synthesis completed: %s (%.2f KB)", resolved_target.name, resolved_target.stat().st_size / 1024)
            return resolved_target

        except Exception as err:
            if isinstance(err, (TTSEmptyInputError, TTSOutputInvalidError)):
                raise

            err_type = type(err).__name__
            safe_err_msg = mask_sensitive_data(str(err))
            logger.error("TTS synthesis error (%s): %s", err_type, safe_err_msg)

            if "EmptyInput" in err_type:
                raise TTSEmptyInputError(str(err)) from err
            elif any(net in err_type or net in safe_err_msg for net in ("Connect", "Timeout", "APIConnection", "RateLimit", "Network")):
                raise NetworkOrAPIError(f"Text-to-speech network or API connection error: {safe_err_msg}") from err
            raise TTSGenerationError(f"Text-to-speech synthesis failed: {safe_err_msg}") from err
