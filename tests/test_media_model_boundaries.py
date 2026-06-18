import json
import logging
import os
import types
from pathlib import Path

import pytest

import process_input as process_input_module


class FakeAudioSegmentSlice:
    def __init__(self, exported_paths):
        self.exported_paths = exported_paths

    def export(self, file_path, format="wav"):
        self.exported_paths.append((file_path, format))
        Path(file_path).write_text("temporary audio", encoding="utf-8")


class FakeInputAudio:
    def __init__(self):
        self.segment_requests = []
        self.exported_paths = []

    def __getitem__(self, item):
        self.segment_requests.append((item.start, item.stop))
        return FakeAudioSegmentSlice(self.exported_paths)


class FakeExportableAudio:
    def __init__(self):
        self.export_calls = []

    def export(self, file_path, format="wav"):
        self.export_calls.append((file_path, format))
        Path(file_path).write_text("normalized audio", encoding="utf-8")


@pytest.mark.parametrize("file_path", ["input.mp3", "input.wav"])
def test_validate_audio_file_returns_decoded_audio(monkeypatch, file_path):
    sentinel_audio = object()

    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)
    monkeypatch.setattr(process_input_module.AudioSegment, "from_file", lambda file_path: sentinel_audio)

    assert process_input_module.validate_audio_file(file_path) is sentinel_audio


def test_validate_audio_file_rejects_missing_files(monkeypatch, caplog):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: False)

    with pytest.raises(SystemExit) as exc_info:
        process_input_module.validate_audio_file("missing.mp3")

    assert exc_info.value.code == 1
    assert "does not exist" in caplog.text


def test_validate_audio_file_rejects_undecodable_files(monkeypatch, caplog):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)

    def fake_from_file(file_path):
        raise Exception("not audio")

    monkeypatch.setattr(process_input_module.AudioSegment, "from_file", fake_from_file)

    with pytest.raises(SystemExit) as exc_info:
        process_input_module.validate_audio_file("input.txt")

    assert exc_info.value.code == 1
    assert "Could not decode audio file" in caplog.text
    assert "not audio" in caplog.text


def test_validate_audio_file_rejects_decode_failures(monkeypatch, caplog):
    monkeypatch.setattr(process_input_module.os.path, "exists", lambda file_path: True)

    def fake_from_mp3(file_path):
        raise process_input_module.CouldntDecodeError("decode failed")

    monkeypatch.setattr(process_input_module.AudioSegment, "from_file", fake_from_mp3)

    with pytest.raises(SystemExit) as exc_info:
        process_input_module.validate_audio_file("broken.mp3")

    assert exc_info.value.code == 1
    assert "Could not decode audio file" in caplog.text
    assert "decode failed" in caplog.text


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


def test_extract_audio_writes_audio_file(monkeypatch, caplog):
    calls = {}

    class FakeAudioFileClip:
        def __init__(self, video_path):
            calls["video_path"] = video_path

        def close(self):
            calls["closed"] = True

        def write_audiofile(self, audio_path):
            calls["audio_path"] = audio_path

    monkeypatch.setattr(process_input_module, "AudioFileClip", FakeAudioFileClip)

    with caplog.at_level(logging.INFO):
        process_input_module.extract_audio("video.mp4", "audio.wav")

    assert calls == {"video_path": "video.mp4", "audio_path": "audio.wav", "closed": True}
    assert "Audio extracted and saved to audio.wav" in caplog.text


def test_extract_audio_logs_and_reraises_errors(monkeypatch, caplog):
    class FakeAudioFileClip:
        def __init__(self, video_path):
            raise RuntimeError("boom")

    monkeypatch.setattr(process_input_module, "AudioFileClip", FakeAudioFileClip)

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="boom"):
        process_input_module.extract_audio("video.mp4", "audio.wav")

    assert "Could not extract audio from 'video.mp4' to 'audio.wav': boom" in caplog.text


