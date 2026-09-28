"""
Voice-Intent Integration Layer
Main Orchestration Entry Point

Complete End-to-End Pipeline:
  1. Receive customer audio.
  2. Send audio to the existing voice-processing project.
  3. Obtain the transcribed customer text.
  4. Send the text to the existing intent-classification project.
  5. Obtain the detected intent and extracted information.
  6. Generate an appropriate customer-facing text response based on the identified intent.
  7. Send the response text to the existing TTS functionality.
  8. Generate an audio response.
  9. Return the audio response to the user.

Clear Stage Logging:
  Audio received
  → Speech-to-text completed
  → Intent classification completed
  → Response generated
  → Text-to-speech completed
  → Audio response ready
"""

import argparse
import datetime
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

import config
from intent_adapter import (
    IntentClassificationAdapter,
    IntentClassificationAPIError,
    IntentClassificationConfigError,
    IntentClassificationError,
)
from response_generator import ResponseGenerator
from sanitizer import mask_sensitive_data, sanitize_customer_message
from voice_adapter import (
    AudioEmptyError,
    AudioFileNotFoundError,
    AudioFormatError,
    NetworkOrAPIError,
    TranscriptionError,
    TTSEmptyInputError,
    TTSGenerationError,
    TTSOutputInvalidError,
    TTSError,
    UnrecognizedSpeechError,
    VoiceProcessingAdapter,
    VoiceProcessingConfigError,
    VoiceProcessingError,
)

# Configure logging
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger("VoiceIntentIntegration")


