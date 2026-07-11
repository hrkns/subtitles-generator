import json
import os

import generate_output


def _write_segments_file(tmp_dir, filename, segments):
    file_path = tmp_dir / filename
    file_path.write_text(json.dumps({"segments": segments}), encoding="utf-8")
    return file_path


def test_create_srt_content_applies_offsets_and_merges_consecutive_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_output, "TMP_DIR", f"{tmp_path}{os.sep}")

    _write_segments_file(
        tmp_path,
        "speech_recognition_result_segment_000000_000003.json",
        [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "Hello"},
            {"start": 2.0, "end": 3.5, "text": "World"},
        ],
    )
    _write_segments_file(
        tmp_path,
        "speech_recognition_result_segment_000010_000011.json",
        [{"start": 0.0, "end": 1.0, "text": "Again"}],
    )

    srt_content = generate_output.create_srt_content(
        [
            "speech_recognition_result_segment_000000_000003.json",
            "speech_recognition_result_segment_000010_000011.json",
        ]
    )

    subtitles = generate_output.parse_srt(srt_content)

    assert [subtitle.text for subtitle in subtitles] == ["Hello", "World", "Again"]
    assert [subtitle.index for subtitle in subtitles] == ["1", "2", "3"]
    assert subtitles[0].time_to_str(subtitles[0].start) == "00:00:00,000"
    assert subtitles[0].time_to_str(subtitles[0].end) == "00:00:02,000"
    assert subtitles[1].time_to_str(subtitles[1].start) == "00:00:02,000"
    assert subtitles[1].time_to_str(subtitles[1].end) == "00:00:03,500"
    assert subtitles[2].time_to_str(subtitles[2].start) == "00:00:10,000"
    assert subtitles[2].time_to_str(subtitles[2].end) == "00:00:11,000"


def test_merge_srt_content_replaces_overlaps_and_reindexes():
    original_srt = (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "Old 1\n\n"
        "2\n"
        "00:00:02,000 --> 00:00:04,000\n"
        "Old 2\n\n"
        "3\n"
        "00:00:05,000 --> 00:00:06,000\n"
        "Keep\n"
    )
    replacement_srt = (
        "1\n"
        "00:00:01,500 --> 00:00:04,500\n"
        "Replacement\n"
    )

    merged_srt = generate_output.merge_srt_content(original_srt, replacement_srt)
    subtitles = generate_output.parse_srt(merged_srt)

    assert [subtitle.index for subtitle in subtitles] == ["1", "2"]
    assert [subtitle.text for subtitle in subtitles] == ["Replacement", "Keep"]
    assert subtitles[0].time_to_str(subtitles[0].start) == "00:00:01,500"
    assert subtitles[0].time_to_str(subtitles[0].end) == "00:00:04,500"


def test_process_directory_writes_srt_output(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_output, "TMP_DIR", f"{tmp_path}{os.sep}")
    _write_segments_file(
        tmp_path,
        "speech_recognition_result_segment_000000_000002.json",
        [{"start": 0.0, "end": 2.0, "text": "Line one"}],
    )

    output_path = tmp_path / "output.srt"

    generate_output.process_directory(str(output_path))

    assert output_path.read_text(encoding="utf-8") == (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "Line one"
    )


def test_process_directory_merges_into_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_output, "TMP_DIR", f"{tmp_path}{os.sep}")
    _write_segments_file(
        tmp_path,
        "speech_recognition_result_segment_000001_000002.json",
        [{"start": 0.0, "end": 1.0, "text": "Replacement"}],
    )

    output_path = tmp_path / "output.srt"
    output_path.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,000\n"
        "Keep\n\n"
        "2\n"
        "00:00:01,000 --> 00:00:02,000\n"
        "Old\n",
        encoding="utf-8",
    )

    generate_output.process_directory(str(output_path), merge_subtitles=True)

    subtitles = generate_output.parse_srt(output_path.read_text(encoding="utf-8"))

    assert [subtitle.index for subtitle in subtitles] == ["1", "2"]
    assert [subtitle.text for subtitle in subtitles] == ["Keep", "Replacement"]