def test_prepare_working_audio_normalizes_audio_input_to_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_path}{os.sep}")

    source_audio = FakeExportableAudio()
    normalized_audio = object()
    validate_calls = []

    monkeypatch.setattr(process_input_module, "is_video_file", lambda input_path: False)

    def fake_validate_audio_file(file_path):
        validate_calls.append(file_path)
        if file_path == "input.wav":
            return source_audio
        if file_path == os.path.join(process_input_module.TMP_DIR, process_input_module.WORKING_AUDIO_FILENAME):
            return normalized_audio
        raise AssertionError(f"Unexpected validation path: {file_path}")

    monkeypatch.setattr(process_input_module, "validate_audio_file", fake_validate_audio_file)

    working_audio_path, working_audio = process_input_module.prepare_working_audio("input.wav")

    assert working_audio_path == os.path.join(process_input_module.TMP_DIR, process_input_module.WORKING_AUDIO_FILENAME)
    assert working_audio is normalized_audio
    assert validate_calls == ["input.wav", working_audio_path]
    assert source_audio.export_calls == [(working_audio_path, process_input_module.WORKING_AUDIO_FORMAT)]


def test_prepare_working_audio_extracts_video_to_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_path}{os.sep}")

    calls = {}
    normalized_audio = object()

    monkeypatch.setattr(process_input_module, "is_video_file", lambda input_path: True)

    def fake_extract_audio(video_path, audio_path):
        calls["extract_audio"] = (video_path, audio_path)

    def fake_validate_audio_file(file_path):
        calls["validate_audio_file"] = file_path
        return normalized_audio

    monkeypatch.setattr(process_input_module, "extract_audio", fake_extract_audio)
    monkeypatch.setattr(process_input_module, "validate_audio_file", fake_validate_audio_file)

    working_audio_path, working_audio = process_input_module.prepare_working_audio("input.mp4")

    assert working_audio_path == os.path.join(process_input_module.TMP_DIR, process_input_module.WORKING_AUDIO_FILENAME)
    assert working_audio is normalized_audio
    assert calls == {
        "extract_audio": ("input.mp4", working_audio_path),
        "validate_audio_file": working_audio_path,
    }


def test_resolve_cleaning_mode_defaults_to_off():
    assert process_input_module.resolve_cleaning_mode() == "off"


def test_resolve_cleaning_mode_uses_saved_default_when_no_explicit_value(monkeypatch):
    monkeypatch.setattr(
        process_input_module,
        "load_cleaning_settings",
        lambda: {
            "default_cleaning_mode": "basic",
            "preselect_saved_cleaning_mode": True,
        },
    )

    assert process_input_module.resolve_cleaning_mode() == "basic"


def test_resolve_cleaning_mode_prefers_explicit_value_over_saved_default(monkeypatch):
    monkeypatch.setattr(
        process_input_module,
        "load_cleaning_settings",
        lambda: {
            "default_cleaning_mode": "basic",
            "preselect_saved_cleaning_mode": True,
        },
    )

    assert process_input_module.resolve_cleaning_mode("off") == "off"


def test_resolve_cleaning_mode_ignores_invalid_saved_default(monkeypatch, caplog):
    monkeypatch.setattr(
        process_input_module,
        "load_cleaning_settings",
        lambda: {
            "default_cleaning_mode": "broken",
            "preselect_saved_cleaning_mode": True,
        },
    )

    with caplog.at_level(logging.WARNING):
        assert process_input_module.resolve_cleaning_mode() == "off"

    assert "Ignoring unsupported saved cleaning mode" in caplog.text


def test_resolve_cleaning_mode_rejects_unknown_modes():
    with pytest.raises(ValueError, match="Unsupported cleaning mode 'nope'"):
        process_input_module.resolve_cleaning_mode("nope")


@pytest.mark.parametrize("preselect_saved_cleaning_mode", [False, True])
def test_persist_default_cleaning_mode_saves_requested_mode_without_changing_preselect_setting(
    monkeypatch,
    preselect_saved_cleaning_mode,
):
    calls = {}

    def fake_save_cleaning_settings(default_cleaning_mode, preselect_saved_cleaning_mode=True):
        calls["save_cleaning_settings"] = (default_cleaning_mode, preselect_saved_cleaning_mode)

    monkeypatch.setattr(
        process_input_module,
        "load_cleaning_settings",
        lambda: {
            "default_cleaning_mode": "off",
            "preselect_saved_cleaning_mode": preselect_saved_cleaning_mode,
        },
    )
    monkeypatch.setattr(process_input_module, "save_cleaning_settings", fake_save_cleaning_settings)

    assert process_input_module.persist_default_cleaning_mode("basic") == "basic"
    assert calls["save_cleaning_settings"] == ("basic", preselect_saved_cleaning_mode)


