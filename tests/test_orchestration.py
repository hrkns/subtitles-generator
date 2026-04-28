import os
import runpy
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import generate_output
import process_input
from execution_args import execution_args


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeAudio:
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms

    def __len__(self):
        return self.duration_ms


def test_execution_args_parses_cli_flags(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "subtitle-generator",
            "--input",
            "input.mp3",
            "--output",
            "output.srt",
            "--checkpoints",
            "30s",
            "--language",
            "es",
            "--merge",
        ],
    )

    args = execution_args()

    assert args.input == "input.mp3"
    assert args.output == "output.srt"
    assert args.checkpoints == "30s"
    assert args.language == "es"
    assert args.merge is True


def test_process_input_requires_an_input_path():
    args = SimpleNamespace(checkpoints=None, segments=None, input=None, language=None)

    try:
        process_input.process_input(args)
        assert False, "Expected ValueError for missing input path"
    except ValueError as exc:
        assert "Input file path is required" in str(exc)


def test_process_input_rejects_conflicting_checkpoints_and_segments():
    args = SimpleNamespace(checkpoints="30s", segments="00:01-00:02", input="input.mp3", language=None)

    try:
        process_input.process_input(args)
        assert False, "Expected ValueError for conflicting checkpoints and segments"
    except ValueError as exc:
        assert "Cannot specify both checkpoints and segments simultaneously" in str(exc)


def test_process_input_extracts_video_audio_and_processes_checkpoint_segments(tmp_path, monkeypatch):
    temp_dir = tmp_path / "tmp"
    fake_audio = FakeAudio(120000)
    calls = {}

    monkeypatch.setattr(process_input, "TMP_DIR", f"{temp_dir}{os.sep}")
    monkeypatch.setattr(process_input, "is_video_file", lambda path: True)
    monkeypatch.setattr(process_input, "extract_audio", lambda src, dst: calls.setdefault("extract_audio", (src, dst)))

    def fake_validate(file_path):
        calls["validate_audio_file"] = file_path
        return fake_audio

    def fake_generate_segments(checkpoints, total_duration_ms):
        calls["generate_segments"] = (checkpoints, total_duration_ms)
        return [(0, 60000), (60000, 120000)]

    def fake_process_audio_segments(input_audio, segments, language, model, template):
        calls["process_audio_segments"] = (input_audio, segments, language, model, template)

    monkeypatch.setattr(process_input, "validate_audio_file", fake_validate)
    monkeypatch.setattr(process_input, "generate_segments_from_checkpoints", fake_generate_segments)
    monkeypatch.setattr(process_input, "process_audio_segments", fake_process_audio_segments)
    monkeypatch.setattr(process_input.whisper, "load_model", lambda name: {"name": name})

    args = SimpleNamespace(checkpoints="1m", segments=None, input="clip.mp4", language="es")

    process_input.process_input(args)

    expected_audio_path = f"{temp_dir}{os.sep}input_audio.mp3"
    assert calls["extract_audio"] == ("clip.mp4", expected_audio_path)
    assert calls["validate_audio_file"] == expected_audio_path
    assert calls["generate_segments"] == ("1m", 120000)
    assert calls["process_audio_segments"] == (
        fake_audio,
        [(0, 60000), (60000, 120000)],
        "es",
        {"name": "tiny"},
        f"{temp_dir}{os.sep}speech_recognition_result_segment_{{}}.json",
    )
    assert temp_dir.is_dir()


def test_process_input_uses_full_audio_duration_when_no_ranges_are_provided(tmp_path, monkeypatch):
    temp_dir = tmp_path / "tmp"
    fake_audio = FakeAudio(42000)
    calls = {}

    monkeypatch.setattr(process_input, "TMP_DIR", f"{temp_dir}{os.sep}")
    monkeypatch.setattr(process_input, "is_video_file", lambda path: False)
    monkeypatch.setattr(process_input, "validate_audio_file", lambda path: fake_audio)
    monkeypatch.setattr(process_input.whisper, "load_model", lambda name: {"name": name})

    def fake_process_audio_segments(input_audio, segments, language, model, template):
        calls["process_audio_segments"] = (input_audio, segments, language, model, template)

    monkeypatch.setattr(process_input, "process_audio_segments", fake_process_audio_segments)

    args = SimpleNamespace(checkpoints=None, segments=None, input="clip.mp3", language=None)

    process_input.process_input(args)

    assert calls["process_audio_segments"] == (
        fake_audio,
        [(0, 42000)],
        "en",
        {"name": "tiny"},
        f"{temp_dir}{os.sep}speech_recognition_result_segment_{{}}.json",
    )


