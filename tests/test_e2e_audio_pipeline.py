"""
End-to-End Audio Test Suite for Voice-Intent Integration.

Tests the full 9-step conversational pipeline where the ONLY input provided is an audio file:
  Audio Input (.wav / .mp3)
  → Correct Transcription
  → Correct Intent
  → Correct Extracted Information
  → Appropriate Response Text
  → Valid Response Audio

Covers all 10 required customer audio scenarios:
 1. Greeting
 2. New booking request
 3. Booking with guest count
 4. Booking with date and time
 5. Inquiry
 6. Modification request
 7. Cancellation request
 8. Incomplete request
 9. Unclear speech/request
10. Invalid or unsupported request

Reports each stage separately and provides an overall pass/fail result.
"""

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from main import VoiceIntentOrchestrator


class StageResult:
    def __init__(self, name: str, passed: bool, detail: str):
        self.name = name
        self.passed = passed
        self.detail = detail


class TestCaseReport:
    def __init__(self, case_id: int, title: str, audio_file: str):
        self.case_id = case_id
        self.title = title
        self.audio_file = audio_file
        self.stages: List[StageResult] = []
        self.overall_passed = True

    def add_stage(self, name: str, passed: bool, detail: str):
        self.stages.append(StageResult(name, passed, detail))
        if not passed:
            self.overall_passed = False

    def print_report(self):
        print("\n" + "=" * 75)
        print(f"  TEST CASE {self.case_id:02d}: {self.title.upper()}")
        print("=" * 75)
        print(f"  [Input Audio]                : {self.audio_file}")
        for i, stage in enumerate(self.stages, 1):
            status_tag = "[PASS]" if stage.passed else "[FAIL]"
            # Format stage detail to avoid excessive width
            detail_str = stage.detail
            if len(detail_str) > 70:
                detail_str = detail_str[:67] + "..."
            print(f"  [Stage {i}/5] {stage.name:<22}: {detail_str:<70} {status_tag}")
        print("-" * 75)
        overall_tag = "PASS" if self.overall_passed else "FAIL"
        print(f"  >> Test Case Result          : {overall_tag}")
        print("=" * 75)