def test_apply_audio_cleaning_off_returns_original_working_audio():
    working_audio = object()

    cleaned_audio_path, cleaned_audio = process_input_module.apply_audio_cleaning(
        "working.wav",
        None,
        working_audio,
    )

    assert cleaned_audio_path == "working.wav"
    assert cleaned_audio is working_audio


def test_apply_audio_cleaning_basic_exports_cleaned_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_path}{os.sep}")

    effect_calls = []
    source_audio = object()
    cleaned_audio_after_effects = FakeExportableAudio()
    cleaned_audio = object()
    expected_output_path = os.path.join(
        process_input_module.TMP_DIR,
        process_input_module.PREPROCESSED_AUDIO_FILENAME_TEMPLATE.format("basic"),
    )

    monkeypatch.setattr(
        process_input_module.audio_effects,
        "high_pass_filter",
        lambda audio, cutoff: effect_calls.append(("high_pass_filter", audio, cutoff)) or cleaned_audio_after_effects,
    )
    monkeypatch.setattr(
        process_input_module.audio_effects,
        "low_pass_filter",
        lambda audio, cutoff: effect_calls.append(("low_pass_filter", audio, cutoff)) or cleaned_audio_after_effects,
    )
    monkeypatch.setattr(
        process_input_module.audio_effects,
        "compress_dynamic_range",
        lambda audio: effect_calls.append(("compress_dynamic_range", audio)) or cleaned_audio_after_effects,
    )
    monkeypatch.setattr(
        process_input_module.audio_effects,
        "normalize",
        lambda audio: effect_calls.append(("normalize", audio)) or cleaned_audio_after_effects,
    )

    def fake_validate_audio_file(file_path):
        if file_path == expected_output_path:
            return cleaned_audio
        raise AssertionError(f"Unexpected validation path: {file_path}")

    monkeypatch.setattr(process_input_module, "validate_audio_file", fake_validate_audio_file)

    cleaned_audio_path, validated_audio = process_input_module.apply_audio_cleaning(
        "working.wav",
        "basic",
        source_audio,
    )

    assert cleaned_audio_path == expected_output_path
    assert validated_audio is cleaned_audio
    assert effect_calls == [
        ("high_pass_filter", source_audio, 120),
        ("low_pass_filter", cleaned_audio_after_effects, 7600),
        ("compress_dynamic_range", cleaned_audio_after_effects),
        ("normalize", cleaned_audio_after_effects),
    ]
    assert cleaned_audio_after_effects.export_calls == [
        (expected_output_path, process_input_module.WORKING_AUDIO_FORMAT)
    ]


def test_load_speechbrain_enhancer_reports_missing_dependency(monkeypatch):
    def fake_import_module(module_name):
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(process_input_module.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="install_speechbrain_dependencies"):
        process_input_module.load_speechbrain_enhancer()


def test_load_speechbrain_enhancer_reports_import_runtime_errors(monkeypatch):
    def fake_import_module(module_name):
        raise RuntimeError("torchaudio C++ extension mismatch")

    monkeypatch.setattr(process_input_module.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="torchaudio C\\+\\+ extension mismatch") as exc_info:
        process_input_module.load_speechbrain_enhancer()

    assert "install_speechbrain_dependencies" not in str(exc_info.value)


def test_load_speechbrain_enhancer_reports_model_load_failure_with_cache_path(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "AUDIO_CACHE_DIR", f"{tmp_path}{os.sep}cache{os.sep}")

    class FakeSpectralMaskEnhancement:
        @staticmethod
        def from_hparams(source, savedir):
            raise RuntimeError("download failed")

    monkeypatch.setattr(
        process_input_module.importlib,
        "import_module",
        lambda module_name: types.SimpleNamespace(SpectralMaskEnhancement=FakeSpectralMaskEnhancement),
    )

    expected_savedir = os.path.join(
        process_input_module.AUDIO_CACHE_DIR,
        process_input_module.SPEECHBRAIN_MODEL_CACHE_DIRNAME,
    )

    with pytest.raises(RuntimeError, match="could not load its enhancement model into") as exc_info:
        process_input_module.load_speechbrain_enhancer()

    assert expected_savedir in str(exc_info.value)
    assert os.path.isdir(expected_savedir)


