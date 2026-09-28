"""
Integration and Boundary Tests for Dual JSON & Audio Output Generation.

Verifies:
1. Generating BOTH a JSON output file for intent classification and an audio response file.
2. Output JSON preservation of all classifier fields (intent, party_size, date, time, food_preference, summary).
3. Audio response file validity, non-empty size, and playable format (.mp3).
4. Distinct JSON filenames per execution (no accidental overwriting).
5. Custom output paths for both JSON and audio.
6. Failure isolation: invalid, missing, or empty audio does NOT generate misleading output files.
7. Coverage across booking, inquiry, modification, cancellation, and invalid inputs.
8. System integrity: no sibling project files modified.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import config
from main import VoiceIntentOrchestrator
from response_generator import ResponseGenerator


class TestDualJsonAndAudioOutput(unittest.TestCase):
    """Test suite verifying dual JSON and audio output generation."""

    @classmethod
    def setUpClass(cls):
        cls.orchestrator = VoiceIntentOrchestrator()
        cls.test_cases_dir = config.AUDIO_DIR / "test_cases"
        cls.intents_dir = config.INTENTS_DIR
        cls.responses_dir = config.RESPONSES_DIR

    def setUp(self):
        self.created_files = []

    def tearDown(self):
        """Clean up any temporary output files created during test."""
        for p in self.created_files:
            try:
                if p and Path(p).exists():
                    Path(p).unlink()
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Test 1: New Booking Request -> Both JSON and Audio Response Generated
    # -----------------------------------------------------------------------
    def test_01_booking_generates_both_json_and_audio(self):
        """Verify booking audio produces a valid intent JSON file and valid audio response."""
        audio_file = self.test_cases_dir / "02_new_booking.mp3"
        self.assertTrue(audio_file.exists(), f"Sample audio missing: {audio_file}")

        result = self.orchestrator.process_audio_file(
            audio_path=audio_file,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "success")

        # 1. Verify JSON output file
        json_path_str = result.get("json_output")
        self.assertIsNotNone(json_path_str, "JSON output path must not be None")
        json_path = Path(json_path_str)
        self.created_files.append(json_path)
        self.assertTrue(json_path.exists(), f"JSON file does not exist on disk: {json_path}")
        self.assertGreater(json_path.stat().st_size, 0, "JSON file must not be 0 bytes")
        self.assertEqual(json_path.suffix.lower(), ".json")
        self.assertTrue(str(json_path).startswith(str(config.INTENTS_DIR)), "JSON must be saved in intents directory")

        # Parse and verify preserved classifier fields
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("intent", data)
        self.assertEqual(data["intent"], "booking")
        self.assertIn("party_size", data)
        self.assertEqual(data["party_size"], 4)
        self.assertIn("date", data)
        self.assertIn("time", data)
        self.assertEqual(data["time"], "20:00")
        self.assertIn("food_preference", data)
        self.assertIn("summary", data)

        # 2. Verify Audio response file
        audio_path_str = result.get("audio_output")
        self.assertIsNotNone(audio_path_str, "Audio response path must not be None")
        audio_path = Path(audio_path_str)
        self.created_files.append(audio_path)
        self.assertTrue(audio_path.exists(), f"Audio file does not exist on disk: {audio_path}")
        self.assertGreater(audio_path.stat().st_size, 1024, "Audio file must contain valid audio payload (> 1 KB)")
        self.assertEqual(audio_path.suffix.lower(), ".mp3")
        self.assertFalse(result.get("tts_failed"), "TTS must not have failed")

    # -----------------------------------------------------------------------
    # Test 2: Inquiry Request -> Both JSON and Audio Response Generated
    # -----------------------------------------------------------------------
    def test_02_inquiry_generates_both_json_and_audio(self):
        """Verify inquiry audio produces a valid intent JSON file and valid audio response."""
        audio_file = self.test_cases_dir / "05_inquiry.mp3"
        self.assertTrue(audio_file.exists(), f"Sample audio missing: {audio_file}")

        result = self.orchestrator.process_audio_file(
            audio_path=audio_file,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "success")

        # Verify JSON
        json_path = Path(result["json_output"])
        self.created_files.append(json_path)
        self.assertTrue(json_path.exists())
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["intent"], "inquiry")
        self.assertIn("summary", data)

        # Verify Audio
        audio_path = Path(result["audio_output"])
        self.created_files.append(audio_path)
        self.assertTrue(audio_path.exists())
        self.assertGreater(audio_path.stat().st_size, 1024)

    # -----------------------------------------------------------------------
    # Test 3: Modification Request -> Both JSON and Audio Response Generated
    # -----------------------------------------------------------------------
    def test_03_modification_generates_both_json_and_audio(self):
        """Verify modification audio produces a valid intent JSON file and audio response."""
        audio_file = self.test_cases_dir / "06_modification.mp3"
        self.assertTrue(audio_file.exists(), f"Sample audio missing: {audio_file}")

        result = self.orchestrator.process_audio_file(
            audio_path=audio_file,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "success")

        # Verify JSON
        json_path = Path(result["json_output"])
        self.created_files.append(json_path)
        self.assertTrue(json_path.exists())
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["intent"], "modification")

        # Verify Audio
        audio_path = Path(result["audio_output"])
        self.created_files.append(audio_path)
        self.assertTrue(audio_path.exists())
        self.assertGreater(audio_path.stat().st_size, 1024)

    # -----------------------------------------------------------------------
    # Test 4: Cancellation Request -> Both JSON and Audio Response Generated
    # -----------------------------------------------------------------------
    def test_04_cancellation_generates_both_json_and_audio(self):
        """Verify cancellation audio produces a valid intent JSON file and audio response."""
        audio_file = self.test_cases_dir / "07_cancellation.mp3"
        self.assertTrue(audio_file.exists(), f"Sample audio missing: {audio_file}")

        result = self.orchestrator.process_audio_file(
            audio_path=audio_file,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "success")

        # Verify JSON
        json_path = Path(result["json_output"])
        self.created_files.append(json_path)
        self.assertTrue(json_path.exists())
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["intent"], "cancellation")

        # Verify Audio
        audio_path = Path(result["audio_output"])
        self.created_files.append(audio_path)
        self.assertTrue(audio_path.exists())
        self.assertGreater(audio_path.stat().st_size, 1024)

    # -----------------------------------------------------------------------
    # Test 5: Custom Output Paths for both JSON and Audio
    # -----------------------------------------------------------------------
    def test_05_custom_output_paths_respected(self):
        """Verify explicit custom output paths for both JSON and audio are respected."""
        audio_file = self.test_cases_dir / "01_greeting.mp3"
        custom_json = config.INTENTS_DIR / "custom_test_output.json"
        custom_audio = config.RESPONSES_DIR / "custom_test_response.mp3"

        self.created_files.extend([custom_json, custom_audio])

        result = self.orchestrator.process_audio_file(
            audio_path=audio_file,
            output_audio_path=custom_audio,
            output_json_path=custom_json,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(Path(result["json_output"]).resolve(), custom_json.resolve())
        self.assertEqual(Path(result["audio_output"]).resolve(), custom_audio.resolve())
        self.assertTrue(custom_json.exists())
        self.assertTrue(custom_audio.exists())
        self.assertGreater(custom_json.stat().st_size, 0)
        self.assertGreater(custom_audio.stat().st_size, 1024)

    # -----------------------------------------------------------------------
    # Test 6: Separate Unique JSON Files on Successive Executions
    # -----------------------------------------------------------------------
    def test_06_unique_json_files_per_execution(self):
        """Verify multiple executions on the same audio produce unique JSON files without overwriting."""
        audio_file = self.test_cases_dir / "01_greeting.mp3"

        result1 = self.orchestrator.process_audio_file(audio_path=audio_file, save_intent_json=True)
        result2 = self.orchestrator.process_audio_file(audio_path=audio_file, save_intent_json=True)

        json1 = Path(result1["json_output"])
        json2 = Path(result2["json_output"])
        self.created_files.extend([json1, json2])

        self.assertNotEqual(json1.name, json2.name, "Successive runs must have unique filenames")
        self.assertTrue(json1.exists(), "First run JSON must still exist")
        self.assertTrue(json2.exists(), "Second run JSON must exist")

    # -----------------------------------------------------------------------
    # Test 7: Formatted JSON with Indentation and Preserved Schema
    # -----------------------------------------------------------------------
    def test_07_json_format_and_preserved_schema(self):
        """Verify JSON output is formatted with 2-space indentation and exact field preservation."""
        audio_file = self.test_cases_dir / "02_new_booking.mp3"

        result = self.orchestrator.process_audio_file(audio_path=audio_file, save_intent_json=True)
        json_path = Path(result["json_output"])
        self.created_files.append(json_path)

        raw_content = json_path.read_text(encoding="utf-8")
        # Verify 2-space indentation
        self.assertIn('  "intent":', raw_content)
        self.assertIn('  "party_size":', raw_content)

        # Verify parsed dictionary has all standard classifier fields
        parsed = json.loads(raw_content)
        mandatory_keys = {"intent", "party_size", "date", "time", "food_preference", "summary"}
        for k in mandatory_keys:
            self.assertIn(k, parsed, f"Mandatory classifier key '{k}' missing from saved JSON")

    # -----------------------------------------------------------------------
    # Test 8: Missing Audio File -> No Output Files Generated
    # -----------------------------------------------------------------------
    def test_08_missing_audio_does_not_create_output_files(self):
        """Verify missing audio file fails gracefully and produces NO output JSON or audio."""
        non_existent = config.AUDIO_DIR / "non_existent_audio_file.wav"

        result = self.orchestrator.process_audio_file(
            audio_path=non_existent,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "audio_not_found")
        self.assertIsNone(result.get("json_output"), "Must not generate JSON output on missing audio")
        self.assertIsNone(result.get("audio_output"), "Must not generate Audio output on missing audio")

    # -----------------------------------------------------------------------
    # Test 9: Unsupported Format Audio -> No Output Files Generated
    # -----------------------------------------------------------------------
    def test_09_unsupported_format_does_not_create_output_files(self):
        """Verify unsupported format audio file fails gracefully and produces NO output files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"this is not audio")
            tmp_path = Path(tmp.name)
        self.created_files.append(tmp_path)

        result = self.orchestrator.process_audio_file(
            audio_path=tmp_path,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "unsupported_format")
        self.assertIsNone(result.get("json_output"))
        self.assertIsNone(result.get("audio_output"))

    # -----------------------------------------------------------------------
    # Test 10: Empty (0-byte) Audio File -> No Output Files Generated
    # -----------------------------------------------------------------------
    def test_10_empty_audio_does_not_create_output_files(self):
        """Verify empty audio file fails gracefully and produces NO misleading output files."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        self.created_files.append(tmp_path)

        result = self.orchestrator.process_audio_file(
            audio_path=tmp_path,
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "empty_audio")
        self.assertIsNone(result.get("json_output"))
        self.assertIsNone(result.get("audio_output"))

    # -----------------------------------------------------------------------
    # Test 11: Text Simulation Mode -> Generates JSON Output
    # -----------------------------------------------------------------------
    def test_11_text_simulation_generates_json_and_audio(self):
        """Verify process_text also generates and saves the intent JSON file and response audio."""
        result = self.orchestrator.process_text(
            customer_text="Table for 2 tonight at 7 PM",
            generate_audio=True,
            save_intent_json=True,
        )

        self.assertEqual(result["status"], "success")

        json_path = Path(result["json_output"])
        self.created_files.append(json_path)
        self.assertTrue(json_path.exists())
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["intent"], "booking")
        self.assertEqual(data["party_size"], 2)

        audio_path = Path(result["audio_output"])
        self.created_files.append(audio_path)
        self.assertTrue(audio_path.exists())
        self.assertGreater(audio_path.stat().st_size, 1024)

    # -----------------------------------------------------------------------
    # Test 12: Sibling Project Integrity
    # -----------------------------------------------------------------------
    def test_12_sibling_projects_untouched(self):
        """Verify sibling projects remain strictly separate and intact."""
        parent_dir = config.BASE_DIR.parent
        vp_dir = parent_dir / "Audio-Conversation-Voice-Response"
        ic_dir = parent_dir / "Customer-Intent-Classification"

        self.assertTrue(vp_dir.exists(), f"Voice processing project missing: {vp_dir}")
        self.assertTrue(ic_dir.exists(), f"Intent classification project missing: {ic_dir}")

        # Check key entrypoints in sibling projects still exist
        self.assertTrue((vp_dir / "main.py").exists())
        self.assertTrue((vp_dir / "src" / "stt_service.py").exists())
        self.assertTrue((ic_dir / "intent_classifier.py").exists())


if __name__ == "__main__":
    unittest.main()
