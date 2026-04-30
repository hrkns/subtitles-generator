import pytest

import gui


class DummyEvent:
    def __init__(self):
        self.ignored = False

    def ignore(self):
        self.ignored = True


class FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines) + [""]
        self.closed = False

    def readline(self):
        return self._lines.pop(0)

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, lines=None, return_code=0):
        self.stdout = FakeStdout(lines or [])
        self.return_code = return_code
        self.terminated = False

    def wait(self):
        return self.return_code

    def poll(self):
        return None if not self.terminated else self.return_code

    def terminate(self):
        self.terminated = True


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self.callbacks):
            callback(*args, **kwargs)


class FakeThread:
    def __init__(self, target):
        self.target = target
        self.started = False
        self.joined = False

    def start(self):
        self.started = True

    def join(self):
        self.joined = True


class FakeWorkerForGui:
    def __init__(self, command):
        self.command = command
        self.output = FakeSignal()
        self.finished = FakeSignal()
        self.stopped = False

    def run(self):
        return None

    def stop(self):
        self.stopped = True

    def is_running(self):
        return False


def build_app_config(**overrides):
    app_config = {
        "last_input_path": "",
        "last_output_path": "",
        "preferred_cleaning_mode": None,
        "auto_apply_cleaning_mode": False,
        "basic_strategy_settings": {
            "high_pass_cutoff_hz": 120,
            "low_pass_cutoff_hz": 7600,
            "apply_dynamic_range_compression": True,
            "apply_normalization": True,
        },
        "speechbrain_strategy_settings": {
            "model_source": "speechbrain/metricgan-plus-voicebank",
            "validate_runtime_before_launch": True,
        },
    }
    app_config.update(overrides)
    return app_config


def create_widget(monkeypatch, app_config=None):
    fake_app_config = build_app_config(**(app_config or {}))
    updates = []

    def fake_update_app_config(app_config_updates):
        fake_app_config.update(app_config_updates)
        updates.append(app_config_updates)
        return fake_app_config.copy()

    monkeypatch.setattr(gui, "load_app_config", lambda: fake_app_config.copy())
    monkeypatch.setattr(gui, "update_app_config", fake_update_app_config)
    monkeypatch.setattr(gui, "is_speechbrain_dependency_available", lambda: False)

    return gui.SubtitlesGeneratorGUI(), updates


def test_worker_run_emits_output_and_finished(monkeypatch):
    fake_process = FakeProcess(lines=["line one\n", "line two\n"], return_code=0)
    monkeypatch.setattr(gui.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    worker = gui.Worker(["python", "main.py"])
    output_lines = []
    finished = []
    worker.output.connect(output_lines.append)
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert output_lines == ["line one\n", "line two\n"]
    assert finished == [True]
    assert fake_process.stdout.closed is True


def test_worker_run_raises_for_non_zero_exit(monkeypatch):
    fake_process = FakeProcess(return_code=1)
    monkeypatch.setattr(gui.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    worker = gui.Worker(["python", "main.py"])

    with pytest.raises(gui.subprocess.CalledProcessError):
        worker.run()


def test_worker_stop_terminates_running_process():
    worker = gui.Worker(["python", "main.py"])
    fake_process = FakeProcess()
    worker.process = fake_process

    worker.stop()

    assert fake_process.terminated is True


def test_select_file_updates_selected_input_and_config(monkeypatch):
    widget, updates = create_widget(monkeypatch, {"last_input_path": "/old"})
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("/tmp/input.mp3", ""))

    widget.select_file()

    assert widget.selectedFile == "/tmp/input.mp3"
    assert widget.selectedFileLabel.text == "Selected File: /tmp/input.mp3"
    assert widget.lastInputPath == "/tmp"
    assert updates[-1] == {
        "last_input_path": "/tmp",
        "last_output_path": "",
        "auto_apply_cleaning_mode": False,
    }


def test_select_output_file_appends_extension_and_updates_config(monkeypatch):
    widget, updates = create_widget(monkeypatch, {"last_output_path": "/old"})
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("/tmp/output", ""))

    widget.select_output_file()

    assert widget.outputPath == "/tmp/output.srt"
    assert widget.outputPathLabel.text == "Output File: /tmp/output.srt"
    assert widget.lastOutputPath == "/tmp"
    assert updates[-1] == {
        "last_input_path": "",
        "last_output_path": "/tmp",
        "auto_apply_cleaning_mode": False,
    }


