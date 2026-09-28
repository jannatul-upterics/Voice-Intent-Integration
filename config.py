"""
Configuration module for the Voice-Intent Integration Orchestrator.

Manages directories, paths to sibling projects (voice-processing and intent-classification),
and runtime parameters for the audio-intent pipeline.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    # Load .env if present in the project root
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Base directory for the voice-intent-integration project
BASE_DIR: Path = Path(__file__).resolve().parent

# Parent directory containing all projects
PARENT_DIR: Path = BASE_DIR.parent

# Working directories for audio input, response generation, and intent classification output
AUDIO_DIR: Path = BASE_DIR / "audio"
RESPONSES_DIR: Path = BASE_DIR / "responses"
INTENTS_DIR: Path = BASE_DIR / "intents"

# Ensure runtime directories exist
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
INTENTS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_project_path(env_var: str, candidate_folder_names: list[str]) -> Optional[Path]:
    """
    Resolve the absolute path to a sibling project.
    
    Checks:
      1. Explicit environment variable override.
      2. Candidate folder names in the parent directory.
    """
    env_path = os.getenv(env_var)
    if env_path:
        custom_path = Path(env_path).resolve()
        if custom_path.exists():
            return custom_path

    for candidate in candidate_folder_names:
        candidate_path = PARENT_DIR / candidate
        if candidate_path.exists() and candidate_path.is_dir():
            return candidate_path.resolve()

    return None


# Sibling project path resolution (supporting both standard and existing folder names)
VOICE_PROCESSING_DIR: Optional[Path] = resolve_project_path(
    "VOICE_PROCESSING_DIR",
    ["voice-processing", "Audio-Conversation-Voice-Response"]
)

INTENT_CLASSIFICATION_DIR: Optional[Path] = resolve_project_path(
    "INTENT_CLASSIFICATION_DIR",
    ["intent-classification", "Customer-Intent-Classification"]
)

# Fallback: if GROQ_API_KEY is not set in environment or local .env,
# load from sibling projects (.env) if available
if "GROQ_API_KEY" not in os.environ:
    for sibling_dir in [INTENT_CLASSIFICATION_DIR, VOICE_PROCESSING_DIR]:
        if sibling_dir:
            sibling_env = sibling_dir / ".env"
            if sibling_env.exists():
                try:
                    from dotenv import load_dotenv
                    load_dotenv(sibling_env)
                    if "GROQ_API_KEY" in os.environ:
                        break
                except ImportError:
                    pass

# Supported audio input formats
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}

# Audio response settings
DEFAULT_RESPONSE_FORMAT = "mp3"
DEFAULT_SAMPLE_RATE = 16000

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def get_environment_status() -> Dict[str, Any]:
    """
    Return a summary of configuration and sibling project accessibility.
    """
    return {
        "base_dir": str(BASE_DIR),
        "parent_dir": str(PARENT_DIR),
        "audio_dir": {
            "path": str(AUDIO_DIR),
            "exists": AUDIO_DIR.exists(),
        },
        "responses_dir": {
            "path": str(RESPONSES_DIR),
            "exists": RESPONSES_DIR.exists(),
        },
        "intents_dir": {
            "path": str(INTENTS_DIR),
            "exists": INTENTS_DIR.exists(),
        },
        "voice_processing_project": {
            "path": str(VOICE_PROCESSING_DIR) if VOICE_PROCESSING_DIR else None,
            "detected": VOICE_PROCESSING_DIR is not None and VOICE_PROCESSING_DIR.exists(),
        },
        "intent_classification_project": {
            "path": str(INTENT_CLASSIFICATION_DIR) if INTENT_CLASSIFICATION_DIR else None,
            "detected": INTENT_CLASSIFICATION_DIR is not None and INTENT_CLASSIFICATION_DIR.exists(),
        },
        "has_groq_api_key": bool(os.getenv("GROQ_API_KEY")),
    }
