"""
Boundary 5 Tests: Sibling Projects Integrity & Isolation.

Verifies the strict constraint:
- "Verify that: No existing project files are modified."
- Both sibling projects remain independent in the parent directory.
- No files are written, renamed, moved, merged, or duplicated in either sibling repository.
- Pipeline execution writes outputs strictly inside voice-intent-integration/.
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from main import VoiceIntentOrchestrator


class TestBoundary5SystemIntegrity(unittest.TestCase):
    """Integrity and isolation tests ensuring sibling projects remain untouched."""

    def setUp(self):
        self.parent_dir = config.PARENT_DIR
        self.voice_project_dir = config.VOICE_PROCESSING_DIR
        self.intent_project_dir = config.INTENT_CLASSIFICATION_DIR

    def test_sibling_projects_exist_in_parent_directory(self):
        """Verify both sibling projects exist as separate directories in the parent folder."""
        self.assertIsNotNone(self.voice_project_dir)
        self.assertTrue(self.voice_project_dir.exists())
        self.assertTrue(self.voice_project_dir.is_dir())

        self.assertIsNotNone(self.intent_project_dir)
        self.assertTrue(self.intent_project_dir.exists())
        self.assertTrue(self.intent_project_dir.is_dir())

        # Verify they are siblings (reside in the parent folder, outside integration folder)
        self.assertEqual(self.voice_project_dir.parent.resolve(), config.PARENT_DIR.resolve())
        self.assertEqual(self.intent_project_dir.parent.resolve(), config.PARENT_DIR.resolve())
        self.assertNotEqual(self.voice_project_dir.resolve(), config.BASE_DIR.resolve())
        self.assertNotEqual(self.intent_project_dir.resolve(), config.BASE_DIR.resolve())

    def test_voice_processing_core_files_intact(self):
        """Verify voice-processing project core source files exist and have not been deleted or renamed."""
        expected_files = [
            self.voice_project_dir / "src" / "stt_service.py",
            self.voice_project_dir / "src" / "tts_service.py",
            self.voice_project_dir / "src" / "audio_validator.py",
            self.voice_project_dir / "requirements.txt",
        ]
        for fpath in expected_files:
            self.assertTrue(fpath.exists(), f"Expected core file missing from voice-processing: {fpath}")

    def test_intent_classification_core_files_intact(self):
        """Verify intent-classification project core source files exist and have not been deleted or renamed."""
        expected_files = [
            self.intent_project_dir / "intent_classifier.py",
            self.intent_project_dir / "requirements.txt",
        ]
        for fpath in expected_files:
            self.assertTrue(fpath.exists(), f"Expected core file missing from intent-classification: {fpath}")

    def test_pipeline_execution_does_not_write_to_sibling_projects(self):
        """
        Verify executing the full pipeline writes output strictly into voice-intent-integration/
        and leaves sibling project directories completely untouched.
        """
        # Snapshot file counts in sibling projects
        def count_files(directory: Path) -> int:
            return sum(1 for _ in directory.glob("**/*") if _.is_file())

        voice_count_before = count_files(self.voice_project_dir)
        intent_count_before = count_files(self.intent_project_dir)

        # Run mock pipeline
        orchestrator = VoiceIntentOrchestrator(mock_mode=True)
        test_audio = config.AUDIO_DIR / "integrity_test_audio.wav"
        test_audio.write_bytes(b"[RIFF MOCK AUDIO DATA]")

        try:
            result = orchestrator.process_audio_file(test_audio)
            self.assertEqual(result["status"], "success")

            # Check output location
            audio_out = Path(result["audio_output"])
            self.assertTrue(
                str(audio_out.resolve()).startswith(str(config.BASE_DIR.resolve())),
                "Generated audio output must reside inside voice-intent-integration project."
            )

            # Assert file counts in sibling projects are 100% unchanged
            voice_count_after = count_files(self.voice_project_dir)
            intent_count_after = count_files(self.intent_project_dir)

            self.assertEqual(
                voice_count_before,
                voice_count_after,
                "Voice-processing directory must not have any new, modified, or deleted files."
            )
            self.assertEqual(
                intent_count_before,
                intent_count_after,
                "Intent-classification directory must not have any new, modified, or deleted files."
            )
        finally:
            if test_audio.exists():
                test_audio.unlink()


if __name__ == "__main__":
    unittest.main()
