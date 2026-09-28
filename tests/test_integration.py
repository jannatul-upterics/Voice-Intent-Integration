"""
Basic Integration and Configuration Tests
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path so config and main can be imported directly
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from main import VoiceIntentOrchestrator


class TestVoiceIntentIntegration(unittest.TestCase):

    def test_paths_and_directories_exist(self):
        """Verify project directories exist."""
        self.assertTrue(config.BASE_DIR.exists(), "Base directory must exist")
        self.assertTrue(config.AUDIO_DIR.exists(), "Audio directory must exist")
        self.assertTrue(config.RESPONSES_DIR.exists(), "Responses directory must exist")

    def test_environment_status_structure(self):
        """Verify environment status report contains required keys."""
        status = config.get_environment_status()
        self.assertIn("base_dir", status)
        self.assertIn("audio_dir", status)
        self.assertIn("responses_dir", status)
        self.assertIn("voice_processing_project", status)
        self.assertIn("intent_classification_project", status)

    def test_sibling_project_detection(self):
        """Verify sibling projects are discovered in the parent directory."""
        status = config.get_environment_status()
        # Sibling projects exist in parent folder
        self.assertTrue(
            status["voice_processing_project"]["detected"],
            "Voice processing project should be detected in parent directory"
        )
        self.assertTrue(
            status["intent_classification_project"]["detected"],
            "Intent classification project should be detected in parent directory"
        )

    def test_audio_format_validation(self):
        """Verify audio validation properly validates file extension."""
        orchestrator = VoiceIntentOrchestrator(mock_mode=True)
        dummy_bad_file = config.BASE_DIR / "dummy_unsupported.xyz"
        dummy_bad_file.write_text("test")
        try:
            with self.assertRaises(ValueError):
                orchestrator.validate_audio_input(dummy_bad_file)
        finally:
            if dummy_bad_file.exists():
                dummy_bad_file.unlink()

    def test_orchestrator_mock_pipeline(self):
        """Verify mock pipeline executes through all architecture stages end-to-end."""
        orchestrator = VoiceIntentOrchestrator(mock_mode=True)
        test_audio = config.AUDIO_DIR / "unit_test_sample.wav"
        test_audio.write_bytes(b"[MOCK WAV DATA]")

        try:
            result = orchestrator.run_pipeline(audio_path=test_audio)
            self.assertEqual(result["status"], "success")
            self.assertIsNotNone(result["extracted_text"])
            self.assertIn("intent", result["intent_classification"])
            self.assertIsNotNone(result["response_text"])
            self.assertTrue(Path(result["audio_output"]).exists())
        finally:
            if test_audio.exists():
                test_audio.unlink()


if __name__ == "__main__":
    unittest.main()
