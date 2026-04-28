import os
import runpy
from types import SimpleNamespace

import pytest

import config
import generate_output as generate_output_module
import modules
import process_input as process_input_module
from execution_args import execution_args


class FakeAudio:
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms

    def __len__(self):
        return self.duration_ms


def test_execution_args_parses_runtime_flags(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input",
            "input.mp3",
            "--output",
            "output.srt",
            "--checkpoints",
            "5m",
            "--language",
            "es",
            "--merge",
        ],
    )

    args = execution_args()

    assert args.input == "input.mp3"
    assert args.output == "output.srt"
    assert args.checkpoints == "5m"
    assert args.language == "es"
    assert args.merge is True
    assert args.version is False


def test_execution_args_parses_version_flag(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--version"])

    args = execution_args()

    assert args.version is True
    assert args.input is None


def test_process_input_uses_checkpoint_flow_for_audio_input(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp"
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_dir}{os.sep}")

    calls = {}
    fake_audio = FakeAudio(65000)
    expected_segments = [(0, 30000), (30000, 65000)]

    monkeypatch.setattr(process_input_module, "is_video_file", lambda input_path: False)

    def fake_validate_audio_file(file_path):
        calls["validate_audio_file"] = file_path
        return fake_audio

    def fake_generate_segments(checkpoints, total_duration_ms):
        calls["generate_segments"] = (checkpoints, total_duration_ms)
        return expected_segments

    def fail_parse_segments(*_args, **_kwargs):
        raise AssertionError("parse_segments should not be used when checkpoints are provided")

    def fake_load_model(model_name):
        calls["load_model"] = model_name
        return "fake-model"

    def fake_process_audio_segments(input_audio, segments_to_process, audio_language, speech_to_text_model, output_json_template):
        calls["process_audio_segments"] = (
            input_audio,
            segments_to_process,
            audio_language,
            speech_to_text_model,
            output_json_template,
        )

    monkeypatch.setattr(process_input_module, "validate_audio_file", fake_validate_audio_file)
    monkeypatch.setattr(process_input_module, "generate_segments_from_checkpoints", fake_generate_segments)
    monkeypatch.setattr(process_input_module, "parse_segments", fail_parse_segments)
    monkeypatch.setattr(process_input_module.whisper, "load_model", fake_load_model)
    monkeypatch.setattr(process_input_module, "process_audio_segments", fake_process_audio_segments)

    args = SimpleNamespace(input="input.mp3", checkpoints="30s", segments=None, language=None)

    process_input_module.process_input(args)

    assert tmp_dir.exists()
    assert calls["validate_audio_file"] == "input.mp3"
    assert calls["generate_segments"] == ("30s", 65000)
    assert calls["load_model"] == "tiny"
    assert calls["process_audio_segments"] == (
        fake_audio,
        expected_segments,
        "en",
        "fake-model",
        f"{process_input_module.TMP_DIR}speech_recognition_result_segment_{{}}.json",
    )


def test_process_input_uses_video_extraction_and_default_full_range(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp"
    monkeypatch.setattr(process_input_module, "TMP_DIR", f"{tmp_dir}{os.sep}")

    calls = {}
    fake_audio = FakeAudio(42000)

    monkeypatch.setattr(process_input_module, "is_video_file", lambda input_path: True)

    def fake_extract_audio(video_path, audio_path):
        calls["extract_audio"] = (video_path, audio_path)

    def fake_validate_audio_file(file_path):
        calls["validate_audio_file"] = file_path
        return fake_audio

    def fail_generate_segments(*_args, **_kwargs):
        raise AssertionError("generate_segments_from_checkpoints should not be used without checkpoints")

    def fail_parse_segments(*_args, **_kwargs):
        raise AssertionError("parse_segments should not be used without segments")

    def fake_process_audio_segments(input_audio, segments_to_process, audio_language, speech_to_text_model, output_json_template):
        calls["process_audio_segments"] = (
            input_audio,
            segments_to_process,
            audio_language,
            speech_to_text_model,
            output_json_template,
        )

    monkeypatch.setattr(process_input_module, "extract_audio", fake_extract_audio)
    monkeypatch.setattr(process_input_module, "validate_audio_file", fake_validate_audio_file)
    monkeypatch.setattr(process_input_module, "generate_segments_from_checkpoints", fail_generate_segments)
    monkeypatch.setattr(process_input_module, "parse_segments", fail_parse_segments)
    monkeypatch.setattr(process_input_module.whisper, "load_model", lambda model_name: "fake-model")
    monkeypatch.setattr(process_input_module, "process_audio_segments", fake_process_audio_segments)

    args = SimpleNamespace(input="input.mp4", checkpoints=None, segments=None, language="es")

    process_input_module.process_input(args)

    expected_audio_path = f"{process_input_module.TMP_DIR}input_audio.mp3"
    assert calls["extract_audio"] == ("input.mp4", expected_audio_path)
    assert calls["validate_audio_file"] == expected_audio_path
    assert calls["process_audio_segments"] == (
        fake_audio,
        [(0, 42000)],
        "es",
        "fake-model",
        f"{process_input_module.TMP_DIR}speech_recognition_result_segment_{{}}.json",
    )


def test_process_input_uses_explicit_segments(monkeypatch):
    calls = {}
    fake_audio = FakeAudio(99000)
    expected_segments = [(1000, 5000)]

    monkeypatch.setattr(process_input_module, "is_video_file", lambda input_path: False)
    monkeypatch.setattr(process_input_module, "validate_audio_file", lambda file_path: fake_audio)
    monkeypatch.setattr(
        process_input_module,
        "generate_segments_from_checkpoints",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("checkpoint flow should not run")),
    )

    def fake_parse_segments(segments, total_duration_ms):
        calls["parse_segments"] = (segments, total_duration_ms)
        return expected_segments

    def fake_process_audio_segments(input_audio, segments_to_process, audio_language, speech_to_text_model, output_json_template):
        calls["process_audio_segments"] = (segments_to_process, audio_language)

    monkeypatch.setattr(process_input_module, "parse_segments", fake_parse_segments)
    monkeypatch.setattr(process_input_module.whisper, "load_model", lambda model_name: "fake-model")
    monkeypatch.setattr(process_input_module, "process_audio_segments", fake_process_audio_segments)

    args = SimpleNamespace(input="input.mp3", checkpoints=None, segments="00:01-00:05", language=None)

    process_input_module.process_input(args)

    assert calls["parse_segments"] == ("00:01-00:05", 99000)
    assert calls["process_audio_segments"] == (expected_segments, "en")


def test_process_input_rejects_missing_input_path():
    args = SimpleNamespace(input=None, checkpoints=None, segments=None, language=None)

    with pytest.raises(ValueError, match="Input file path is required"):
        process_input_module.process_input(args)


def test_process_input_rejects_checkpoints_and_segments_together():
    args = SimpleNamespace(input="input.mp3", checkpoints="30s", segments="00:01-00:05", language=None)

    with pytest.raises(ValueError, match="Cannot specify both checkpoints and segments"):
        process_input_module.process_input(args)


def test_generate_output_uses_input_directory_when_output_is_missing(monkeypatch):
    calls = {}

    def fake_validate_output(path):
        calls["validate_output"] = path
        return "resolved-output.srt"

    def fake_process_directory(output_path, merge_subtitles):
        calls["process_directory"] = (output_path, merge_subtitles)

    monkeypatch.setattr(generate_output_module, "validate_output", fake_validate_output)
    monkeypatch.setattr(generate_output_module, "process_directory", fake_process_directory)

    args = SimpleNamespace(input=os.path.join("folder", "input.mp3"), output=None, merge=True)

    generate_output_module.generate_output(args)

    assert calls["validate_output"] == "folder"
    assert calls["process_directory"] == ("resolved-output.srt", True)


def test_generate_output_uses_explicit_output_path(monkeypatch):
    calls = {}

    def fake_validate_output(path):
        calls["validate_output"] = path
        return path

    def fake_process_directory(output_path, merge_subtitles):
        calls["process_directory"] = (output_path, merge_subtitles)

    monkeypatch.setattr(generate_output_module, "validate_output", fake_validate_output)
    monkeypatch.setattr(generate_output_module, "process_directory", fake_process_directory)

    args = SimpleNamespace(input="input.mp3", output="custom-output.srt", merge=False)

    generate_output_module.generate_output(args)

    assert calls["validate_output"] == "custom-output.srt"
    assert calls["process_directory"] == ("custom-output.srt", False)


def test_main_runs_pipeline_and_cleans_tmp_dir(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp"
    calls = []

    class FakeChronometer:
        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

        def print_duration(self):
            calls.append("print_duration")

    monkeypatch.setattr(config, "TMP_DIR", f"{tmp_dir}{os.sep}")
    monkeypatch.setattr(modules, "Chronometer", FakeChronometer)

    args = SimpleNamespace(version=False)
    monkeypatch.setattr(modules, "execution_args", lambda: args)
    monkeypatch.setattr(process_input_module, "process_input", lambda received_args: calls.append(("process_input", received_args)))
    monkeypatch.setattr(generate_output_module, "generate_output", lambda received_args: calls.append(("generate_output", received_args)))

    tmp_dir.mkdir()
    runpy.run_module("main", run_name="__main__")

    assert not tmp_dir.exists()
    assert calls == [
        "start",
        ("process_input", args),
        ("generate_output", args),
        "stop",
        "print_duration",
    ]


def test_main_version_mode_skips_pipeline(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp"
    calls = []

    class FakeChronometer:
        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

        def print_duration(self):
            calls.append("print_duration")

    monkeypatch.setattr(config, "TMP_DIR", f"{tmp_dir}{os.sep}")
    monkeypatch.setattr(modules, "Chronometer", FakeChronometer)

    args = SimpleNamespace(version=True)
    monkeypatch.setattr(modules, "execution_args", lambda: args)
    monkeypatch.setattr(
        process_input_module,
        "process_input",
        lambda received_args: (_ for _ in ()).throw(AssertionError("process_input should not run in version mode")),
    )
    monkeypatch.setattr(
        generate_output_module,
        "generate_output",
        lambda received_args: (_ for _ in ()).throw(AssertionError("generate_output should not run in version mode")),
    )

    runpy.run_module("main", run_name="__main__")

    assert calls == ["start", "stop", "print_duration"]
