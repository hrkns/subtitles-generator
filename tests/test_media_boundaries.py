import json
import os
from pathlib import Path

import pytest

import process_input
from pydub.exceptions import CouldntDecodeError


class FakeExportedAudioSegment:
    def export(self, file_path, format="mp3"):
        Path(file_path).write_text("audio", encoding="utf-8")
        return format


class FakeInputAudio:
    def __getitem__(self, _segment_slice):
        return FakeExportedAudioSegment()


def test_validate_audio_file_returns_audio_for_existing_mp3(tmp_path, monkeypatch):
    input_file = tmp_path / "input.mp3"
    input_file.write_text("audio", encoding="utf-8")
    expected_audio = object()

    monkeypatch.setattr(process_input.AudioSegment, "from_mp3", lambda path: expected_audio)

    assert process_input.validate_audio_file(str(input_file)) is expected_audio


def test_validate_audio_file_exits_when_file_is_missing(tmp_path):
    with pytest.raises(SystemExit):
        process_input.validate_audio_file(str(tmp_path / "missing.mp3"))


def test_validate_audio_file_exits_for_unsupported_extensions(tmp_path):
    input_file = tmp_path / "input.wav"
    input_file.write_text("audio", encoding="utf-8")

    with pytest.raises(SystemExit):
        process_input.validate_audio_file(str(input_file))


def test_validate_audio_file_exits_when_decoding_fails(tmp_path, monkeypatch):
    input_file = tmp_path / "input.mp3"
    input_file.write_text("audio", encoding="utf-8")

    def raise_decode_error(_path):
        raise CouldntDecodeError()

    monkeypatch.setattr(process_input.AudioSegment, "from_mp3", raise_decode_error)

    with pytest.raises(SystemExit):
        process_input.validate_audio_file(str(input_file))


def test_is_video_file_returns_false_when_file_does_not_exist(tmp_path):
    assert process_input.is_video_file(str(tmp_path / "missing.mp4")) is False


def test_is_video_file_checks_mime_type(tmp_path, monkeypatch):
    input_file = tmp_path / "input.bin"
    input_file.write_text("content", encoding="utf-8")

    class FakeMagic:
        def __init__(self, mime=True):
            self.mime = mime

        def from_file(self, _file_path):
            return "video/mp4"

    monkeypatch.setattr(process_input.magic, "Magic", FakeMagic)

    assert process_input.is_video_file(str(input_file)) is True


def test_extract_audio_writes_audio_file_and_reports_success(monkeypatch, capsys):
    calls = {}

    class FakeAudioFileClip:
        def __init__(self, video_path):
            calls["video_path"] = video_path

        def write_audiofile(self, audio_path):
            calls["audio_path"] = audio_path

    monkeypatch.setattr(process_input, "AudioFileClip", FakeAudioFileClip)

    process_input.extract_audio("input.mp4", "output.mp3")
    captured = capsys.readouterr()

    assert calls == {"video_path": "input.mp4", "audio_path": "output.mp3"}
    assert "Audio extracted and saved to output.mp3" in captured.out


def test_extract_audio_reports_errors_without_raising(monkeypatch, capsys):
    class FakeAudioFileClip:
        def __init__(self, _video_path):
            raise RuntimeError("boom")

    monkeypatch.setattr(process_input, "AudioFileClip", FakeAudioFileClip)

    process_input.extract_audio("input.mp4", "output.mp3")
    captured = capsys.readouterr()

    assert "An error occurred: boom" in captured.out


def test_process_audio_segments_writes_json_output_and_cleans_temp_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input, "TMP_DIR", f"{tmp_path}{os.sep}")
    monkeypatch.setattr(process_input.whisper, "load_audio", lambda file_path: file_path)
    monkeypatch.setattr(
        process_input.whisper,
        "transcribe",
        lambda model, audio, language=None: {"segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}]},
    )

    output_template = str(tmp_path / "result_{}.json")

    process_input.process_audio_segments(FakeInputAudio(), [(0, 1000)], "en", {"name": "tiny"}, output_template)

    output_file = tmp_path / "result_000000_000001.json"
    assert output_file.exists()
    assert json.loads(output_file.read_text(encoding="utf-8")) == {
        "segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}]
    }
    assert not (tmp_path / "temp_segment_1.mp3").exists()


def test_process_audio_segments_wraps_transcription_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input, "TMP_DIR", f"{tmp_path}{os.sep}")
    monkeypatch.setattr(process_input.whisper, "load_audio", lambda file_path: file_path)

    def raise_transcription_error(_model, _audio, language=None):
        raise RuntimeError("transcription failed")

    monkeypatch.setattr(process_input.whisper, "transcribe", raise_transcription_error)

    with pytest.raises(RuntimeError, match="audio segment #1"):
        process_input.process_audio_segments(
            FakeInputAudio(),
            [(0, 1000)],
            "en",
            {"name": "tiny"},
            str(tmp_path / "result_{}.json"),
        )