def test_widget_preselects_saved_cleaning_mode_when_enabled(monkeypatch):
    widget, _updates = create_widget(
        monkeypatch,
        {
            "preferred_cleaning_mode": "basic",
            "auto_apply_cleaning_mode": True,
        },
    )

    assert widget.cleaningModeComboBox.currentText() == "basic"
    assert widget.autoApplyCleaningModeCheckBox.isChecked() is True
    assert widget.saveCleaningModeCheckBox.isChecked() is False
    assert widget.cleaningModeStatusLabel.text == "Basic cleaning uses the lightweight built-in preprocessing chain."


def test_widget_defaults_cleaning_mode_to_off_when_saved_value_is_not_preselected(monkeypatch):
    widget, _updates = create_widget(
        monkeypatch,
        {
            "preferred_cleaning_mode": "basic",
            "auto_apply_cleaning_mode": False,
        },
    )

    assert widget.cleaningModeComboBox.currentText() == "off"
    assert widget.autoApplyCleaningModeCheckBox.isChecked() is False
    assert widget.cleaningModeStatusLabel.text == "Off uses the normalized working WAV without additional cleaning."


def test_build_command_uses_preselected_saved_cleaning_mode(monkeypatch):
    widget, _updates = create_widget(
        monkeypatch,
        {
            "preferred_cleaning_mode": "basic",
            "auto_apply_cleaning_mode": True,
        },
    )
    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"

    assert widget.build_command() == [
        gui.sys.executable,
        "main.py",
        "--input",
        "/tmp/input.mp3",
        "--output",
        "/tmp/output.srt",
        "--checkpoints",
        "30s",
        "--cleaning-mode",
        "basic",
    ]


def test_cleaning_mode_status_reports_unavailable_speechbrain(monkeypatch):
    widget, _updates = create_widget(monkeypatch)

    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    assert widget.cleaningModeStatusLabel.text == (
        "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before using this mode."
    )


