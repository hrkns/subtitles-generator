import logging

import pytest

from generate_output import convert_to_srt_time, extract_time_from_filename, validate_output


def test_validate_output_returns_default_file_for_directory(tmp_path):
    assert validate_output(str(tmp_path)) == str(tmp_path / "output.srt")


def test_validate_output_rejects_non_srt_file(tmp_path):
    invalid_output = tmp_path / "output.txt"

    with pytest.raises(ValueError, match="Invalid output file type"):
        validate_output(str(invalid_output))


def test_validate_output_rejects_missing_directory(tmp_path):
    missing_output = tmp_path / "missing" / "output.srt"

    with pytest.raises(Exception, match="Output directory does not exist"):
        validate_output(str(missing_output))


def test_validate_output_warns_before_overwriting_existing_file(tmp_path, caplog):
    output_file = tmp_path / "existing.srt"
    output_file.write_text("existing subtitles", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        resolved_output = validate_output(str(output_file))

    assert resolved_output == str(output_file)
    assert "will be overwritten" in caplog.text


@pytest.mark.parametrize(
    ("time_in_seconds", "expected"),
    [
        (3661.234, "01:01:01,234"),
        (90002.5, "25:00:02,500"),
    ],
)
def test_convert_to_srt_time(time_in_seconds, expected):
    assert convert_to_srt_time(time_in_seconds) == expected


def test_extract_time_from_filename_returns_segment_start_offset():
    filename = "speech_recognition_result_segment_010203_010303.json"

    assert extract_time_from_filename(filename) == 3723


def test_extract_time_from_filename_returns_none_for_invalid_names():
    assert extract_time_from_filename("invalid.json") is None
