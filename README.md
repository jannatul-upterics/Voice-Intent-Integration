# Voice-Intent Integration

A Python integration project that coordinates an audio-in, audio-out workflow for a restaurant reservation assistant, generating **both a structured JSON output file for intent classification and a synthesized audio response file**.

This project acts as an orchestration layer. It accepts customer audio, coordinates transcription through a voice processing adapter, extracts customer intent and reservation details through an intent classification adapter, saves the classification output as a formatted `.json` file, drafts an appropriate spoken reply, and generates a playable `.mp3` audio response file.

---

## Project Structure

```text
voice-intent-integration/
├── main.py                          # Central orchestrator running the full audio-to-JSON and audio-to-speech pipeline
├── voice_adapter.py                 # Adapter for speech-to-text and text-to-speech calls
├── intent_adapter.py                # Adapter for intent detection and entity extraction
├── response_generator.py            # Formulates spoken conversational response text
├── sanitizer.py                     # Redacts sensitive tokens, API keys, and local file paths
├── config.py                        # Path discovery, environment loading, and settings
├── app.py                           # Streamlit web interface with microphone recording and output inspection
├── web_app.py                       # Flask web server and REST API
├── interface.py                     # Command-line launcher for UI and CLI tasks
├── run_e2e_audio_tests.py           # Standalone runner for the 10 customer audio test scenarios
├── requirements.txt                 # Python package dependencies for this project
├── .env.example                     # Template for environment variables
├── .gitignore                       # Git ignore rules for virtual environments, keys, and outputs
├── audio/                           # Audio input directory
│   ├── sample_customer_audio.wav    # Default sample customer recording (.wav)
│   ├── README.md                    # Folder description
│   ├── .gitkeep                     # Keeps directory tracked in version control
│   ├── uploads/                     # Temporary directory for user uploads and mic recordings
│   └── test_cases/                  # 10 realistic customer audio recordings (.mp3)
│       ├── 01_greeting.mp3
│       ├── 02_new_booking.mp3
│       ├── 03_booking_guest_count.mp3
│       ├── 04_booking_date_time.mp3
│       ├── 05_inquiry.mp3
│       ├── 06_modification.mp3
│       ├── 07_cancellation.mp3
│       ├── 08_incomplete_request.mp3
│       ├── 09_unclear_request.mp3
│       └── 10_unsupported_request.mp3
├── intents/                         # Output directory for saved intent classification JSON files
│   ├── .gitkeep                     # Keeps directory tracked in version control
│   └── *_intent_*.json              # Formatted JSON output files containing classifier fields
├── responses/                       # Output directory for generated response audio files
│   ├── README.md                    # Folder description
│   ├── .gitkeep                     # Keeps directory tracked in version control
│   ├── response_mock.mp3            # Lightweight placeholder audio for mock/offline testing
│   └── *.mp3                        # Synthesized response audio files (.mp3)
├── templates/                       # Frontend HTML templates
│   └── index.html                   # Single-page interface for the Flask web app
└── tests/                           # Unit, boundary, interface, output, and end-to-end tests
    ├── __init__.py                  # Test package initialization
    ├── conftest.py                  # Pytest configuration and calendar reference fixture
    ├── test_boundary_1_voice_to_text.py
    ├── test_boundary_2_text_to_intent.py
    ├── test_boundary_3_intent_to_response.py
    ├── test_boundary_4_response_to_audio.py
    ├── test_boundary_5_system_integrity.py
    ├── test_e2e_audio_pipeline.py
    ├── test_error_handling.py
    ├── test_integration.py
    ├── test_intent_integration.py
    ├── test_interface.py
    ├── test_json_and_audio_output.py  # Tests dual JSON and audio response generation
    ├── test_response_generation.py
    ├── test_tts_integration.py
    └── test_voice_integration.py
```

---

## File Descriptions

### Core Integration Modules

* **`main.py`**  
  Contains the `VoiceIntentOrchestrator` class, which manages the pipeline from start to finish. It takes an input audio file, coordinates speech-to-text, intent classification, saving the classification JSON file, response text generation, and text-to-speech synthesis. It returns a dictionary containing the transcription, intent data, path to the saved intent `.json` file (`json_output`), customer response text, and path to the synthesized `.mp3` audio file (`audio_output`). It also provides a direct command-line interface with detailed stage logging.