class TestEndToEndAudioPipeline(unittest.TestCase):
    """End-to-End Pipeline Verification using ONLY Audio Inputs."""

    reports: List[TestCaseReport] = []

    @classmethod
    def setUpClass(cls):
        cls.orchestrator = VoiceIntentOrchestrator(mock_mode=False)
        cls.test_cases_dir = config.AUDIO_DIR / "test_cases"
        cls.reports = []

    def _execute_e2e_audio_case(
        self,
        case_id: int,
        title: str,
        audio_filename: str,
        expected_transcript_keywords: List[str],
        expected_intent: str,
        expected_slots: Dict[str, Any],
        expected_response_keywords: List[str],
    ) -> Dict[str, Any]:
        """
        Executes and validates a single end-to-end audio test case across all 5 verification stages.
        Input MUST be an audio file path only.
        """
        audio_path = self.test_cases_dir / audio_filename
        report = TestCaseReport(case_id, title, audio_filename)

        # -------------------------------------------------------------------
        # Verification 1: Audio Input Validation
        # -------------------------------------------------------------------
        audio_valid = audio_path.exists() and audio_path.stat().st_size > 0 and audio_path.suffix.lower() in config.SUPPORTED_AUDIO_EXTENSIONS
        size_kb = (audio_path.stat().st_size / 1024) if audio_path.exists() else 0
        report.add_stage(
            "Audio Input",
            audio_valid,
            f"{audio_path.name} ({size_kb:.2f} KB, format={audio_path.suffix})"
        )
        self.assertTrue(audio_valid, f"Audio file {audio_filename} must exist and be non-empty.")

        # Execute full 9-step orchestration pipeline
        output_audio_dest = config.RESPONSES_DIR / f"e2e_{case_id:02d}_response.mp3"
        result = self.orchestrator.process_audio_file(
            audio_path=audio_path,
            output_audio_path=output_audio_dest,
            generate_audio=True,
        )

        # -------------------------------------------------------------------
        # Verification 2: Correct Transcription
        # -------------------------------------------------------------------
        transcript = result.get("customer_text") or ""
        transcript_passed = bool(transcript.strip()) and all(
            kw.lower() in transcript.lower() for kw in expected_transcript_keywords
        )
        report.add_stage(
            "Correct Transcription",
            transcript_passed,
            f'"{transcript}"'
        )
        self.assertTrue(
            transcript_passed,
            f"Transcription '{transcript}' missing expected keywords: {expected_transcript_keywords}"
        )

        # -------------------------------------------------------------------
        # Verification 3: Correct Intent
        # -------------------------------------------------------------------
        intent_data = result.get("intent_classification") or {}
        detected_intent = str(intent_data.get("intent", "")).lower()
        if isinstance(expected_intent, (list, tuple, set)):
            intent_passed = detected_intent in [i.lower() for i in expected_intent]
            exp_display = "/".join(expected_intent)
        else:
            intent_passed = (detected_intent == expected_intent.lower())
            exp_display = expected_intent

        report.add_stage(
            "Correct Intent",
            intent_passed,
            f"Detected='{detected_intent}' (Expected='{exp_display}')"
        )
        self.assertTrue(
            intent_passed,
            f"Detected intent '{detected_intent}' does not match expected '{exp_display}'"
        )

        # -------------------------------------------------------------------
        # Verification 4: Correct Extracted Information
        # -------------------------------------------------------------------
        slots_passed = True
        slot_details = []
        for slot_key, expected_val in expected_slots.items():
            actual_val = intent_data.get(slot_key)
            if expected_val is not None:
                if str(actual_val) != str(expected_val):
                    slots_passed = False
                    slot_details.append(f"{slot_key}: {actual_val} != {expected_val}")
                else:
                    slot_details.append(f"{slot_key}={actual_val}")
            else:
                slot_details.append(f"{slot_key}={actual_val}")

        slots_summary = ", ".join(slot_details) if slot_details else "No mandatory slot constraints"
        report.add_stage("Extracted Information", slots_passed, slots_summary)
        self.assertTrue(slots_passed, f"Slot extraction discrepancy: {slot_details}")

        # -------------------------------------------------------------------
        # Verification 5: Appropriate Response Text
        # -------------------------------------------------------------------
        resp_text = result.get("response_text") or ""
        response_passed = bool(resp_text.strip()) and all(
            kw.lower() in resp_text.lower() for kw in expected_response_keywords
        )
        # Verify speech friendliness (no markdown or raw tokens)
        speech_friendly = "**" not in resp_text and "`" not in resp_text
        response_passed = response_passed and speech_friendly

        report.add_stage(
            "Appropriate Response",
            response_passed,
            f'"{resp_text}"'
        )
        self.assertTrue(
            response_passed,
            f"Response text '{resp_text}' failed criteria (keywords: {expected_response_keywords}, speech-friendly: {speech_friendly})"
        )

        # -------------------------------------------------------------------
        # Verification 6: Valid Response Audio
        # -------------------------------------------------------------------
        out_audio_path = result.get("audio_output")
        audio_ready = False
        out_kb = 0.0
        if out_audio_path:
            p = Path(out_audio_path)
            if p.exists() and p.stat().st_size > 0 and p.suffix.lower() == ".mp3":
                audio_ready = True
                out_kb = p.stat().st_size / 1024

        report.add_stage(
            "Valid Response Audio",
            audio_ready,
            f"{Path(out_audio_path).name if out_audio_path else 'None'} ({out_kb:.2f} KB)"
        )
        self.assertTrue(audio_ready, f"Synthesized response audio must exist and be non-empty: {out_audio_path}")

        # Record and print stage report
        self.__class__.reports.append(report)
        report.print_report()
        return result

    # -----------------------------------------------------------------------
    # Test Case 1: Greeting
    # -----------------------------------------------------------------------
    def test_01_customer_greeting(self):
        """Audio Case 1: Customer greets the system politely."""
        self._execute_e2e_audio_case(
            case_id=1,
            title="Greeting",
            audio_filename="01_greeting.mp3",
            expected_transcript_keywords=["hello", "evening"],
            expected_intent="inquiry",
            expected_slots={},
            expected_response_keywords=["assist"],
        )

    # -----------------------------------------------------------------------
    # Test Case 2: New booking request
    # -----------------------------------------------------------------------
    def test_02_new_booking_request(self):
        """Audio Case 2: Customer places new complete table reservation."""
        self._execute_e2e_audio_case(
            case_id=2,
            title="New Booking Request",
            audio_filename="02_new_booking.mp3",
            expected_transcript_keywords=["book", "four", "friday", "8"],
            expected_intent="booking",
            expected_slots={"party_size": 4, "time": "20:00"},
            expected_response_keywords=["4 guests", "September 25th", "8 PM"],
        )

    # -----------------------------------------------------------------------
    # Test Case 3: Booking with guest count
    # -----------------------------------------------------------------------
    def test_03_booking_with_guest_count(self):
        """Audio Case 3: Customer specifies guest count only, system prompts for date/time."""
        self._execute_e2e_audio_case(
            case_id=3,
            title="Booking with Guest Count",
            audio_filename="03_booking_guest_count.mp3",
            expected_transcript_keywords=["table", "six", "guests"],
            expected_intent="booking",
            expected_slots={"party_size": 6},
            expected_response_keywords=["6 guests", "which date and time"],
        )

    # -----------------------------------------------------------------------
    # Test Case 4: Booking with date and time
    # -----------------------------------------------------------------------
    def test_04_booking_with_date_and_time(self):
        """Audio Case 4: Customer specifies date and time, system prompts for guest count."""
        self._execute_e2e_audio_case(
            case_id=4,
            title="Booking with Date and Time",
            audio_filename="04_booking_date_time.mp3",
            expected_transcript_keywords=["tomorrow", "7:30"],
            expected_intent="booking",
            expected_slots={"time": "19:30"},
            expected_response_keywords=["7:30 PM", "how many guests"],
        )

    # -----------------------------------------------------------------------
    # Test Case 5: Inquiry
    # -----------------------------------------------------------------------
    def test_05_customer_inquiry(self):
        """Audio Case 5: Customer asks about dietary options and operating hours."""
        self._execute_e2e_audio_case(
            case_id=5,
            title="Inquiry",
            audio_filename="05_inquiry.mp3",
            expected_transcript_keywords=["vegan", "dinner"],
            expected_intent="inquiry",
            expected_slots={},
            expected_response_keywords=["vegan", "vegetarian", "gluten-free"],
        )

    # -----------------------------------------------------------------------
    # Test Case 6: Modification request
    # -----------------------------------------------------------------------
    def test_06_modification_request(self):
        """Audio Case 6: Customer requests reservation change."""
        self._execute_e2e_audio_case(
            case_id=6,
            title="Modification Request",
            audio_filename="06_modification.mp3",
            expected_transcript_keywords=["change", "six", "8:30"],
            expected_intent="modification",
            expected_slots={"party_size": 6, "time": "20:30"},
            expected_response_keywords=["6 guests", "8:30 PM", "confirmation number"],
        )

    # -----------------------------------------------------------------------
    # Test Case 7: Cancellation request
    # -----------------------------------------------------------------------
    def test_07_cancellation_request(self):
        """Audio Case 7: Customer cancels reservation."""
        self._execute_e2e_audio_case(
            case_id=7,
            title="Cancellation Request",
            audio_filename="07_cancellation.mp3",
            expected_transcript_keywords=["cancel", "reservation", "friday"],
            expected_intent="cancellation",
            expected_slots={},
            expected_response_keywords=["cancel your reservation", "confirmation number"],
        )

    # -----------------------------------------------------------------------
    # Test Case 8: Incomplete request
    # -----------------------------------------------------------------------
    def test_08_incomplete_request(self):
        """Audio Case 8: Customer provides date only, system prompts for party and time."""
        self._execute_e2e_audio_case(
            case_id=8,
            title="Incomplete Request",
            audio_filename="08_incomplete_request.mp3",
            expected_transcript_keywords=["table", "tonight"],
            expected_intent="booking",
            expected_slots={},
            expected_response_keywords=["how many guests", "what time"],
        )

    # -----------------------------------------------------------------------
    # Test Case 9: Unclear speech/request
    # -----------------------------------------------------------------------
    def test_09_unclear_request(self):
        """Audio Case 9: Ambiguous/unclear speech prompts polite general inquiry response."""
        self._execute_e2e_audio_case(
            case_id=9,
            title="Unclear Speech / Request",
            audio_filename="09_unclear_request.mp3",
            expected_transcript_keywords=["thinking", "coming"],
            expected_intent="inquiry",
            expected_slots={},
            expected_response_keywords=["lunch", "dinner"],
        )

    # -----------------------------------------------------------------------
    # Test Case 10: Invalid or unsupported request
    # -----------------------------------------------------------------------
    def test_10_unsupported_request(self):
        """Audio Case 10: Request outside restaurant capabilities is handled politely."""
        self._execute_e2e_audio_case(
            case_id=10,
            title="Invalid / Unsupported Request",
            audio_filename="10_unsupported_request.mp3",
            expected_transcript_keywords=["taxi", "airport"],
            expected_intent=["inquiry", "unsupported", "unknown", "booking"],
            expected_slots={},
            expected_response_keywords=["dining"],
        )

    @classmethod
    def tearDownClass(cls):
        """Print overall pass/fail summary table across all 10 end-to-end cases."""
        if not cls.reports:
            return

        print("\n" + "=" * 75)
        print("  END-TO-END AUDIO PIPELINE TEST SUITE - OVERALL SUMMARY")
        print("=" * 75)
        print(f"  {'#':<4} {'Scenario Title':<35} {'Audio Input File':<25} {'Result':<8}")
        print("-" * 75)

        passed_count = 0
        for r in cls.reports:
            status_text = "PASS" if r.overall_passed else "FAIL"
            if r.overall_passed:
                passed_count += 1
            print(f"  {r.case_id:<4} {r.title:<35} {r.audio_file:<25} {status_text:<8}")

        print("=" * 75)
        total = len(cls.reports)
        rate = (passed_count / total * 100) if total else 0
        overall_status = "ALL TESTS PASSED" if passed_count == total else f"{total - passed_count} FAILED"
        print(f"  TOTAL: {passed_count}/{total} PASSED ({rate:.1f}%) -> [{overall_status}]")
        print("=" * 75 + "\n")


if __name__ == "__main__":
    unittest.main()