def test_cleaning_mode_status_reports_runtime_validation_for_available_speechbrain(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.speechbrainDependencyAvailable = True
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    assert widget.cleaningModeStatusLabel.text == (
        "SpeechBrain enhancement dependencies are available. Model readiness will be validated before launch, and the first run may download model assets."
    )


def test_run_script_requires_input_and_output(monkeypatch):
    widget, _updates = create_widget(monkeypatch)

    widget.run_script()

    assert widget.logTextEdit.lines == ["No input or output file selected."]
    assert widget.btnRunScript.disabled is False


def test_run_script_starts_worker_and_disables_controls(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"
    widget.cleaningModeComboBox.setCurrentText("basic")
    widget.saveCleaningModeCheckBox.setChecked(True)
    widget.autoApplyCleaningModeCheckBox.setChecked(True)

    created = {}

    def fake_worker_factory(command):
        worker = FakeWorkerForGui(command)
        created["worker"] = worker
        return worker

    def fake_thread_factory(target):
        thread = FakeThread(target)
        created["thread"] = thread
        return thread

    monkeypatch.setattr(gui, "Worker", fake_worker_factory)
    monkeypatch.setattr(gui.threading, "Thread", fake_thread_factory)

    widget.run_script()

    assert widget.logTextEdit.lines == ["Running script..."]
    assert widget.btnRunScript.disabled is True
    assert widget.btnSelectFile.disabled is True
    assert widget.btnSelectOutput.disabled is True
    assert widget.btnCancelScript.visible is True
    assert updates[-2] == {
        "last_input_path": "",
        "last_output_path": "",
        "auto_apply_cleaning_mode": True,
    }
    assert updates[-1] == {
        "preferred_cleaning_mode": "basic",
        "auto_apply_cleaning_mode": True,
    }
    assert created["worker"].command == [
        gui.sys.executable,
        "main.py",
        "--input",
        "/tmp/input.mp3",
        "--output",
        "/tmp/output.srt",
        "--checkpoints",
        "30s",
        "--cleaning-mode",
        "basic",
    ]
    assert created["thread"].started is True


def test_run_script_blocks_unavailable_speechbrain_before_execution(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    widget.run_script()

    assert widget.logTextEdit.lines == [
        "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before running with this mode."
    ]
    assert not hasattr(widget, "worker")
    assert widget.btnRunScript.disabled is False


def test_run_script_blocks_speechbrain_when_runtime_validation_fails(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.speechbrainDependencyAvailable = True
    monkeypatch.setattr(
        gui,
        "validate_speechbrain_runtime_ready",
        lambda: (_ for _ in ()).throw(RuntimeError("SpeechBrain enhancement is unavailable: model download failed")),
    )

    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    widget.run_script()

    assert widget.logTextEdit.lines == [
        "Validating SpeechBrain enhancement availability...",
        "SpeechBrain enhancement is unavailable: model download failed",
    ]
    assert not hasattr(widget, "worker")
    assert widget.btnRunScript.disabled is False


def test_run_script_validates_speechbrain_then_starts_worker(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.speechbrainDependencyAvailable = True

    created = {}

    def fake_worker_factory(command):
        worker = FakeWorkerForGui(command)
        created["worker"] = worker
        return worker

    def fake_thread_factory(target):
        thread = FakeThread(target)
        created["thread"] = thread
        return thread

    monkeypatch.setattr(gui, "validate_speechbrain_runtime_ready", lambda: None)
    monkeypatch.setattr(gui, "Worker", fake_worker_factory)
    monkeypatch.setattr(gui.threading, "Thread", fake_thread_factory)

    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    widget.run_script()

    assert widget.logTextEdit.lines == [
        "Validating SpeechBrain enhancement availability...",
        "Running script...",
    ]
    assert created["worker"].command == [
        gui.sys.executable,
        "main.py",
        "--input",
        "/tmp/input.mp3",
        "--output",
        "/tmp/output.srt",
        "--checkpoints",
        "30s",
        "--cleaning-mode",
        "speechbrain",
    ]
    assert created["thread"].started is True


def test_cancel_script_stops_worker_and_restores_controls(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.worker = FakeWorkerForGui([])
    widget.btnRunScript.setDisabled(True)
    widget.btnSelectFile.setDisabled(True)
    widget.btnSelectOutput.setDisabled(True)
    widget.btnCancelScript.show()

    widget.cancel_script()

    assert widget.worker.stopped is True
    assert widget.btnRunScript.disabled is False
    assert widget.btnSelectFile.disabled is False
    assert widget.btnSelectOutput.disabled is False
    assert widget.btnCancelScript.visible is False


def test_close_event_ignores_when_user_declines_running_process(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    worker = FakeWorkerForGui([])
    worker.is_running = lambda: True
    thread = FakeThread(None)
    widget.worker = worker
    widget.thread = thread
    event = DummyEvent()

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args, **kwargs: gui.QMessageBox.No)

    widget.closeEvent(event)

    assert event.ignored is True
    assert worker.stopped is False
    assert thread.joined is False
    assert updates == []


def test_close_event_stops_running_process_and_persists_preferences(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    worker = FakeWorkerForGui([])
    worker.is_running = lambda: True
    thread = FakeThread(None)
    widget.worker = worker
    widget.thread = thread
    widget.autoApplyCleaningModeCheckBox.setChecked(True)
    event = DummyEvent()

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args, **kwargs: gui.QMessageBox.Yes)

    widget.closeEvent(event)

    assert event.ignored is False
    assert worker.stopped is True
    assert thread.joined is True
    assert updates[-1] == {
        "last_input_path": "",
        "last_output_path": "",
        "auto_apply_cleaning_mode": True,
    }