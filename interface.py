"""
Unified Interface Launcher for Voice-Intent Integration.

Allows starting either the Streamlit web app, the Flask web interface,
or running interactive audio processing directly from the command line.

Usage:
  python interface.py --streamlit          # Launch Streamlit interactive UI
  python interface.py --web                # Launch Flask Web UI (http://127.0.0.1:5000)
  python interface.py --audio <path>       # Process a specific audio file directly
"""

import sys
import argparse
import subprocess
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from main import VoiceIntentOrchestrator


def run_streamlit(port=8501):
    """Launch Streamlit web application."""
    app_path = BASE_DIR / "app.py"
    print(f"\n=======================================================")
    print(f"  Launching Streamlit Voice Assistant Interface")
    print(f"  App file: {app_path}")
    print(f"  URL: http://localhost:{port}")
    print(f"=======================================================\n")
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", str(port)]
    subprocess.run(cmd)


def run_flask(host="127.0.0.1", port=5000):
    """Launch Flask web application."""
    print(f"\n=======================================================")
    print(f"  Launching Flask Voice Assistant Web Application")
    print(f"  URL: http://{host}:{port}")
    print(f"=======================================================\n")
    from web_app import run_web_app
    run_web_app(host=host, port=port)


def run_cli_audio(audio_path: str):
    """Process an audio file via the complete integration pipeline and output results."""
    orchestrator = VoiceIntentOrchestrator()
    path = Path(audio_path)
    if not path.is_absolute():
        path = BASE_DIR / audio_path

    print(f"\nProcessing customer audio: {path.name} ({path.stat().st_size / 1024:.2f} KB)...")
    result = orchestrator.process_audio_file(path, generate_audio=True)

    print("\n" + "=" * 65)
    print("  VOICE-INTENT PIPELINE EXECUTION RESULT")
    print("=" * 65)
    print(f"  Audio Input          : {result.get('audio_file')}")
    print(f"  Transcribed Text     : \"{result.get('customer_text')}\"")
    print(f"  Detected Intent      : {result.get('intent_classification', {}).get('intent') if result.get('intent_classification') else None}")
    print(f"  Intent JSON File     : {result.get('json_output')}")
    print(f"  Customer Response    : \"{result.get('response_text')}\"")
    print(f"  Generated Audio      : {result.get('audio_output')}")
    print(f"  Pipeline Status      : {result.get('status').upper()}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Launch interface for Voice-Intent Integration"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--streamlit", action="store_true", help="Launch Streamlit interface (default)")
    group.add_argument("--web", action="store_true", help="Launch Flask web interface")
    group.add_argument("--audio", type=str, help="Process customer audio file directly")
    parser.add_argument("--port", type=int, default=None, help="Port to run the web server on")

    args = parser.parse_args()

    if args.web:
        port = args.port or 5000
        run_flask(port=port)
    elif args.audio:
        run_cli_audio(args.audio)
    else:
        # Default to streamlit
        port = args.port or 8501
        run_streamlit(port=port)


if __name__ == "__main__":
    main()