def test_apply_audio_cleaning_speechbrain_enhances_working_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_path}{os.sep}")
    monkeypatch.setattr(process_input_module, "AUDIO_CACHE_DIR", f"{tmp_path}{os.sep}cache{os.sep}")

    calls = {}
    cleaned_audio = object()
    expected_output_path = os.path.join(
        process_input_module.TMP_DIR,
        process_input_module.PREPROCESSED_AUDIO_FILENAME_TEMPLATE.format("speechbrain"),
    )
    expected_savedir = os.path.join(
        process_input_module.AUDIO_CACHE_DIR,
        process_input_module.SPEECHBRAIN_MODEL_CACHE_DIRNAME,
    )

    class FakeEnhancer:
        def enhance_file(self, input_path, output_path):
            calls["enhance_file"] = (input_path, output_path)
            Path(output_path).write_text("enhanced audio", encoding="utf-8")

    class FakeSpectralMaskEnhancement:
        @staticmethod
        def from_hparams(source, savedir):
            calls["from_hparams"] = (source, savedir)
            return FakeEnhancer()

    monkeypatch.setattr(
        process_input_module.importlib,
        "import_module",
        lambda module_name: types.SimpleNamespace(SpectralMaskEnhancement=FakeSpectralMaskEnhancement),
    )

    def fake_validate_audio_file(file_path):
        if file_path == expected_output_path:
            return cleaned_audio
        raise AssertionError(f"Unexpected validation path: {file_path}")

    monkeypatch.setattr(process_input_module, "validate_audio_file", fake_validate_audio_file)

    cleaned_audio_path, validated_audio = process_input_module.apply_audio_cleaning(
        "working.wav",
        "speechbrain",
    )

    assert cleaned_audio_path == expected_output_path
    assert validated_audio is cleaned_audio
    assert calls["from_hparams"] == (process_input_module.SPEECHBRAIN_MODEL_SOURCE, expected_savedir)
    assert calls["enhance_file"] == ("working.wav", expected_output_path)
    assert Path(expected_output_path).exists()


def test_prepare_transcription_audio_applies_cleaning_after_working_audio_creation(monkeypatch):
    calls = {}
    working_audio = object()
    cleaned_audio = object()

    def fake_prepare_working_audio(input_path):
        calls["prepare_working_audio"] = input_path
        return "working.wav", working_audio

    def fake_apply_audio_cleaning(working_audio_path, cleaning_mode=None, received_audio=None):
        calls["apply_audio_cleaning"] = (working_audio_path, cleaning_mode, received_audio)
        return "cleaned.wav", cleaned_audio

    monkeypatch.setattr(process_input_module, "prepare_working_audio", fake_prepare_working_audio)
    monkeypatch.setattr(process_input_module, "apply_audio_cleaning", fake_apply_audio_cleaning)

    prepared_audio_path, prepared_audio = process_input_module.prepare_transcription_audio("input.wav", "basic")

    assert prepared_audio_path == "cleaned.wav"
    assert prepared_audio is cleaned_audio
    assert calls == {
        "prepare_working_audio": "input.wav",
        "apply_audio_cleaning": ("working.wav", "basic", working_audio),
    }


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

    temp_audio_1 = os.path.join(process_input_module.TMP_DIR, "temp_segment_1.wav")
    temp_audio_2 = os.path.join(process_input_module.TMP_DIR, "temp_segment_2.wav")
    output_json_1 = tmp_path / "result_000000_000002.json"
    output_json_2 = tmp_path / "result_000002_000004.json"

    assert input_audio.segment_requests == [(0, 2000), (2000, 4000)]
    assert input_audio.exported_paths == [(temp_audio_1, "wav"), (temp_audio_2, "wav")]
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
    assert not (tmp_path / "temp_segment_1.wav").exists()
