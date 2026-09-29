# Voice-Intent Integration

A lightweight integration project that connects an existing voice processing service and an intent classification service into an end-to-end customer voice reservation assistant.

---

## 1. Project Overview

We built this project to bridge two standalone modules:
* `Audio-Conversation-Voice-Response` (voice processing: speech-to-text and text-to-speech)
* `Customer-Intent-Classification` (intent detection and slot extraction)

Instead of manually typing customer text or selecting form fields, a customer interacts entirely through voice. The pipeline accepts customer audio, transcribes the speech, identifies the customer's intent, drafts a conversational reply, generates a playable audio response, and saves a structured JSON file of the classification result.

Both a command-line interface and a web application are included, allowing users to upload or record audio, review the transcription and formatted JSON, listen to the generated speech, and download both output files separately.

---

## 2. Features

* **Audio file upload via web interface**: Drag and drop audio files, browse local files (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`), record live through your browser microphone, or pick from 10 sample customer recordings.
* **Speech-to-text transcription**: Converts customer audio to text using the voice processing module.
* **Intent classification**: Extracts intents (`booking`, `inquiry`, `modification`, `cancellation`) and reservation slots (`party_size`, `date`, `time`, `food_preference`, `summary`) without modifying classifier fields.
* **JSON output file generation**: Automatically formats and saves the classification result as a separate `.json` file in the `intents/` folder.
* **Spoken response generation**: Drafts a conversational answer based on the intent, translates dates and times into natural speech (e.g. converting `20:00` to "8 PM"), and prompts for missing details.
* **Text-to-speech conversion**: Converts the drafted response into realistic speech saved as an `.mp3` file in `responses/`.
* **In-browser audio playback**: Built-in audio player lets you listen to the response as soon as processing completes.
* **Formatted JSON display**: Shows the intent classification output on the website in a readable view with syntax highlighting.
* **Separate download buttons**: Dedicated buttons to download the generated `intent_result.json` file and the response `.mp3` audio file separately.

---

## 3. Project Structure

```text
voice-intent-integration/
├── main.py                  # Pipeline orchestrator and command-line entry point
├── voice_adapter.py         # Adapter for speech-to-text (STT) and text-to-speech (TTS)
├── intent_adapter.py        # Adapter for intent classification and entity extraction
├── response_generator.py    # Formulates conversational reply text and follow-up prompts
├── sanitizer.py             # Redacts API keys and internal file paths in logs
├── config.py                # Resolves paths, working directories, and settings
├── web_app.py               # Flask server and REST API endpoints
├── app.py                   # Alternative Streamlit web interface
├── interface.py             # CLI launcher for web apps and terminal processing
├── run_e2e_audio_tests.py   # Standalone runner for the 10 customer audio test cases
├── requirements.txt         # Dependencies for this integration project
├── .env.example             # Example environment file template
├── audio/                   # Audio inputs
│   ├── sample_customer_audio.wav
│   ├── uploads/             # Temporary storage for uploads and mic recordings
│   └── test_cases/          # 10 realistic customer test recordings (.mp3)
├── intents/                 # Output folder for generated intent JSON files
├── responses/               # Output folder for generated response MP3 files
├── templates/
│   └── index.html           # Web interface template with player, JSON viewer, and downloads
└── tests/                   # Automated test suite (unit, boundary, interface, e2e)
```

### Key Files Explained

* **`main.py`**: The central coordinator (`VoiceIntentOrchestrator`). Manages audio validation, transcription, intent classification, JSON saving, response generation, and audio synthesis.
* **`voice_adapter.py`**: Interacts with the voice processing service for speech-to-text and text-to-speech. Includes an offline mock mode for testing without external APIs.
* **`intent_adapter.py`**: Passes customer text to the classifier and returns a normalized dictionary of intents and slots.
* **`response_generator.py`**: Generates friendly conversational text based on the detected intent and asks follow-up questions if required details are missing.
* **`sanitizer.py`**: Cleans logs and user-facing messages by masking API keys and local file paths.
* **`config.py`**: Auto-detects sibling project folders, loads `.env` variables, and sets up working directories.
* **`web_app.py`**: Runs the Flask web application and exposes endpoints for processing audio and serving download files securely.
* **`templates/index.html`**: Single-page frontend with microphone recording, drag-and-drop file upload, audio player, syntax-highlighted JSON viewer, and download buttons.

---

## 4. How It Works

Here is the step-by-step process when an audio file is submitted:

```text
Customer Audio (Upload / Mic / Test Case)
       │
       ▼
1. Speech-to-Text (Transcribes customer audio to text)
       │
       ▼
2. Intent Classification (Extracts intent and reservation parameters)
       │
       ▼
3. Save Intent JSON (Writes formatted classification result to intents/)
       │
       ▼
4. Response Generation (Drafts spoken reply text and prompts for missing slots)
       │
       ▼
5. Text-to-Speech (Synthesizes reply text into spoken audio in responses/)
       │
       ▼
6. Web Presentation (Displays transcript, syntax-highlighted JSON & audio player)
       │
       ▼
7. Separate Downloads (User can download intent_result.json and response_audio.mp3)
```

1. **Upload audio**: The user uploads an audio file, records speech with a microphone, or clicks a pre-recorded test scenario.
2. **Transcribe speech**: `voice_adapter.py` validates the audio format and converts customer speech into text.
3. **Classify intent**: `intent_adapter.py` passes the transcript to the intent classifier to extract the intent and details (party size, date, time, food preference, summary).
4. **Save JSON file**: `main.py` saves the exact classification result as a `.json` file in `intents/`.
5. **Draft response**: `response_generator.py` writes an appropriate customer reply. If key reservation details are missing (e.g., party size or time), it politely asks for them.
6. **Synthesize speech**: `voice_adapter.py` converts the response text into speech and saves it as an `.mp3` file in `responses/`.
7. **Display results**: The web app displays the transcribed text, renders the JSON output with color highlighting, and loads the audio player.
8. **Download files**: The user can click **Download JSON** to get `intent_result.json` and **Download Audio** to get the `.mp3` file.

---

## 5. Environment Setup

A pre-configured `.env` file is **already provided with this project**.

Before running the application, make sure the provided `.env` file is placed directly inside the **project root directory (`voice-intent-integration/`)**.

```text
voice-intent-integration/
├── .env      <-- Place the provided .env file here
├── main.py
├── ...
```

The `.env` file contains the required environment variables. Do not include actual API keys or secret values in the README.

**Important:**

* Do not create a new `.env` file if the provided one is available.
* Do not commit the `.env` file to GitHub because it may contain API keys or other sensitive information.
* Do not expose or copy actual API keys or secret values into the README.

---

## 6. Installation and Setup

### Prerequisites

* Python 3.10 or higher
* The two sibling project folders located in the parent directory:
  * `Audio-Conversation-Voice-Response` (or `voice-processing`)
  * `Customer-Intent-Classification` (or `intent-classification`)

### 1. Install Dependencies

Install the packages needed by the integration project:

```bash
cd voice-intent-integration
pip install -r requirements.txt
```

### 2. Verify Configuration

Run the configuration check to confirm that your `.env` file and sibling projects are detected:

```bash
python main.py --check-env
```

If everything is configured correctly, it will report that directories and API keys are ready.

---

## 7. Running the Application

### 1. Web Application (Flask - Recommended)

Start the web server:

```bash
python web_app.py
```
*(You can also use `python interface.py --web`)*

Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

**How to use the website:**
1. Choose how you want to provide audio:
   * **Record Voice**: Click the microphone button, speak your request, and click stop.
   * **Upload Audio File**: Drag and drop an audio file (`.wav`, `.mp3`, `.m4a`, etc.) or click to browse.
   * **Customer Scenarios**: Click any of the 10 quick-select scenario chips (e.g. "2. New Booking", "5. Dining Inquiry").
2. Click **Process Customer Audio**.
3. View and play results:
   * The audio player will automatically load and play the assistant's spoken reply.
   * Read the customer's transcribed speech directly below the player.
   * Inspect the formatted intent classification JSON in the code viewer.
   * Use the collapsible diagnostics drawer to view extracted reservation tags and status details.
4. Download results:
   * Click **Download Audio** to save the generated `.mp3` file.
   * Click **Download JSON** to save the generated `intent_result.json` file.

### 2. Streamlit Web Application (Alternative)

If you prefer using Streamlit:

```bash
python -m streamlit run app.py
```
*(Or via `python interface.py --streamlit`)*

Open `http://localhost:8501` in your browser.

### 3. Command Line Interface (CLI)

You can also run audio files directly in your terminal:

```bash
# Process a sample customer audio file
python main.py audio/sample_customer_audio.wav

# Process a pre-recorded test scenario
python main.py audio/test_cases/02_new_booking.mp3

# Specify custom output paths for audio and JSON
python main.py audio/sample_customer_audio.wav -o responses/custom_reply.mp3 -j intents/custom_intent.json

# Skip speech synthesis (transcription and JSON output only)
python main.py audio/sample_customer_audio.wav --no-tts

# Test with direct text simulation (bypassing speech-to-text)
python main.py --text "I would like to reserve a table for four tonight at 8 PM"

# Run in offline mock mode (no external API calls)
python main.py audio/sample_customer_audio.wav --mock
```

---

## 8. Output Files

Every successful run produces two output files saved to disk:

### 1. Intent Classification JSON File (`intents/`)

* **Saved to**: `intents/<audio_stem>_intent_<timestamp>_<uuid>.json`
* **Format**: Formatted UTF-8 JSON.
* **Content**: The complete dictionary returned by the intent classifier, preserving all keys:
  ```json
  {
    "intent": "booking",
    "party_size": 4,
    "date": "2026-10-02",
    "time": "20:00",
    "food_preference": null,
    "summary": "Customer wants to book a table for 4 people on Friday at 8 PM."
  }
  ```
* **Safety check**: If transcription fails or audio is empty, no misleading JSON file is generated.

### 2. Audio Response File (`responses/`)

* **Saved to**: `responses/resp_<uuid>.mp3` (or `responses/ui_resp_<uuid>.mp3` from the web app)
* **Format**: Standard `.mp3` audio.
* **Content**: The synthesized voice response generated from the assistant's reply text.
* **Safety check**: Verified to exist and have a valid non-zero size before completion.

### How Downloads Work

* **Download JSON**: Clicking the button calls `/api/intent/<filename>?download=true&filename=intent_result.json`. The server validates that the file is inside the safe `intents/` directory and sends the actual file with attachment headers so your browser saves it as `intent_result.json`.
* **Download Audio**: Clicking the button calls `/api/audio/<filename>?download=true&filename=<filename>`, sending the actual `.mp3` file generated for that run.

Both download routes strictly guard against path traversal attempts (`403 Forbidden` for unauthorized paths).

---

## 9. Testing

The project has a comprehensive automated test suite inside the `tests/` directory covering unit tests, boundaries, error handling, web interface features, dual output generation, and end-to-end audio pipeline execution.

### Run All Tests

To run the complete test suite:

```bash
python -m pytest tests/ -v
```

**Actual test output:**
```text
======================== 136 passed, 1 warning in 104.42s ========================
```
All **136 tests passed** with 0 failures across all 14 test modules.

### Run Web Interface & Download Tests

Tests the web endpoints, response rendering, separate download buttons, attachment headers, and path traversal security:

```bash
python -m pytest tests/test_interface.py -v
```

**Actual test output:**
```text
============================= 12 passed in 7.17s =============================
```

### Run Dual Output Tests

Verifies that both the JSON file and audio file are generated across intents, custom paths, and failure modes:

```bash
python -m pytest tests/test_json_and_audio_output.py -v
```

**Actual test output:**
```text
============================= 12 passed in 10.15s =============================
```

### Run End-to-End Audio Pipeline Tests

Executes all 10 realistic customer audio recordings through the entire pipeline:

```bash
python run_e2e_audio_tests.py
```
*(Or via `python -m pytest tests/test_e2e_audio_pipeline.py -v`)*

**Actual test output:**
```text
All 10 customer audio test scenarios passed successfully.
```

### Run Specific Boundary Tests

```bash
# Test audio validation and speech-to-text boundary
python -m unittest tests/test_boundary_1_voice_to_text.py

# Test text validation and intent classification boundary
python -m unittest tests/test_boundary_2_text_to_intent.py

# Test response generation logic and missing slot prompts
python -m unittest tests/test_boundary_3_intent_to_response.py

# Test speech synthesis and response audio output
python -m unittest tests/test_boundary_4_response_to_audio.py

# Test system integrity and sibling project independence
python -m unittest tests/test_boundary_5_system_integrity.py

# Test error handling and sensitive token sanitization
python -m unittest tests/test_error_handling.py
```
