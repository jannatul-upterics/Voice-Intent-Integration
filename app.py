"""
Streamlit Web Interface for the Voice-Intent Integration Project.

Provides an audio-only customer interface:
  1. Record customer speech via browser microphone (st.audio_input),
     upload customer audio file (.wav, .mp3, .m4a, .ogg, .flac),
     or select a realistic customer audio test case.
  2. Sends the audio through the complete integration pipeline:
     Audio -> voice-processing (STT) -> intent-classification -> response-generation -> voice-processing (TTS).
  3. Synthesizes and plays back the response audio file.
  4. Optionally reveals intermediate transcription and detected intent in a collapsible debug expander.

The user is never required to manually type or provide text, intent, entities, or responses.
"""

import sys
import uuid
from pathlib import Path

import streamlit as st

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from main import VoiceIntentOrchestrator

# Configure Streamlit page
st.set_page_config(
    page_title="The Voice Assistant",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.2rem;
        background: linear-gradient(135deg, #0284c7 0%, #38bdf8 50%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        font-size: 1rem;
        text-align: center;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .flow-badge {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 0.6rem;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid #334155;
        border-radius: 9999px;
        padding: 0.5rem 1.2rem;
        font-size: 0.85rem;
        font-weight: 600;
        color: #e2e8f0;
        margin: 0 auto 1.75rem auto;
        width: fit-content;
    }
    .flow-arrow {
        color: #38bdf8;
        font-weight: bold;
    }
    .response-card {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 12px;
        padding: 1.25rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header & Subtitle
st.markdown("<div class='main-header'>The Voice Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Autonomous Restaurant Voice Reservation & Inquiry System</div>", unsafe_allow_html=True)

# Pipeline Flow Banner
st.markdown(
    """
    <div class='flow-badge'>
        <span>🎙️ Customer Audio</span>
        <span class='flow-arrow'>➔</span>
        <span>⚙️ Integration Pipeline</span>
        <span class='flow-arrow'>➔</span>
        <span>🔊 Spoken Audio Response</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Cache orchestrator instance so it initializes once
@st.cache_resource
def get_orchestrator():
    return VoiceIntentOrchestrator()

orchestrator = get_orchestrator()

# Temporary upload directory
upload_dir = config.AUDIO_DIR / "uploads"
upload_dir.mkdir(parents=True, exist_ok=True)
test_cases_dir = config.AUDIO_DIR / "test_cases"

# ---------------------------------------------------------------------------
# Section 1: Audio Input Only (No text, intent, or slot inputs)
# ---------------------------------------------------------------------------
st.subheader("1. Provide Customer Audio")

input_method = st.radio(
    "Select Audio Input Method:",
    options=["🎙️ Record Microphone", "📁 Upload Audio File", "🎵 Pre-recorded Scenarios"],
    horizontal=True,
    label_visibility="collapsed",
)

audio_file_to_process = None
audio_label = None

if input_method == "🎙️ Record Microphone":
    st.caption("Click the microphone below to record customer speech:")
    recorded_audio = st.audio_input("Record customer speech")
    if recorded_audio:
        temp_audio_path = upload_dir / f"mic_rec_{uuid.uuid4().hex[:8]}.wav"
        with open(temp_audio_path, "wb") as f:
            f.write(recorded_audio.getvalue())
        audio_file_to_process = temp_audio_path
        audio_label = f"Microphone Recording ({temp_audio_path.stat().st_size / 1024:.2f} KB)"
        st.success(f"Recorded: {audio_label}")

elif input_method == "📁 Upload Audio File":
    st.caption("Upload a customer audio file (.wav, .mp3, .m4a, .ogg, .flac):")
    uploaded_file = st.file_uploader(
        "Choose an audio file",
        type=["wav", "mp3", "m4a", "ogg", "flac"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        suffix = Path(uploaded_file.name).suffix or ".wav"
        temp_audio_path = upload_dir / f"upload_{uuid.uuid4().hex[:8]}{suffix}"
        with open(temp_audio_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        audio_file_to_process = temp_audio_path
        audio_label = f"{uploaded_file.name} ({temp_audio_path.stat().st_size / 1024:.2f} KB)"
        st.audio(temp_audio_path, format=f"audio/{suffix.lstrip('.')}")
        st.success(f"Loaded: {audio_label}")

else:  # Pre-recorded Scenarios
    st.caption("Select one of the 10 realistic customer audio test scenarios:")
    scenarios = {
        "01_greeting.mp3": "1. Greeting ('Hello, good evening...')",
        "02_new_booking.mp3": "2. New Booking ('Table for four this Friday at 8 PM...')",
        "03_booking_guest_count.mp3": "3. Booking with Guest Count ('Table for six guests...')",
        "04_booking_date_time.mp3": "4. Booking with Date & Time ('Tomorrow evening at 7:30 PM...')",
        "05_inquiry.mp3": "5. Dining Inquiry ('Vegetarian & gluten-free options...')",
        "06_modification.mp3": "6. Modification Request ('Change booking to 6 on Saturday...')",
        "07_cancellation.mp3": "7. Cancellation Request ('Cancel reservation for this Friday...')",
        "08_incomplete_request.mp3": "8. Incomplete Request ('Table for tonight please...')",
        "09_unclear_request.mp3": "9. Unclear Speech ('Thinking about coming by later...')",
        "10_unsupported_request.mp3": "10. Unsupported Request ('Can you book me a taxi?...')"
    }
    selected_key = st.selectbox(
        "Choose scenario:",
        options=list(scenarios.keys()),
        format_func=lambda k: scenarios[k],
        label_visibility="collapsed",
    )
    if selected_key:
        sample_path = test_cases_dir / selected_key
        if not sample_path.exists():
            sample_path = config.AUDIO_DIR / selected_key

        if sample_path.exists():
            audio_file_to_process = sample_path
            audio_label = f"{selected_key} ({sample_path.stat().st_size / 1024:.2f} KB)"
            st.audio(sample_path, format="audio/mp3")

# ---------------------------------------------------------------------------
# Section 2: Pipeline Execution Trigger
# ---------------------------------------------------------------------------
st.write("")
process_clicked = st.button(
    "🚀 Process Customer Audio",
    type="primary",
    disabled=(audio_file_to_process is None),
    use_container_width=True,
)

if process_clicked and audio_file_to_process:
    with st.spinner("Processing customer audio through complete integration pipeline..."):
        out_filename = f"ui_resp_{uuid.uuid4().hex[:8]}.mp3"
        out_path = config.RESPONSES_DIR / out_filename

        # Execute full integration pipeline: Audio -> STT -> Intent -> Response -> TTS -> Audio
        result = orchestrator.process_audio_file(
            audio_path=audio_file_to_process,
            output_audio_path=out_path,
            generate_audio=True,
        )

    # -----------------------------------------------------------------------
    # Section 3: Primary User Experience - Audio Response Playback
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("2. Spoken Audio Response")

    audio_output = result.get("audio_output")
    if audio_output and Path(audio_output).exists() and Path(audio_output).stat().st_size > 0:
        p = Path(audio_output)
        with open(p, "rb") as f:
            audio_bytes = f.read()

        st.audio(audio_bytes, format="audio/mp3", autoplay=True)

        st.markdown(
            f"""
            <div class='response-card'>
                <p style='margin:0; font-size: 1.05rem; font-style: italic; color: #f1f5f9;'>
                    "{result.get('response_text', '')}"
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.download_button(
            label="⬇️ Download Response Audio (MP3)",
            data=audio_bytes,
            file_name=p.name,
            mime="audio/mpeg",
        )
    else:
        st.error(
            result.get("customer_facing_message")
            or "Failed to generate response audio. Please check the logs."
        )

    # -----------------------------------------------------------------------
    # Section 4: Intermediate Pipeline Details (Optional / Debug Expander)
    # -----------------------------------------------------------------------
    with st.expander("🔍 Intermediate Pipeline Details (Debug / Diagnostics)", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**1. Transcribed Customer Speech:**")
            st.code(result.get("customer_text") or "(No speech recognized)", language="text")

            intent_data = result.get("intent_classification") or {}
            detected_intent = intent_data.get("intent", "unknown")
            st.markdown(f"**2. Detected Intent:** `{detected_intent}`")

        with col2:
            st.markdown("**3. Extracted Information:**")
            slots = {}
            for k in ["party_size", "date", "time", "food_preference", "seating_preference", "celebration_requirement"]:
                v = intent_data.get(k)
                if v:
                    slots[k] = v
            if slots:
                st.json(slots)
            else:
                st.caption("No specific reservation entities extracted.")

        st.markdown("**4. Generated Customer Response Text:**")
        st.text_area("Response Text", value=result.get("response_text", ""), height=80, disabled=True)

        json_out = result.get("json_output")
        if json_out and Path(json_out).exists():
            st.markdown(f"**5. Intent Classification JSON Output:** `{Path(json_out).name}`")
            with open(json_out, "r", encoding="utf-8") as jf:
                json_raw_data = jf.read()
            st.download_button(
                label="⬇️ Download Intent JSON",
                data=json_raw_data,
                file_name=Path(json_out).name,
                mime="application/json",
            )

        st.caption(f"Status: `{result.get('status')}` | Intent JSON: `{json_out}` | Audio Output: `{audio_output}`")

