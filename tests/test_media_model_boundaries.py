import json
import os
from pathlib import Path

import pytest

import process_input as process_input_module


class FakeAudioSegmentSlice:
    def __init__(self, exported_paths):
        self.exported_paths = exported_paths

    def export(self, file_path, format="mp3"):
        self.exported_paths.append((file_path, format))
        Path(file_path).write_text("temporary audio", encoding="utf-8")


class FakeInputAudio:
    def __init__(self):
        self.segment_requests = []
        self.exported_paths = []

    def __getitem__(self, item):
        self.segment_requests.append((item.start, item.stop))
        return FakeAudioSegmentSlice(self.exported_paths)


def test_validate_audio_file_returns_decoded_mp3(monkeypatch):
    sentinel_audio = object()

    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)
    monkeypatch.setattr(process_input_module.AudioSegment, "from_mp3", lambda file_path: sentinel_audio)

    assert process_input_module.validate_audio_file("input.mp3") is sentinel_audio


def test_validate_audio_file_rejects_missing_files(monkeypatch, caplog):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: False)

    with pytest.raises(SystemExit) as exc_info:
        process_input_module.validate_audio_file("missing.mp3")

    assert exc_info.value.code == 1
    assert "does not exist" in caplog.text


def test_validate_audio_file_rejects_non_mp3_files(monkeypatch, caplog):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)

    with pytest.raises(SystemExit) as exc_info:
        process_input_module.validate_audio_file("input.wav")

    assert exc_info.value.code == 1
    assert "Currently only MP3 is supported" in caplog.text


def test_validate_audio_file_rejects_decode_failures(monkeypatch, caplog):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)

    def fake_from_mp3(file_path):
        raise process_input_module.CouldntDecodeError("decode failed")

    monkeypatch.setattr(process_input_module.AudioSegment, "from_mp3", fake_from_mp3)

    with pytest.raises(SystemExit) as exc_info:
        process_input_module.validate_audio_file("broken.mp3")

    assert exc_info.value.code == 1
    assert "Could not decode audio file" in caplog.text


def test_is_video_file_returns_false_when_file_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: False)

    assert process_input_module.is_video_file("missing.mp4") is False
    assert "File does not exist." in capsys.readouterr().out


def test_is_video_file_detects_video_mime(monkeypatch):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)

    class FakeMagic:
        def __init__(self, mime=True):
            self.mime = mime

        def from_file(self, file_path):
            return "video/mp4"

    monkeypatch.setattr(process_input_module.magic, "Magic", FakeMagic)

    assert process_input_module.is_video_file("video.mp4") is True


def test_is_video_file_detects_non_video_mime(monkeypatch):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)

    class FakeMagic:
        def __init__(self, mime=True):
            self.mime = mime

        def from_file(self, file_path):
            return "audio/mpeg"

    monkeypatch.setattr(process_input_module.magic, "Magic", FakeMagic)

    assert process_input_module.is_video_file("audio.mp3") is False


def test_extract_audio_writes_audio_file(monkeypatch, capsys):
    calls = {}

    class FakeAudioFileClip:
        def __init__(self, video_path):
            calls["video_path"] = video_path

        def write_audiofile(self, audio_path):
            calls["audio_path"] = audio_path

    monkeypatch.setattr(process_input_module, "AudioFileClip", FakeAudioFileClip)

    process_input_module.extract_audio("video.mp4", "audio.mp3")

    assert calls == {"video_path": "video.mp4", "audio_path": "audio.mp3"}
    assert "Audio extracted and saved to audio.mp3" in capsys.readouterr().out


def test_extract_audio_reports_errors(monkeypatch, capsys):
    class FakeAudioFileClip:
        def __init__(self, video_path):
            raise RuntimeError("boom")

    monkeypatch.setattr(process_input_module, "AudioFileClip", FakeAudioFileClip)

    process_input_module.extract_audio("video.mp4", "audio.mp3")

    assert "An error occurred: boom" in capsys.readouterr().out


def test_process_audio_segments_exports_transcribes_and_writes_json(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_path}{os.sep}")

    input_audio = FakeInputAudio()
    loaded_audio_paths = []
    transcribe_calls = []

    def fake_load_audio(file_path):
        loaded_audio_paths.append(file_path)
        return f"loaded:{file_path}"

    def fake_transcribe(model, audio, language=None):
        transcribe_calls.append((model, audio, language))
        return {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}]}

    monkeypatch.setattr(process_input_module.whisper, "load_audio", fake_load_audio)
    monkeypatch.setattr(process_input_module.whisper, "transcribe", fake_transcribe)

    output_json_template = f"{tmp_path}{os.sep}result_{{}}.json"

    process_input_module.process_audio_segments(
        input_audio,
        [(0, 2000), (2000, 4000)],
        "en",
        "fake-model",
        output_json_template,
    )

    temp_audio_1 = f"{process_input_module.TMP_DIR}temp_segment_1.mp3"
    temp_audio_2 = f"{process_input_module.TMP_DIR}temp_segment_2.mp3"
    output_json_1 = tmp_path / "result_000000_000002.json"
    output_json_2 = tmp_path / "result_000002_000004.json"

    assert input_audio.segment_requests == [(0, 2000), (2000, 4000)]
    assert input_audio.exported_paths == [(temp_audio_1, "mp3"), (temp_audio_2, "mp3")]
    assert loaded_audio_paths == [temp_audio_1, temp_audio_2]
    assert transcribe_calls == [
        ("fake-model", f"loaded:{temp_audio_1}", "en"),
        ("fake-model", f"loaded:{temp_audio_2}", "en"),
    ]
    assert json.loads(output_json_1.read_text(encoding="utf-8")) == {
        "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}]
    }
    assert json.loads(output_json_2.read_text(encoding="utf-8")) == {
        "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}]
    }
    assert not Path(temp_audio_1).exists()
    assert not Path(temp_audio_2).exists()


def test_process_audio_segments_wraps_transcription_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_path}{os.sep}")

    input_audio = FakeInputAudio()

    monkeypatch.setattr(process_input_module.whisper, "load_audio", lambda file_path: file_path)

    def fake_transcribe(model, audio, language=None):
        raise Exception("transcription failed")

    monkeypatch.setattr(process_input_module.whisper, "transcribe", fake_transcribe)

    with pytest.raises(RuntimeError, match="audio segment #1: transcription failed"):
        process_input_module.process_audio_segments(
            input_audio,
            [(0, 2000)],
            "en",
            "fake-model",
            f"{tmp_path}{os.sep}result_{{}}.json",
        )

    assert not (tmp_path / "result_000000_000002.json").exists()