def test_process_input_routes_explicit_segments_to_segment_parser(tmp_path, monkeypatch):
    temp_dir = tmp_path / "tmp"
    fake_audio = FakeAudio(75000)
    calls = {}

    monkeypatch.setattr(process_input, "TMP_DIR", f"{temp_dir}{os.sep}")
    monkeypatch.setattr(process_input, "is_video_file", lambda path: False)
    monkeypatch.setattr(process_input, "validate_audio_file", lambda path: fake_audio)
    monkeypatch.setattr(process_input.whisper, "load_model", lambda name: {"name": name})
    monkeypatch.setattr(process_input, "parse_segments", lambda segments, total: calls.setdefault("parse_segments", (segments, total)) or [(1000, 2000)])

    def fake_process_audio_segments(input_audio, segments, language, model, template):
        calls["process_audio_segments"] = (input_audio, segments, language, model, template)

    monkeypatch.setattr(process_input, "process_audio_segments", fake_process_audio_segments)

    args = SimpleNamespace(checkpoints=None, segments="00:01-00:02", input="clip.mp3", language="fr")

    process_input.process_input(args)

    assert calls["parse_segments"] == ("00:01-00:02", 75000)
    assert calls["process_audio_segments"][2] == "fr"


def test_generate_output_resolves_default_output_path_and_forwards_merge(monkeypatch):
    calls = {}

    def fake_validate_output(path):
        calls["validate_output"] = path
        return "resolved-output.srt"

    def fake_process_directory(output_path, merge_subtitles=False):
        calls["process_directory"] = (output_path, merge_subtitles)

    monkeypatch.setattr(generate_output, "validate_output", fake_validate_output)
    monkeypatch.setattr(generate_output, "process_directory", fake_process_directory)

    args = SimpleNamespace(input="C:/media/input.mp3", output=None, merge=True)

    generate_output.generate_output(args)

    assert calls["validate_output"] == "C:/media"
    assert calls["process_directory"] == ("resolved-output.srt", True)


def test_main_executes_pipeline_and_cleans_temporary_directory(tmp_path, monkeypatch):
    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    events = []
    args = SimpleNamespace(version=False)

    fake_config = types.ModuleType("config")
    fake_config.TMP_DIR = str(temp_dir)

    fake_modules = types.ModuleType("modules")

    class FakeChronometer:
        def start(self):
            events.append("start")

        def stop(self):
            events.append("stop")

        def print_duration(self):
            events.append("print_duration")

    fake_modules.Chronometer = FakeChronometer
    fake_modules.execution_args = lambda: args

    fake_process_input_module = types.ModuleType("process_input")
    fake_process_input_module.process_input = lambda received_args: events.append(("process_input", received_args))

    fake_generate_output_module = types.ModuleType("generate_output")
    fake_generate_output_module.generate_output = lambda received_args: events.append(("generate_output", received_args))

    monkeypatch.setitem(sys.modules, "config", fake_config)
    monkeypatch.setitem(sys.modules, "modules", fake_modules)
    monkeypatch.setitem(sys.modules, "process_input", fake_process_input_module)
    monkeypatch.setitem(sys.modules, "generate_output", fake_generate_output_module)

    runpy.run_path(str(REPO_ROOT / "main.py"), run_name="__main__")

    assert events[0] == "start"
    assert ("process_input", args) in events
    assert ("generate_output", args) in events
    assert "stop" in events
    assert "print_duration" in events
    assert not temp_dir.exists()