class VoiceIntentOrchestrator:
    """
    Coordinates end-to-end data flow between voice-processing, intent-classification,
    and response synthesis without modifying or duplicating the core logic of either subsystem.
    """

    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.voice_adapter = VoiceProcessingAdapter(
            mock_client=self._build_mock_client() if mock_mode else None
        )
        self.intent_adapter = IntentClassificationAdapter(mock_mode=mock_mode)
        self.response_generator = ResponseGenerator()
        logger.info("Initialized VoiceIntentOrchestrator (Mock Mode: %s)", self.mock_mode)

    @staticmethod
    def _build_mock_client():
        class MockTranscriptions:
            def create(self, *args, **kwargs):
                class MockResult:
                    text = "I would like to book a table for four people tonight at 8 PM."
                return MockResult()

        class MockSpeech:
            def create(self, *args, **kwargs):
                class MockAudioResult:
                    content = (b"\xff\xfb\x90\x00" + (b"\x00" * 414)) * 5
                return MockAudioResult()

        class MockAudio:
            transcriptions = MockTranscriptions()
            speech = MockSpeech()

        class MockClient:
            audio = MockAudio()

        return MockClient()

    def process_audio_file(
        self,
        audio_path: Union[str, Path],
        output_audio_path: Optional[Union[str, Path]] = None,
        output_json_path: Optional[Union[str, Path]] = None,
        generate_audio: bool = True,
        save_intent_json: bool = True,
        raise_on_input_error: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes the full pipeline with robust error handling:
          1. Receive customer audio.
          2. Send audio to existing voice-processing (Speech-to-Text).
          3. Obtain transcribed customer text.
          4. Send text to existing intent-classification.
          5. Save intent classification result as a formatted JSON file.
          6. Generate appropriate customer-facing text response.
          7. Send response text to existing TTS functionality.
          8. Generate and save audio response file.
          9. Return paths to both JSON and audio response files.

        Robustly handles all failure modes:
          - Audio file does not exist (Case 1)
          - Unsupported audio format (Case 2)
          - Empty audio file (Case 3)
          - Speech cannot be recognized (Case 4)
          - Empty transcription text (Case 5)
          - Intent classification failure (Case 6)
          - Undetermined intent (Case 7)
          - Missing required reservation info (Case 8)
          - Response generation failure (Case 9)
          - Text-to-speech failure (Case 10)
          - Missing or 0-byte generated audio file (Case 11)
          - External API or network failure (Case 12)

        Args:
            audio_path: Path to customer audio file.
            output_audio_path: Optional destination path for synthesized response speech.
            output_json_path: Optional destination path for saved intent JSON output.
            generate_audio: If True, generates audio output via TTS.
            save_intent_json: If True, saves intent classification result to a .json file.
            raise_on_input_error: If True, raises exceptions on validation errors rather than returning error dict.

        Returns:
            Dict[str, Any]: Complete results including transcribed text, intent data,
                            json_output path, response text, and generated audio response path.
        """
        # -------------------------------------------------------------------
        # Stage 1: Audio received & validated (Cases 1, 2, 3)
        # -------------------------------------------------------------------
        try:
            valid_audio = self.voice_adapter.validate_audio(audio_path)
            file_size_kb = valid_audio.stat().st_size / 1024
            logger.info("Audio received: %s (%.2f KB)", valid_audio.name, file_size_kb)
        except (AudioFileNotFoundError, AudioFormatError, AudioEmptyError, VoiceProcessingError) as err:
            logger.error("Audio validation failure: %s", err, exc_info=True)
            if raise_on_input_error:
                raise

            if isinstance(err, AudioFileNotFoundError):
                cust_msg = "The requested audio recording could not be found. Please check the file path and try again."
                err_code = "audio_not_found"
            elif isinstance(err, AudioFormatError):
                supported = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
                cust_msg = f"The provided audio format is not supported. Please provide a standard audio file ({supported})."
                err_code = "unsupported_format"
            elif isinstance(err, AudioEmptyError):
                cust_msg = "The audio file is empty. Please provide an audio recording containing speech."
                err_code = "empty_audio"
            else:
                cust_msg = "Could not process the provided audio file. Please check the file and try again."
                err_code = "invalid_audio"

            return {
                "status": "error",
                "error_type": err_code,
                "customer_message": cust_msg,
                "audio_file": str(Path(audio_path).name) if audio_path else None,
                "customer_text": None,
                "extracted_text": None,
                "intent_classification": None,
                "json_output": None,
                "response_text": cust_msg,
                "audio_output": None,
            }

        # -------------------------------------------------------------------
        # Stage 2: Speech-to-text (Cases 4, 5, 12)
        # -------------------------------------------------------------------
        customer_text = ""
        stt_network_error = False
        stt_failed = False

        try:
            customer_text = self.voice_adapter.transcribe(valid_audio)
            logger.info("Speech-to-text completed: \"%s\"", customer_text)
        except NetworkOrAPIError as err:
            logger.error("STT network or external API error: %s", err, exc_info=True)
            stt_network_error = True
        except Exception as err:
            logger.error("Speech-to-text transcription failed: %s", err, exc_info=True)
            stt_failed = True

        speech_is_empty = (not customer_text or not str(customer_text).strip()) and not stt_network_error and not stt_failed

        # -------------------------------------------------------------------
        # Stage 3: Intent Classification (Cases 6, 7, 12)
        # -------------------------------------------------------------------
        if stt_network_error:
            intent_result = {
                "intent": "unknown",
                "party_size": None,
                "date": None,
                "time": None,
                "food_preference": {},
                "summary": "Network connection error occurred during voice transcription.",
                "error_type": "network_error",
            }
            logger.warning("Intent classification bypassed due to STT network error.")
        elif stt_failed:
            intent_result = {
                "intent": "unknown",
                "party_size": None,
                "date": None,
                "time": None,
                "food_preference": {},
                "summary": "Transcription service failed.",
                "error_type": "classification_failed",
            }
            logger.warning("Intent classification bypassed due to STT failure.")
        elif speech_is_empty:
            intent_result = {
                "intent": "unknown",
                "party_size": None,
                "date": None,
                "time": None,
                "food_preference": {},
                "summary": "No speech detected in audio.",
                "is_empty": True,
                "is_empty_or_unclear": True,
            }
            logger.info("Intent classification: No speech detected in audio.")
        else:
            try:
                intent_result = self.intent_adapter.safe_classify(customer_text)
                logger.info(
                    "Intent classification completed: intent='%s' (party_size=%s, date=%s, time=%s)",
                    intent_result.get("intent"),
                    intent_result.get("party_size"),
                    intent_result.get("date"),
                    intent_result.get("time"),
                )
            except Exception as err:
                logger.error("Intent classification encountered unexpected error: %s", err, exc_info=True)
                intent_result = {
                    "intent": "unknown",
                    "party_size": None,
                    "date": None,
                    "time": None,
                    "food_preference": {},
                    "summary": "Intent classification failed.",
                    "error_type": "classification_failed",
                }

        # -------------------------------------------------------------------
        # Stage 4: Save Intent Classification JSON
        # -------------------------------------------------------------------
        json_output = None
        # Only save intent JSON if transcription succeeded and speech was detected (avoids misleading empty/failed outputs)
        if save_intent_json and not stt_network_error and not stt_failed and not speech_is_empty:
            try:
                if output_json_path:
                    dest_json = Path(output_json_path)
                else:
                    stem = valid_audio.stem
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    unique_id = uuid.uuid4().hex[:6]
                    dest_json = config.INTENTS_DIR / f"{stem}_intent_{timestamp}_{unique_id}.json"

                dest_json.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_json, "w", encoding="utf-8") as f:
                    json.dump(intent_result, f, indent=2, ensure_ascii=False)

                if dest_json.exists() and dest_json.stat().st_size > 0:
                    json_output = dest_json
                    logger.info("Intent classification JSON saved: %s (%d bytes)", dest_json.name, dest_json.stat().st_size)
            except Exception as err:
                logger.error("Failed to save intent classification JSON file: %s", err, exc_info=True)
                json_output = None

        # -------------------------------------------------------------------
        # Stage 5: Response Generation (Cases 8, 9)
        # -------------------------------------------------------------------
        try:
            response_text = self.response_generator.generate_response(intent_result, customer_text)
            logger.info("Response generated: \"%s\"", response_text)
        except Exception as err:
            logger.error("Response generation failed unexpectedly: %s", err, exc_info=True)
            response_text = "Thank you for contacting us. How may I assist you with your dining plans today?"

        # -------------------------------------------------------------------
        # Stage 6: Text-to-Speech & Audio Verification (Cases 10, 11, 12)
        # -------------------------------------------------------------------
        audio_output = None
        tts_failed = False
        if generate_audio:
            try:
                audio_output = self.voice_adapter.synthesize_speech(
                    text=response_text,
                    output_path=output_audio_path,
                )
                # Verify generated audio file existence and non-zero size (Case 11)
                if not audio_output.exists() or audio_output.stat().st_size == 0:
                    raise TTSOutputInvalidError(f"Generated audio file is missing or 0 bytes: {audio_output.name}")

                out_kb = audio_output.stat().st_size / 1024
                logger.info("Text-to-speech completed: %s (%.2f KB)", audio_output.name, out_kb)
                logger.info("Audio response ready: %s", audio_output)
            except TTSOutputInvalidError as err:
                logger.error("TTS output verification failed: %s", err, exc_info=True)
                audio_output = None
                tts_failed = True
            except NetworkOrAPIError as err:
                logger.error("TTS network or external API error: %s", err, exc_info=True)
                audio_output = None
                tts_failed = True
            except Exception as err:
                logger.error("Text-to-speech synthesis failed: %s", err, exc_info=True)
                audio_output = None
                tts_failed = True

        status = "success"
        if stt_network_error:
            status = "network_error"

        return {
            "status": status,
            "audio_file": str(valid_audio.resolve()),
            "customer_text": customer_text,
            "extracted_text": customer_text,
            "intent_classification": intent_result,
            "json_output": str(json_output.resolve()) if json_output else None,
            "response_text": response_text,
            "audio_output": str(audio_output.resolve()) if audio_output else None,
            "tts_failed": tts_failed,
        }

    def process_text(
        self,
        customer_text: str,
        output_audio_path: Optional[Union[str, Path]] = None,
        output_json_path: Optional[Union[str, Path]] = None,
        generate_audio: bool = True,
        save_intent_json: bool = True,
    ) -> Dict[str, Any]:
        """
        Simulate from text input -> Intent Classification -> Save JSON -> Response Text -> TTS Audio.
        """
        logger.info("Text received: \"%s\"", customer_text)

        intent_result = self.intent_adapter.safe_classify(customer_text)
        logger.info("Intent classification completed: intent='%s'", intent_result.get("intent"))

        json_output = None
        if save_intent_json and customer_text and customer_text.strip():
            try:
                if output_json_path:
                    dest_json = Path(output_json_path)
                else:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    unique_id = uuid.uuid4().hex[:6]
                    dest_json = config.INTENTS_DIR / f"text_intent_{timestamp}_{unique_id}.json"

                dest_json.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_json, "w", encoding="utf-8") as f:
                    json.dump(intent_result, f, indent=2, ensure_ascii=False)

                if dest_json.exists() and dest_json.stat().st_size > 0:
                    json_output = dest_json
                    logger.info("Intent classification JSON saved: %s (%d bytes)", dest_json.name, dest_json.stat().st_size)
            except Exception as err:
                logger.error("Failed to save intent classification JSON in process_text: %s", err, exc_info=True)
                json_output = None

        try:
            response_text = self.response_generator.generate_response(intent_result, customer_text)
            logger.info("Response generated: \"%s\"", response_text)
        except Exception as err:
            logger.error("Response generation failed in process_text: %s", err, exc_info=True)
            response_text = "Thank you for contacting us. How may I assist you with your dining plans today?"

        audio_output = None
        tts_failed = False
        if generate_audio:
            try:
                audio_output = self.voice_adapter.synthesize_speech(
                    text=response_text,
                    output_path=output_audio_path,
                )
                if not audio_output.exists() or audio_output.stat().st_size == 0:
                    raise TTSOutputInvalidError(f"Generated audio file is missing or 0 bytes: {audio_output.name}")
                logger.info("Text-to-speech completed: %s", audio_output.name)
                logger.info("Audio response ready: %s", audio_output)
            except Exception as err:
                logger.error("TTS synthesis failed in process_text: %s", err, exc_info=True)
                audio_output = None
                tts_failed = True

        return {
            "status": "success",
            "audio_file": None,
            "customer_text": customer_text,
            "extracted_text": customer_text,
            "intent_classification": intent_result,
            "json_output": str(json_output.resolve()) if json_output else None,
            "response_text": response_text,
            "audio_output": str(audio_output.resolve()) if audio_output else None,
            "tts_failed": tts_failed,
        }

    def validate_audio_input(self, audio_path: Union[str, Path]) -> Path:
        """Validate input audio file existence and format."""
        try:
            return self.voice_adapter.validate_audio(audio_path)
        except (AudioFileNotFoundError, AudioFormatError, AudioEmptyError, VoiceProcessingError) as err:
            raise ValueError(str(err)) from err

    def run_pipeline(
        self,
        audio_path: Optional[Union[str, Path]] = None,
        output_audio: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Backward-compatible pipeline runner."""
        if not audio_path:
            raise ValueError("audio_path is required.")

        return self.process_audio_file(
            audio_path=audio_path,
            output_audio_path=output_audio,
            generate_audio=True,
        )


def process_customer_audio(
    audio_path: Union[str, Path],
    output_audio: Optional[Union[str, Path]] = None,
    output_json: Optional[Union[str, Path]] = None,
    mock_mode: bool = False,
) -> Dict[str, Any]:
    """
    Main integration entry function:
    Accepts customer audio file path, runs the complete pipeline,
    and returns both the intent JSON and audio response to the user.
    """
    orchestrator = VoiceIntentOrchestrator(mock_mode=mock_mode)
    return orchestrator.process_audio_file(
        audio_path=audio_path,
        output_audio_path=output_audio,
        output_json_path=output_json,
        generate_audio=True,
        save_intent_json=True,
    )


def print_env_status():
    """Print the detected environment status and sibling project resolution."""
    status = config.get_environment_status()
    print("\n" + "=" * 65)
    print("  VOICE-INTENT INTEGRATION - ENVIRONMENT STATUS")
    print("=" * 65)
    print(f"Base Directory   : {status['base_dir']}")
    print(f"Parent Directory : {status['parent_dir']}")
    print(f"Audio Input Dir  : {status['audio_dir']['path']} (Exists: {status['audio_dir']['exists']})")
    print(f"Responses Dir    : {status['responses_dir']['path']} (Exists: {status['responses_dir']['exists']})")
    print(f"Groq API Key     : {'CONFIGURED' if status['has_groq_api_key'] else 'NOT SET'}")
    print("-" * 65)
    print("Sibling Projects (Orchestrated Subsystems):")

    vp = status["voice_processing_project"]
    vp_status = "DETECTED" if vp["detected"] else "NOT FOUND"
    print(f"  * Voice Processing Subsystem      : [{vp_status}] -> {vp['path']}")

    ic = status["intent_classification_project"]
    ic_status = "DETECTED" if ic["detected"] else "NOT FOUND"
    print(f"  * Intent Classification Subsystem : [{ic_status}] -> {ic['path']}")
    print("=" * 65 + "\n")


def display_pipeline_summary(result: Dict[str, Any]) -> None:
    """
    Print an orchestration trace showing each stage of the pipeline:
      Audio received
      → Speech-to-text completed
      → Intent classification completed
      → Intent JSON saved
      → Response generated
      → Text-to-speech completed
      → Audio response ready
    """
    intent_data = result.get("intent_classification") or {}
    audio_in = result.get("audio_file")
    json_out = result.get("json_output")
    audio_out = result.get("audio_output")
    tts_failed = result.get("tts_failed", False)

    print("\n" + "=" * 65)
    print("  VOICE-INTENT ORCHESTRATION PIPELINE EXECUTION")
    print("=" * 65)

    # Stage 1: Audio received
    if audio_in:
        in_path = Path(audio_in)
        in_size_kb = (in_path.stat().st_size / 1024) if in_path.exists() else 0
        print(f"  [1/6] Audio received              : {in_path.name} ({in_size_kb:.2f} KB)")
    else:
        print(f"  [1/6] Direct text received        : \"{result.get('customer_text')}\"")

    # Stage 2: Speech-to-text completed
    cust_text = result.get('customer_text') or "(No discernible speech detected)"
    print(f"  [2/6] Speech-to-text completed    : \"{cust_text}\"")

    # Stage 3: Intent classification completed
    intent_name = intent_data.get("intent", "unknown")
    ps = intent_data.get("party_size") or "unspecified"
    dt = intent_data.get("date") or "unspecified"
    tm = intent_data.get("time") or "unspecified"
    print(f"  [3/6] Intent classification done  : Intent='{intent_name}', Party={ps}, Date={dt}, Time={tm}")

    # Stage 4: Intent JSON saved
    if json_out:
        j_path = Path(json_out)
        j_size_b = j_path.stat().st_size if j_path.exists() else 0
        print(f"  [4/6] Intent JSON saved           : {j_path.name} ({j_size_b} bytes)")
    else:
        print(f"  [4/6] Intent JSON saved           : [SKIPPED / Not Available]")

    # Stage 5: Response generated
    print(f"  [5/6] Response generated          : \"{result.get('response_text')}\"")

    # Stage 6: Text-to-speech completed
    if audio_out:
        out_path = Path(audio_out)
        out_size_kb = (out_path.stat().st_size / 1024) if out_path.exists() else 0
        print(f"  [6/6] Text-to-speech completed    : {out_path.name} ({out_size_kb:.2f} KB)")
        print("-" * 65)
        if json_out:
            print(f"  >> Intent JSON output             : {json_out}")
        print(f"  >> Audio response ready           : {audio_out}")
    elif tts_failed:
        print(f"  [6/6] Text-to-speech completed    : [NOTICE: Audio synthesis unavailable]")
        print("-" * 65)
        if json_out:
            print(f"  >> Intent JSON output             : {json_out}")
        print(f"  >> Notice                         : Audio synthesis was unavailable; text response provided above.")
    else:
        print(f"  [6/6] Text-to-speech completed    : [SKIPPED via --no-tts]")
        print("-" * 65)
        if json_out:
            print(f"  >> Intent JSON output             : {json_out}")
        print(f"  >> Response ready (Text Only)     : Customer response generated.")

    print("=" * 65)
    print("[SUCCESS] Complete voice-intent cycle executed successfully.\n")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Voice-Intent Integration: Provide ONLY an audio file to run the complete end-to-end voice assistant cycle."
    )
    # The audio file is the only required input
    parser.add_argument(
        "audio_file",
        nargs="?",
        default=None,
        help="Path to customer audio file (.wav, .mp3, .m4a, .ogg, .flac)",
    )
    parser.add_argument(
        "-a",
        "--audio",
        dest="audio_flag",
        default=None,
        help="Explicit flag to specify customer audio file path",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_audio",
        default=None,
        help="Custom destination path for the generated audio response file",
    )
    parser.add_argument(
        "-j",
        "--json-output",
        dest="output_json",
        default=None,
        help="Custom destination path for the generated intent classification JSON file",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Generate text response only (skip audio synthesis)",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip saving the intent classification JSON file to disk",
    )
    parser.add_argument(
        "-t",
        "--text",
        dest="text_input",
        default=None,
        help="Direct customer text simulation (skip audio ingestion)",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Inspect configuration and sibling project detection status",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run pipeline with offline mock simulation (no API calls)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.check_env:
        print_env_status()
        return

    orchestrator = VoiceIntentOrchestrator(mock_mode=args.mock)
    generate_tts = not args.no_tts
    save_json = not args.no_json

    # Direct text simulation mode (if explicitly requested by developer)
    if args.text_input:
        print("\n" + "=" * 65)
        print("  VOICE-INTENT INTEGRATION: TEXT SIMULATION MODE")
        print("=" * 65)
        try:
            result = orchestrator.process_text(
                customer_text=args.text_input,
                output_audio_path=args.output_audio,
                output_json_path=args.output_json,
                generate_audio=generate_tts,
                save_intent_json=save_json,
            )
            display_pipeline_summary(result)
            return result
        except Exception as err:
            safe_err = sanitize_customer_message(str(err))
            logger.error("Text simulation failed: %s", err, exc_info=True)
            print(f"\n[ERROR] {safe_err}", file=sys.stderr)
            sys.exit(1)

    # Primary mode: User provides ONLY an audio file
    audio_path = args.audio_file or args.audio_flag

    if not audio_path:
        if len(sys.argv) == 1:
            print_env_status()
            print("Usage: python main.py <path_to_customer_audio_file>")
            print("   or: python main.py audio/sample_customer_audio.wav\n")
            try:
                audio_path = input("Please enter the path to the customer audio file: ").strip()
                if not audio_path:
                    print("No audio file provided. Exiting.")
                    sys.exit(0)
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled by user.")
                sys.exit(0)
        else:
            print("[ERROR] No input audio file provided. Usage: python main.py <path_to_customer_audio_file>", file=sys.stderr)
            sys.exit(1)

    # Execute complete pipeline
    try:
        result = orchestrator.process_audio_file(
            audio_path=audio_path,
            output_audio_path=args.output_audio,
            output_json_path=args.output_json,
            generate_audio=generate_tts,
            save_intent_json=save_json,
        )

        if result.get("status") == "error":
            cust_err = result.get("customer_message", "Could not process audio file.")
            print(f"\n[ERROR] {cust_err}", file=sys.stderr)
            sys.exit(1)

        display_pipeline_summary(result)
        return result

    except AudioFileNotFoundError as err:
        logger.error("Audio file not found: %s", err, exc_info=True)
        print("\n[ERROR] The requested audio recording could not be found. Please check the file path and try again.", file=sys.stderr)
        sys.exit(1)

    except AudioFormatError as err:
        logger.error("Unsupported audio format: %s", err, exc_info=True)
        supported = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
        print(f"\n[ERROR] The provided audio format is not supported. Please provide a standard audio file ({supported}).", file=sys.stderr)
        sys.exit(1)

    except AudioEmptyError as err:
        logger.error("Empty audio file: %s", err, exc_info=True)
        print("\n[ERROR] The audio file is empty. Please provide an audio recording containing speech.", file=sys.stderr)
        sys.exit(1)

    except NetworkOrAPIError as err:
        logger.error("Network or API error: %s", err, exc_info=True)
        print("\n[ERROR] We are currently experiencing a temporary connection issue. Please try again in a few moments.", file=sys.stderr)
        sys.exit(1)

    except Exception as err:
        safe_msg = sanitize_customer_message(str(err))
        logger.error("Unhandled error: %s", err, exc_info=True)
        print(f"\n[ERROR] {safe_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
