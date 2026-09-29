"""
Test Suite for the Voice-Intent Integration Interface.

Tests the interface capabilities:
  1. Accepts/records customer audio.
  2. Sends audio through the complete integration pipeline.
  3. Generates response audio.
  4. Makes response audio available for playback.
  5. User does not have to enter text, intent, entities, or response text.
  6. Intermediate transcription and detected intent are exposed for debugging.
  7. Robust error handling for missing, invalid, or empty audio uploads.
  8. Preserves existing sibling projects intact.
"""

import sys
import unittest
import py_compile
from io import BytesIO
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from web_app import app, orchestrator


class TestVoiceIntentInterface(unittest.TestCase):
    """Integration and boundary tests for the web interface."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.test_cases_dir = config.AUDIO_DIR / "test_cases"
        cls.sample_booking = cls.test_cases_dir / "02_new_booking.mp3"
        cls.sample_greeting = cls.test_cases_dir / "01_greeting.mp3"

    def test_01_streamlit_app_compiles(self):
        """Verify that app.py (Streamlit interface) compiles with clean syntax."""
        streamlit_app = BASE_DIR / "app.py"
        self.assertTrue(streamlit_app.exists(), "app.py must exist in voice-intent-integration")
        compiled = py_compile.compile(str(streamlit_app), doraise=True)
        self.assertIsNotNone(compiled)

    def test_02_web_interface_renders_audio_only_experience(self):
        """Verify main web interface renders with audio input, JSON display, and separate download buttons."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Primary input elements
        self.assertIn("Customer Audio Input", html)
        self.assertIn("Record Voice", html)
        self.assertIn("Upload Audio File", html)
        self.assertIn("Customer Scenarios", html)

        # Primary results elements
        self.assertIn("Spoken Audio Response", html)
        self.assertIn("Download Audio", html)
        self.assertIn("download-audio-btn", html)
        self.assertIn("Transcribed Customer Speech", html)
        self.assertIn("result-transcript", html)
        self.assertIn("Intent Classification Result (JSON)", html)
        self.assertIn("Download JSON", html)
        self.assertIn("download-json-btn", html)
        self.assertIn("result-json-code", html)

        # Confirm user is not prompted for manual text or intent inputs
        self.assertNotIn("Enter customer text", html)
        self.assertNotIn("Select intent", html)
        self.assertNotIn("Enter party size", html)

        # Confirm diagnostic drawer is present
        self.assertIn("Intermediate Diagnostics & Slot Tags", html)

    def test_03_samples_endpoint_lists_all_test_cases(self):
        """Verify GET /api/samples returns all available customer audio scenarios."""
        resp = self.client.get("/api/samples")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("samples", data)
        sample_names = [s["filename"] for s in data["samples"]]
        self.assertIn("01_greeting.mp3", sample_names)
        self.assertIn("02_new_booking.mp3", sample_names)
        self.assertIn("05_inquiry.mp3", sample_names)

    def test_04_process_sample_scenario_end_to_end(self):
        """
        Verify POST /api/process_sample runs the full pipeline on a selected customer audio file:
        Audio Input -> Pipeline -> Response Audio Playback + Download, and Intent JSON Display + Download.
        """
        resp = self.client.post(
            "/api/process_sample",
            json={"sample_filename": "02_new_booking.mp3"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # 1. Pipeline success
        self.assertEqual(data.get("status"), "success")

        # 2. Response audio ready for playback & download
        self.assertIsNotNone(data.get("audio_output_url"))
        self.assertTrue(data.get("audio_output_url").startswith("/api/audio/"))
        self.assertIsNotNone(data.get("audio_output_filename"))
        self.assertIsNotNone(data.get("audio_download_url"))
        self.assertIn("download=true", data.get("audio_download_url"))

        # 3. JSON output ready for display & download
        self.assertIsNotNone(data.get("json_output_url"))
        self.assertTrue(data.get("json_output_url").startswith("/api/intent/"))
        self.assertIsNotNone(data.get("json_output_filename"))
        self.assertIsNotNone(data.get("json_download_url"))
        self.assertIn("download=true", data.get("json_download_url"))

        # 4. Intent classification fields preserved and available
        intent_info = data.get("intent_classification", {})
        self.assertEqual(intent_info.get("intent"), "booking")
        self.assertTrue(bool(data.get("customer_text")))
        self.assertTrue(bool(data.get("response_text")))

        # 5. Verify audio playback endpoint serves actual audio
        audio_url = data.get("audio_output_url")
        audio_resp = self.client.get(audio_url)
        self.assertEqual(audio_resp.status_code, 200)
        self.assertEqual(audio_resp.content_type, "audio/mpeg")
        self.assertGreater(len(audio_resp.data), 1000)

        # 6. Verify audio download endpoint serves file as attachment
        audio_download_url = data.get("audio_download_url")
        audio_dl_resp = self.client.get(audio_download_url)
        self.assertEqual(audio_dl_resp.status_code, 200)
        self.assertIn("attachment", audio_dl_resp.headers.get("Content-Disposition", ""))

        # 7. Verify JSON endpoint serves valid JSON matching intent_classification
        json_url = data.get("json_output_url")
        json_resp = self.client.get(json_url)
        self.assertEqual(json_resp.status_code, 200)
        self.assertEqual(json_resp.content_type, "application/json")
        served_json = json_resp.get_json()
        self.assertEqual(served_json.get("intent"), "booking")
        self.assertEqual(served_json, intent_info)

        # 8. Verify JSON download endpoint sets Content-Disposition attachment with intent_result.json
        json_dl_url = data.get("json_download_url")
        json_dl_resp = self.client.get(json_dl_url)
        self.assertEqual(json_dl_resp.status_code, 200)
        self.assertIn("attachment", json_dl_resp.headers.get("Content-Disposition", ""))
        self.assertIn("intent_result.json", json_dl_resp.headers.get("Content-Disposition", ""))

    def test_05_process_uploaded_audio_file(self):
        """
        Verify POST /api/process_audio accepts multipart audio file upload (microphone or file drop),
        processes it through the complete integration pipeline, and produces valid response audio and intent JSON.
        """
        if not self.sample_greeting.exists():
            self.skipTest("Sample greeting audio not found.")

        with open(self.sample_greeting, "rb") as f:
            audio_bytes = f.read()

        data = {
            "audio": (BytesIO(audio_bytes), "my_voice_recording.mp3")
        }

        resp = self.client.post(
            "/api/process_audio",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 200)
        res_data = resp.get_json()

        # Audio response generated & available
        self.assertEqual(res_data.get("status"), "success")
        self.assertIsNotNone(res_data.get("audio_output_url"))
        self.assertIsNotNone(res_data.get("audio_download_url"))
        self.assertIsNotNone(res_data.get("json_output_url"))
        self.assertIsNotNone(res_data.get("json_download_url"))
        self.assertFalse(res_data.get("tts_failed"))

        # Intermediate debug data populated
        self.assertIn("evening", res_data.get("customer_text", "").lower())
        self.assertEqual(res_data.get("intent_classification", {}).get("intent"), "inquiry")
        self.assertIn("assist", res_data.get("response_text", "").lower())

        # Verify JSON download endpoint works for the uploaded audio run
        json_dl_resp = self.client.get(res_data.get("json_download_url"))
        self.assertEqual(json_dl_resp.status_code, 200)
        self.assertIn("attachment", json_dl_resp.headers.get("Content-Disposition", ""))
        downloaded_json = json_dl_resp.get_json()
        self.assertEqual(downloaded_json.get("intent"), "inquiry")

    def test_06_error_handling_no_audio_file_provided(self):
        """Verify POST /api/process_audio with missing file returns 400 with polite customer message."""
        resp = self.client.post("/api/process_audio", data={})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("customer_facing_message", data)

    def test_07_error_handling_invalid_sample_name(self):
        """Verify POST /api/process_sample with nonexistent filename returns 404."""
        resp = self.client.post(
            "/api/process_sample",
            json={"sample_filename": "non_existent_audio_file.mp3"},
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")

    def test_08_audio_serving_endpoint(self):
        """Verify /api/audio endpoint serves sample audio with appropriate MIME type."""
        resp = self.client.get("/api/audio/01_greeting.mp3?sample=true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "audio/mpeg")
        self.assertGreater(len(resp.data), 5000)

    def test_09_audio_serving_endpoint_not_found(self):
        """Verify /api/audio endpoint returns 404 for missing file."""
        resp = self.client.get("/api/audio/fake_audio_never_exists.mp3")
        self.assertEqual(resp.status_code, 404)

    def test_10_intent_serving_endpoint_not_found(self):
        """Verify /api/intent endpoint returns 404 for missing file."""
        resp = self.client.get("/api/intent/fake_intent_never_exists.json")
        self.assertEqual(resp.status_code, 404)

    def test_11_path_traversal_protection(self):
        """Verify directory traversal attempts on /api/audio and /api/intent are blocked with 403."""
        # Traversal on audio endpoint
        audio_traversal = self.client.get("/api/audio/../config.py")
        self.assertIn(audio_traversal.status_code, [403, 404])

        # Traversal on intent endpoint
        intent_traversal = self.client.get("/api/intent/../config.py")
        self.assertIn(intent_traversal.status_code, [403, 404])

    def test_12_sibling_projects_untouched(self):
        """Verify that neither sibling project was modified by the interface implementation."""
        sibling_voice = config.VOICE_PROCESSING_DIR
        sibling_intent = config.INTENT_CLASSIFICATION_DIR
        self.assertTrue(sibling_voice.exists())
        self.assertTrue(sibling_intent.exists())

        # Assert no interface files were created inside sibling project folders
        self.assertFalse((sibling_voice / "app.py").exists())
        self.assertFalse((sibling_intent / "app.py").exists())
        self.assertFalse((sibling_voice / "web_app.py").exists())
        self.assertFalse((sibling_intent / "web_app.py").exists())


if __name__ == "__main__":
    unittest.main()