* **`voice_adapter.py`**  
  Contains `VoiceProcessingAdapter`. It validates incoming audio files (existence, supported extension, and non-empty file size) and delegates speech-to-text and text-to-speech requests to external voice services. It also includes an offline mock mode for testing without external service calls.

* **`intent_adapter.py`**  
  Contains `IntentClassificationAdapter`. It receives customer text, validates that it is non-empty, and interfaces with the intent classification subsystem. It preserves all classifier fields, returning a standardized dictionary containing `intent`, `party_size`, `date`, `time`, `food_preference`, `summary`, and any auxiliary reservation attributes.

* **`response_generator.py`**  
  Contains `ResponseGenerator`. It receives the structured intent dictionary and generates natural, spoken conversational text for the customer. It handles table bookings, dining inquiries, reservation modifications, cancellations, and unclear requests. It translates raw dates and times into conversational speech (such as converting `20:00` into "8 PM"), detects missing parameters (such as guest count or time) to prompt the user with specific follow-up questions, and generates clean fallback messages if an error occurs.

* **`sanitizer.py`**  
  Contains sanitization helper functions (`sanitize_text`, `mask_api_key`, `sanitize_customer_message`). It redacts sensitive tokens (such as `gsk_...` API keys or Bearer tokens) and local filesystem paths from logs and customer messages, ensuring that technical error details and credentials never appear in customer responses.

