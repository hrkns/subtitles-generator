import json
import logging
import os

import pytest

import generate_output
import process_input as process_input_module
from generate_output import Subtitle


def test_subtitle_round_trip_preserves_multiline_text():
    block = (
        "7\n"
        "00:00:01,250 --> 00:00:03,500\n"
        "first line\n"
        "second line\n"
    )

    subtitle = Subtitle.from_srt_block(block)

    assert subtitle.index == "7"
    assert subtitle.text == "first line\nsecond line"
    assert Subtitle.time_to_str(subtitle.start) == "00:00:01,250"
    assert Subtitle.time_to_str(subtitle.end) == "00:00:03,500"
    assert subtitle.to_srt_block() == block


def test_subtitle_parse_time_range_rejects_invalid_ranges():
    with pytest.raises(ValueError):
        Subtitle.parse_time_range("not-a-time-range")


def test_create_srt_content_keeps_original_times_when_filename_has_no_offset(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(generate_output, "TMP_DIR", f"{tmp_path}{os.sep}")
    input_file = tmp_path / "custom_name.json"
    input_file.write_text(
        json.dumps({"segments": [{"start": 1.0, "end": 2.5, "text": "No offset"}]}),
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        srt_content = generate_output.create_srt_content([input_file.name])

    subtitles = generate_output.parse_srt(srt_content)

    assert len(subtitles) == 1
    assert subtitles[0].text == "No offset"
    assert Subtitle.time_to_str(subtitles[0].start) == "00:00:01,000"
    assert Subtitle.time_to_str(subtitles[0].end) == "00:00:02,500"
    assert "does not match the expected format" in caplog.text


def test_validate_and_order_checkpoints_warns_when_sorting(caplog):
    with caplog.at_level(logging.WARNING):
        ordered = process_input_module.validate_and_order_checkpoints("00:10,00:05", 20000)

    assert ordered == ["00:05", "00:10"]
    assert "out of order and have been sorted" in caplog.text


def test_parse_segments_warns_for_out_of_order_and_overlapping_ranges(caplog):
    with caplog.at_level(logging.WARNING):
        segments = process_input_module.parse_segments("00:10-00:20,00:15-00:25,00:05-00:08", 30000)

    assert segments == [(10000, 20000), (15000, 25000), (5000, 8000)]
    assert "Segments are out of order" in caplog.text
    assert "are overlapping" in caplog.text
    assert "Overlapping segments detected" in caplog.text


def test_process_directory_logs_errors_when_content_generation_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(generate_output, "TMP_DIR", f"{tmp_path}{os.sep}")
    (tmp_path / "speech_recognition_result_segment_000000_000001.json").write_text("{}", encoding="utf-8")

    def fake_create_srt_content(_json_files):
        raise RuntimeError("boom")

    monkeypatch.setattr(generate_output, "create_srt_content", fake_create_srt_content)

    output_path = tmp_path / "output.srt"

    with caplog.at_level(logging.ERROR):
        generate_output.process_directory(str(output_path))

    assert not output_path.exists()
    assert "An error occurred while processing speech recognition JSON files: boom" in caplog.text
