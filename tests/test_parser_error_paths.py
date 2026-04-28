import logging
import os

import pytest

import generate_output
from process_input import parse_segments


def test_subtitle_from_srt_block_preserves_multiline_text():
    subtitle = generate_output.Subtitle.from_srt_block(
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "Line one\n"
        "Line two\n"
    )

    assert subtitle.index == "1"
    assert subtitle.text == "Line one\nLine two"


def test_parse_srt_ignores_empty_blocks():
    subtitles = generate_output.parse_srt(
        "1\n"
        "00:00:00,000 --> 00:00:01,000\n"
        "Hello\n\n\n"
        "2\n"
        "00:00:01,000 --> 00:00:02,000\n"
        "World\n"
    )

    assert [subtitle.text for subtitle in subtitles] == ["Hello", "World"]


def test_validate_output_rejects_empty_paths():
    with pytest.raises(ValueError, match="must not be empty"):
        generate_output.validate_output("")


def test_process_directory_logs_errors_without_raising(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(generate_output, "TMP_DIR", f"{tmp_path}{os.sep}")
    monkeypatch.setattr(generate_output, "create_srt_content", lambda json_files: (_ for _ in ()).throw(RuntimeError("boom")))
    output_path = tmp_path / "output.srt"

    with caplog.at_level(logging.ERROR):
        generate_output.process_directory(str(output_path))

    assert "An error occurred while processing speech recognition JSON files: boom" in caplog.text
    assert not output_path.exists()


def test_parse_segments_logs_overlap_and_order_warnings(caplog):
    with caplog.at_level(logging.WARNING):
        segments = parse_segments("00:10-00:20,00:15-00:25", 30000)

    assert segments == [(10000, 20000), (15000, 25000)]
    assert "Segments are out of order" in caplog.text
    assert "are overlapping" in caplog.text