* **`config.py`**  
  Manages configuration settings, working directories (`AUDIO_DIR`, `RESPONSES_DIR`, `INTENTS_DIR`), supported audio formats (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`), and logging formats. It resolves sibling project paths and loads environment variables from local or parent `.env` files.

### User Interfaces and Launchers

* **`app.py`**  
  A Streamlit web application providing an audio-only user interface. Users can record speech with a browser microphone, upload an audio file, or pick from pre-recorded customer scenarios. It runs the audio through `VoiceIntentOrchestrator`, plays back the resulting audio response, and provides a collapsible debug drawer showing intermediate transcription, extracted slots, and a download button for the generated intent JSON file.

* **`web_app.py`**  
  A lightweight Flask web server. It serves `templates/index.html` and exposes REST endpoints:
  * `POST /api/process_audio`: Accepts multipart audio file uploads or microphone recordings, runs the pipeline, and returns playback URLs for both the response audio and intent JSON.
  * `POST /api/process_sample`: Runs the pipeline against one of the pre-recorded audio test cases.
  * `GET /api/samples`: Returns the list of available audio test cases.
  * `GET /api/audio/<filename>`: Streams response audio files for browser playback.
  * `GET /api/intent/<filename>`: Serves generated intent classification JSON files.

* **`templates/index.html`**  
  The frontend interface for `web_app.py`. Built with HTML5, CSS, and JavaScript. Supports browser microphone recording via the `MediaRecorder` API, drag-and-drop file upload, quick-select test scenarios, an audio player for playback, and an expandable diagnostics drawer.

* **`interface.py`**  
  A unified command-line entry point. Accepts flags to launch either web interface (`--streamlit` or `--web`) or process a local audio file directly via the terminal (`--audio <path>`).

* **`run_e2e_audio_tests.py`**  
  A standalone test runner script that executes the 10 customer audio test scenarios in `audio/test_cases/` and prints a stage-by-stage pass/fail report to the console.

### Configuration and Setup Files

* **`requirements.txt`**  
  Specifies direct dependencies needed by the integration layer: `python-dotenv`, `flask`, and `streamlit`.

* **`.env.example`**  
  Template configuration outlining required and optional variables (`GROQ_API_KEY`, `VOICE_PROCESSING_DIR`, `INTENT_CLASSIFICATION_DIR`, `LOG_LEVEL`).

* **`.gitignore`**  
  Excludes Python bytecode caches, virtual environments, `.env` files, temporary user uploads (`audio/uploads/*`), generated response audio files (`responses/*.mp3`), and generated intent JSON files (`intents/*.json`).

### Audio and Storage Folders

* **`audio/`**  
  Working directory for incoming audio files.
  * `sample_customer_audio.wav`: A default customer audio recording used for quick testing.
  * `uploads/`: Temporary workspace for recordings and files submitted via the web interfaces.
  * `test_cases/`: Contains 10 realistic customer audio recordings covering greetings, new bookings, guest count specifications, date/time specifications, inquiries, modifications, cancellations, incomplete requests, unclear speech, and unsupported requests.

* **`intents/`**  
  Output directory where intent classification result `.json` files are saved. Each processed audio input generates a separate, uniquely named JSON file.

* **`responses/`**  
  Destination directory where synthesized `.mp3` audio response files are saved. Contains `response_mock.mp3` for offline testing.

---

## Workflow

The files in this project interact in a clear, sequential order:

```text
Customer Audio (.wav / .mp3)
           │
           ▼
     [ config.py ] ────────── Validates path and format settings
           │
           ▼
  [ voice_adapter.py ] ────── Checks file validity; converts speech to text (STT)
           │
           ▼
  [ intent_adapter.py ] ───── Receives text; extracts intent and slot entities
           │
           ▼
      [ intents/ ] ────────── Saves intent classification result (.json)
           │
           ▼
[ response_generator.py ] ── Formulates spoken response text and prompts for missing slots
           │
           ▼
    [ sanitizer.py ] ──────── Strips API keys and internal system paths
           │
           ▼
  [ voice_adapter.py ] ────── Converts response text into spoken audio (.mp3 via TTS)
           │
           ▼
     [ responses/ ] ───────── Saves synthesized audio response for playback
```

### Execution Stages

1. **Input Ingestion**: Customer audio is provided via the CLI, uploaded through `web_app.py`, or recorded via `app.py`.
2. **Audio Validation & Transcription (STT)**: `main.py` passes the audio file to `voice_adapter.py`. The adapter checks that the file exists, has a supported format, and is not 0 bytes. It delegates transcription and returns the customer speech text.
3. **Intent Classification**: `main.py` sends the transcribed text to `intent_adapter.py`. The adapter invokes classification and extracts slots (`party_size`, `date`, `time`, `food_preference`, `summary`, etc.).
4. **Save Intent JSON**: `main.py` formats the full intent classification dictionary and saves it as an indented `.json` file inside `intents/` with a unique filename (`<audio_stem>_intent_<timestamp>_<uuid>.json`).
5. **Response Formulation**: `main.py` passes the intent dictionary and transcribed text to `response_generator.py`. The generator constructs a customer-facing reply, confirming reservation details or asking follow-up questions for any missing parameters.
6. **Text-to-Speech (TTS) Synthesis**: `main.py` sends the response text to `voice_adapter.py`, which synthesizes spoken audio and saves it as a playable `.mp3` file inside `responses/`.
7. **Delivery**: The system outputs the paths to both the generated JSON file and the generated audio response file.

---

## Output Files (JSON & Audio)

For every valid audio input, the pipeline generates two distinct output files:

### 1. Intent Classification JSON Output (`intents/`)

The classification result is saved as a readable, indented `.json` file inside the `intents/` directory.

* **File Naming**: Uniquely generated per run to avoid overwriting earlier outputs:
  ```text
  intents/<audio_stem>_intent_<timestamp>_<unique_id>.json
  ```
  *(Example: `intents/02_new_booking_intent_20260928_195000_a1b2c3.json`)*
* **Preserved Schema**: All fields returned by the classifier are saved verbatim without altering or removing keys:
  ```json
  {
    "intent": "booking",
    "party_size": 4,
    "date": "2026-10-02",
    "time": "20:00",
    "food_preference": {
      "vegetarian": 1
    },
    "summary": "Customer wants to book a table for 4 people on Friday at 8 PM.",
    "seating_preference": {
      "window": 4
    }
  }
  ```
* **Failure Safety**: If the audio file is missing, empty, or unparseable, or if speech transcription fails, no misleading or empty JSON file is written to disk.

### 2. Audio Response File (`responses/`)

The synthesized spoken reply is saved as an audio file inside the `responses/` directory.

* **File Format**: Standard `.mp3` audio format matching the voice adapter.
* **Content**: Contains the assistant's spoken conversational reply (not the input audio).
* **Verification**: The pipeline verifies that the generated audio file exists, is playable, and has a valid non-zero size before completing.

### Inspecting Outputs

* **Terminal / CLI**: Running `main.py` prints the resolved filesystem paths for both outputs:
  ```text
  >> Intent JSON output  : D:\...\voice-intent-integration\intents\sample_intent_...json
  >> Audio response ready : D:\...\voice-intent-integration\responses\resp_...mp3
  ```
* **Streamlit UI (`app.py`)**: The audio player plays the spoken response automatically. The "Intermediate Pipeline Details" expander displays the detected intent, extracted slots, and provides a direct download button for the generated intent `.json` file.
* **Flask Web API (`web_app.py`)**: API responses include `json_output`, `json_output_url` (`/api/intent/<filename>`), and `audio_output_url` (`/api/audio/<filename>`).

---

## Installation and Setup

### 1. Install Dependencies

Install the requirements in your Python environment:

```bash
cd "Voice-Intent-Integration"
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` and configure your settings:

```ini
# Groq API Key (used for transcription and intent extraction)
GROQ_API_KEY=your_groq_api_key_here

# Sibling Project Path Overrides (optional; auto-discovered by default)
# VOICE_PROCESSING_DIR="../Audio-Conversation-Voice-Response"
# INTENT_CLASSIFICATION_DIR="../Customer-Intent-Classification"

# Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

> **Note:** If `GROQ_API_KEY` is already defined in a `.env` file in either sibling project directory, `config.py` discovers and loads it automatically.

To verify that paths and environment variables are detected correctly:

```bash
python main.py --check-env
```

---

## Usage

### 1. Command Line Interface

Process a customer audio file directly:

```bash
# Process a local audio file (generates both JSON and Audio outputs)
python main.py audio/sample_customer_audio.wav

# Process a pre-recorded test scenario
python main.py audio/test_cases/02_new_booking.mp3

# Specify custom output paths for both audio and intent JSON
python main.py audio/sample_customer_audio.wav -o responses/custom_reply.mp3 -j intents/custom_intent.json

# Skip audio synthesis (text response + intent JSON only)
python main.py audio/sample_customer_audio.wav --no-tts

# Skip saving the intent JSON file
python main.py audio/sample_customer_audio.wav --no-json
```

### 2. Streamlit Web Interface

To run the interactive browser interface with microphone recording, playback, and JSON inspection:

```bash
python -m streamlit run app.py
```
*(Or via `python interface.py --streamlit`)*

Open `http://localhost:8501` in your browser.

### 3. Flask Web Application

To run the lightweight web server with REST endpoints:

```bash
python web_app.py
```
*(Or via `python interface.py --web`)*

Open `http://127.0.0.1:5000` in your browser.

### 4. Text Simulation Mode

Run intent classification, save the JSON output, generate response text, and synthesize speech from customer text directly:

```bash
python main.py --text "I would like to reserve a table for four tonight at 8 PM"
```

### 5. Offline Mock Mode

Run the pipeline in offline mock mode without making external API calls:

```bash
python main.py audio/sample_customer_audio.wav --mock
```

---

## Testing

The project includes unit tests, boundary tests, error-handling tests, interface tests, output tests, and end-to-end audio pipeline tests inside the `tests/` directory.

### Run All Tests

To run the entire test suite using `pytest`:

```bash
pytest -v
```

Or using Python's `unittest` module:

```bash
python -m unittest discover tests
```

### Run Dual JSON & Audio Output Tests

Verify that both the JSON output file and audio response file are generated correctly for booking, inquiry, modification, cancellation, and invalid inputs:

```bash
pytest tests/test_json_and_audio_output.py -v
```

### Run the End-to-End Audio Pipeline Tests

Run all 10 customer audio test cases through the complete audio-to-audio pipeline:

```bash
python run_e2e_audio_tests.py
```
*(Or via `pytest tests/test_e2e_audio_pipeline.py -v`)*

### Run Specific Boundary Tests

```bash
# Test audio validation and speech-to-text boundary
python -m unittest tests/test_boundary_1_voice_to_text.py

# Test text validation and intent classification boundary
python -m unittest tests/test_boundary_2_text_to_intent.py

# Test response generation logic and slot handling
python -m unittest tests/test_boundary_3_intent_to_response.py

# Test text-to-speech synthesis and audio output
python -m unittest tests/test_boundary_4_response_to_audio.py

# Test error handling across all failure modes
python -m unittest tests/test_error_handling.py

# Test web interface routes, upload handling, and audio serving
python -m unittest tests/test_interface.py
```
