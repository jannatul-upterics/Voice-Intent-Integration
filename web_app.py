"""
Flask Web Interface for the Voice-Intent Integration Orchestrator.

Provides an audio-first interface:
  1. Accepts or records customer audio via microphone, drag-and-drop file upload, or pre-recorded customer scenarios.
  2. Passes audio through the complete integration pipeline (STT -> Intent Classifier -> Response Generator -> TTS).
  3. Returns synthesized response audio and provides instant browser playback.
  4. Optionally exposes intermediate transcription and detected intent for debugging in a collapsible drawer.

The user is NEVER required to manually enter text, intent, entities, or response text.
"""

import os
import sys
import logging
import uuid
from pathlib import Path
from typing import Dict, Any

from flask import Flask, render_template, request, jsonify, send_file, url_for

# Ensure voice-intent-integration root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from main import VoiceIntentOrchestrator

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger("VoiceIntentWebApp")

# Initialize Flask application
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max audio upload

# Uploads directory
UPLOADS_DIR = config.AUDIO_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
TEST_CASES_DIR = config.AUDIO_DIR / "test_cases"

# Initialize Orchestrator instance
orchestrator = VoiceIntentOrchestrator()


@app.route("/")
def index():
    """Renders the main audio interface."""
    return render_template("index.html")


@app.route("/api/samples", methods=["GET"])
def get_samples():
    """Returns available sample audio scenarios."""
    samples = []
    if TEST_CASES_DIR.exists():
        for file in sorted(TEST_CASES_DIR.glob("*.mp3")):
            samples.append({
                "filename": file.name,
                "size_kb": round(file.stat().st_size / 1024, 2),
                "url": url_for("serve_audio", filename=file.name, sample="true")
            })
    return jsonify({"samples": samples})


@app.route("/api/process_audio", methods=["POST"])
def process_audio():
    """
    Accepts customer audio file upload or live recording.
    Runs complete integration pipeline and returns audio response.
    """
    if "audio" not in request.files:
        return jsonify({
            "status": "error",
            "error": "No audio file provided in request.",
            "customer_facing_message": "Please record or upload an audio file."
        }), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({
            "status": "error",
            "error": "Empty filename received.",
            "customer_facing_message": "Please select a valid audio file."
        }), 400

    # Preserve or generate valid audio extension
    original_ext = Path(audio_file.filename).suffix.lower()
    if original_ext not in config.SUPPORTED_AUDIO_EXTENSIONS:
        # Default to .wav for browser MediaRecorder blobs
        original_ext = ".wav"

    save_filename = f"cust_upload_{uuid.uuid4().hex[:8]}{original_ext}"
    save_path = UPLOADS_DIR / save_filename
    audio_file.save(save_path)

    logger.info("Saved customer audio upload to %s (%d bytes)", save_path, save_path.stat().st_size)

    # Process through complete integration pipeline
    result = orchestrator.process_audio_file(
        audio_path=save_path,
        output_audio_path=config.RESPONSES_DIR / f"resp_{uuid.uuid4().hex[:8]}.mp3",
        generate_audio=True
    )

    return _build_response_payload(result)


@app.route("/api/process_sample", methods=["POST"])
def process_sample():
    """
    Processes one of the 10 customer test case scenarios.
    """
    data = request.get_json(silent=True) or {}
    sample_filename = data.get("sample_filename")
    if not sample_filename:
        return jsonify({
            "status": "error",
            "error": "No sample_filename specified.",
            "customer_facing_message": "Please select a sample scenario."
        }), 400

    sample_path = TEST_CASES_DIR / sample_filename
    if not sample_path.exists():
        # Check in root AUDIO_DIR
        sample_path = config.AUDIO_DIR / sample_filename

    if not sample_path.exists():
        return jsonify({
            "status": "error",
            "error": f"Sample file not found: {sample_filename}",
            "customer_facing_message": "The selected sample could not be found."
        }), 404

    logger.info("Processing customer sample scenario: %s", sample_path)

    result = orchestrator.process_audio_file(
        audio_path=sample_path,
        output_audio_path=config.RESPONSES_DIR / f"resp_{sample_filename}",
        generate_audio=True
    )

    return _build_response_payload(result)


@app.route("/api/audio/<path:filename>", methods=["GET"])
def serve_audio(filename: str):
    """
    Serves generated response audio files or input samples.
    """
    is_sample = request.args.get("sample", "false").lower() == "true"
    if is_sample:
        target_path = TEST_CASES_DIR / filename
        if not target_path.exists():
            target_path = config.AUDIO_DIR / filename
    else:
        target_path = config.RESPONSES_DIR / filename
        if not target_path.exists():
            target_path = UPLOADS_DIR / filename

    if not target_path.exists():
        return jsonify({"error": "Audio file not found"}), 404

    mimetype = "audio/mpeg" if target_path.suffix.lower() == ".mp3" else "audio/wav"
    return send_file(str(target_path), mimetype=mimetype)


@app.route("/api/intent/<path:filename>", methods=["GET"])
def serve_intent_json(filename: str):
    """
    Serves generated intent classification JSON files.
    """
    target_path = config.INTENTS_DIR / filename
    if not target_path.exists():
        return jsonify({"error": "Intent JSON file not found"}), 404
    return send_file(str(target_path), mimetype="application/json")


def _build_response_payload(result: Dict[str, Any]):
    """Constructs the JSON payload with audio playback URL, JSON output URL, and diagnostics."""
    audio_output = result.get("audio_output")
    audio_output_url = None
    audio_output_filename = None

    if audio_output:
        p = Path(audio_output)
        if p.exists() and p.stat().st_size > 0:
            audio_output_filename = p.name
            audio_output_url = f"/api/audio/{p.name}"

    json_output = result.get("json_output")
    json_output_url = None
    json_output_filename = None

    if json_output:
        jp = Path(json_output)
        if jp.exists() and jp.stat().st_size > 0:
            json_output_filename = jp.name
            json_output_url = f"/api/intent/{jp.name}"

    status_code = 200 if result.get("status") in ("success", "partial_failure") else 400

    return jsonify({
        "status": result.get("status", "unknown"),
        "customer_text": result.get("customer_text") or "",
        "intent_classification": result.get("intent_classification") or {},
        "json_output": json_output,
        "json_output_filename": json_output_filename,
        "json_output_url": json_output_url,
        "response_text": result.get("response_text") or "",
        "audio_output_filename": audio_output_filename,
        "audio_output_url": audio_output_url,
        "tts_failed": result.get("tts_failed", False),
        "customer_facing_message": result.get("customer_facing_message")
    }), status_code


def run_web_app(host="127.0.0.1", port=5000, debug=False):
    """Start the Flask web interface server."""
    logger.info("Starting Voice-Intent Web Interface on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_web_app()
