import logging

import pytest

import gui


BASIC_CLEANING_STATUS = (
    "Basic cleaning uses the lightweight built-in preprocessing chain.\n"
    "Audio cleanup performance is still unstable and may vary depending on the platform where it is executed."
)

SPEECHBRAIN_UNAVAILABLE_STATUS = (
    "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before using this mode.\n"
    "Audio cleanup performance is still unstable and may vary depending on the platform where it is executed."
)

SPEECHBRAIN_AVAILABLE_STATUS = (
    "SpeechBrain enhancement dependencies are available. Model readiness will be validated before launch, and the first run may download model assets.\n"
    "Audio cleanup performance is still unstable and may vary depending on the platform where it is executed."
)


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


class FakeQThread:
    def __init__(self, *_args, wait_results=None, **_kwargs):
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.started_called = False
        self.quit_called = False
        self.waited = False
        self.wait_timeouts = []
        self.wait_results = list(wait_results) if wait_results is not None else [True]
        self.request_interruption_called = False
        self.terminate_called = False
        self.deleted = False

    def start(self):
        self.started_called = True

    def requestInterruption(self):
        self.request_interruption_called = True

    def quit(self):
        self.quit_called = True
        self.finished.emit()

    def wait(self, timeout=None):
        self.waited = True
        self.wait_timeouts.append(timeout)
        if self.wait_results:
            return self.wait_results.pop(0)
        return True

    def terminate(self):
        self.terminate_called = True

    def deleteLater(self):
        self.deleted = True


class FakeWorkerForGui:
    def __init__(self, command):
        self.command = command
        self.output = FakeSignal()
        self.finished = FakeSignal()
        self.stopped = False
        self.thread = None
        self.deleted = False

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        return None

    def deleteLater(self):
        self.deleted = True

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


def test_worker_run_reports_non_zero_exit_and_finishes(monkeypatch):
    fake_process = FakeProcess(return_code=1)
    monkeypatch.setattr(gui.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    worker = gui.Worker(["python", "main.py"])
    output_lines = []
    finished = []
    worker.output.connect(output_lines.append)
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert len(output_lines) == 1
    assert "Script execution failed:" in output_lines[0]
    assert "returned non-zero exit status 1" in output_lines[0]
    assert finished == [True]


def test_worker_run_reports_startup_errors_and_finishes(monkeypatch):
    monkeypatch.setattr(
        gui.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("python executable missing")),
    )

    worker = gui.Worker(["python", "main.py"])
    output_lines = []
    finished = []
    worker.output.connect(output_lines.append)
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert output_lines == ["Script execution failed: python executable missing"]
    assert finished == [True]


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


def test_select_file_uses_platform_dirname_for_last_input_path(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    selected_path = r"C:\media\input.mp3"
    dirname_calls = []

    def fake_dirname(file_name):
        dirname_calls.append(file_name)
        return r"C:\media"

    monkeypatch.setattr(gui.os.path, "dirname", fake_dirname)
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *args, **kwargs: (selected_path, ""))

    widget.select_file()

    assert dirname_calls == [selected_path]
    assert widget.lastInputPath == r"C:\media"
    assert updates[-1]["last_input_path"] == r"C:\media"


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


def test_select_output_file_uses_platform_dirname_for_last_output_path(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    selected_path = r"C:\media\output"
    dirname_calls = []

    def fake_dirname(file_name):
        dirname_calls.append(file_name)
        return r"C:\media"

    monkeypatch.setattr(gui.os.path, "dirname", fake_dirname)
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (selected_path, ""))

    widget.select_output_file()

    assert dirname_calls == [r"C:\media\output.srt"]
    assert widget.lastOutputPath == r"C:\media"
    assert updates[-1]["last_output_path"] == r"C:\media"


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
    assert widget.cleaningModeStatusLabel.text == BASIC_CLEANING_STATUS


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


def test_speechbrain_dependency_available_returns_false_for_missing_module(monkeypatch):
    monkeypatch.setattr(
        gui.importlib,
        "import_module",
        lambda module_name: (_ for _ in ()).throw(ModuleNotFoundError(module_name)),
    )

    assert gui.is_speechbrain_dependency_available() is False


def test_speechbrain_dependency_available_defers_runtime_import_errors_to_validation(monkeypatch, caplog):
    monkeypatch.setattr(
        gui.importlib,
        "import_module",
        lambda module_name: (_ for _ in ()).throw(RuntimeError("torchaudio C++ extension mismatch")),
    )

    with caplog.at_level(logging.WARNING):
        assert gui.is_speechbrain_dependency_available() is True

    assert "runtime validation will report details" in caplog.text
    assert "torchaudio C++ extension mismatch" in caplog.text


def test_cleaning_mode_status_reports_unavailable_speechbrain(monkeypatch):
    widget, _updates = create_widget(monkeypatch)

    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    assert widget.cleaningModeStatusLabel.text == SPEECHBRAIN_UNAVAILABLE_STATUS


def test_cleaning_mode_status_reports_runtime_validation_for_available_speechbrain(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.speechbrainDependencyAvailable = True
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    assert widget.cleaningModeStatusLabel.text == SPEECHBRAIN_AVAILABLE_STATUS


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

    def fake_thread_factory(*_args, **_kwargs):
        thread = FakeQThread()
        created["thread"] = thread
        return thread

    monkeypatch.setattr(gui, "Worker", fake_worker_factory)
    monkeypatch.setattr(gui, "QThread", fake_thread_factory)

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
    assert created["worker"].thread is created["thread"]
    assert created["thread"].started_called is True
    assert created["thread"].started.callbacks == [created["worker"].run]


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
    created = {}

    def fake_thread_factory(*_args, **_kwargs):
        thread = FakeQThread()
        created["validation_thread"] = thread
        return thread

    monkeypatch.setattr(
        gui,
        "validate_speechbrain_runtime_ready",
        lambda: (_ for _ in ()).throw(RuntimeError("SpeechBrain enhancement is unavailable: model download failed")),
    )
    monkeypatch.setattr(gui, "QThread", fake_thread_factory)

    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    widget.run_script()

    assert widget.logTextEdit.lines == ["Validating SpeechBrain enhancement availability..."]
    assert widget.speechbrainValidationWorker.thread is created["validation_thread"]
    assert created["validation_thread"].started.callbacks == [widget.speechbrainValidationWorker.run]
    assert created["validation_thread"].started_called is True
    assert widget.btnRunScript.disabled is True

    created["validation_thread"].started.emit()

    assert widget.logTextEdit.lines == [
        "Validating SpeechBrain enhancement availability...",
        "SpeechBrain enhancement is unavailable: model download failed",
    ]
    assert not hasattr(widget, "worker")
    assert widget.btnRunScript.disabled is False


def test_run_script_validates_speechbrain_then_starts_worker(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.speechbrainDependencyAvailable = True

    created = {"threads": [], "validation_calls": 0}

    def fake_worker_factory(command):
        worker = FakeWorkerForGui(command)
        created["worker"] = worker
        return worker

    def fake_thread_factory(*_args, **_kwargs):
        thread = FakeQThread()
        created["threads"].append(thread)
        return thread

    def fake_validate_speechbrain_runtime_ready():
        created["validation_calls"] += 1

    monkeypatch.setattr(gui, "validate_speechbrain_runtime_ready", fake_validate_speechbrain_runtime_ready)
    monkeypatch.setattr(gui, "Worker", fake_worker_factory)
    monkeypatch.setattr(gui, "QThread", fake_thread_factory)

    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"
    widget.cleaningModeComboBox.setCurrentText("speechbrain")

    widget.run_script()

    assert widget.logTextEdit.lines == ["Validating SpeechBrain enhancement availability..."]
    assert created["validation_calls"] == 0
    assert created["threads"][0].started_called is True
    assert "worker" not in created

    created["threads"][0].started.emit()

    assert widget.logTextEdit.lines == [
        "Validating SpeechBrain enhancement availability...",
        "SpeechBrain enhancement is ready.",
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
    assert created["validation_calls"] == 1
    assert created["worker"].thread is created["threads"][1]
    assert created["threads"][1].started_called is True


def test_cancel_script_requests_worker_stop_and_waits_for_finished_signal_to_restore_controls(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    widget.worker = FakeWorkerForGui([])
    widget.btnRunScript.setDisabled(True)
    widget.btnSelectFile.setDisabled(True)
    widget.btnSelectOutput.setDisabled(True)
    widget.btnCancelScript.show()

    widget.cancel_script()

    assert widget.worker.stopped is True
    assert widget.btnRunScript.disabled is True
    assert widget.btnSelectFile.disabled is True
    assert widget.btnSelectOutput.disabled is True
    assert widget.btnCancelScript.visible is True

    widget.script_finished()

    assert widget.btnRunScript.disabled is False
    assert widget.btnSelectFile.disabled is False
    assert widget.btnSelectOutput.disabled is False
    assert widget.btnCancelScript.visible is False


def test_close_event_ignores_when_user_declines_running_process(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    worker = FakeWorkerForGui([])
    worker.is_running = lambda: True
    thread = FakeQThread()
    widget.worker = worker
    widget.thread = thread
    event = DummyEvent()

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args, **kwargs: gui.QMessageBox.No)

    widget.closeEvent(event)

    assert event.ignored is True
    assert worker.stopped is False
    assert thread.waited is False
    assert updates == []


def test_close_event_stops_running_process_and_persists_preferences(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    worker = FakeWorkerForGui([])
    worker.is_running = lambda: True
    thread = FakeQThread()
    widget.worker = worker
    widget.thread = thread
    widget.autoApplyCleaningModeCheckBox.setChecked(True)
    event = DummyEvent()

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args, **kwargs: gui.QMessageBox.Yes)

    widget.closeEvent(event)

    assert event.ignored is False
    assert worker.stopped is True
    assert thread.quit_called is True
    assert thread.waited is True
    assert updates[-1] == {
        "last_input_path": "",
        "last_output_path": "",
        "auto_apply_cleaning_mode": True,
    }


def test_close_event_waits_for_running_speechbrain_validation_thread(monkeypatch):
    widget, updates = create_widget(monkeypatch)
    validation_thread = FakeQThread()
    validation_worker = FakeWorkerForGui([])
    widget.speechbrainValidationThread = validation_thread
    widget.speechbrainValidationWorker = validation_worker
    event = DummyEvent()

    widget.closeEvent(event)

    assert event.ignored is False
    assert widget.isClosing is True
    assert validation_thread.request_interruption_called is True
    assert validation_thread.quit_called is True
    assert validation_thread.waited is True
    assert validation_thread.wait_timeouts == [gui.SPEECHBRAIN_VALIDATION_SHUTDOWN_TIMEOUT_MS]
    assert validation_thread.terminate_called is False
    assert widget.speechbrainValidationThread is None
    assert widget.speechbrainValidationWorker is None
    assert updates[-1] == {
        "last_input_path": "",
        "last_output_path": "",
        "auto_apply_cleaning_mode": False,
    }


def test_close_event_terminates_stalled_speechbrain_validation_thread(monkeypatch, caplog):
    widget, _updates = create_widget(monkeypatch)
    validation_thread = FakeQThread(wait_results=[False, True])
    widget.speechbrainValidationThread = validation_thread
    widget.speechbrainValidationWorker = FakeWorkerForGui([])
    event = DummyEvent()

    with caplog.at_level(logging.WARNING):
        widget.closeEvent(event)

    assert validation_thread.request_interruption_called is True
    assert validation_thread.quit_called is True
    assert validation_thread.terminate_called is True
    assert validation_thread.wait_timeouts == [
        gui.SPEECHBRAIN_VALIDATION_SHUTDOWN_TIMEOUT_MS,
        gui.SPEECHBRAIN_VALIDATION_SHUTDOWN_TIMEOUT_MS,
    ]
    assert "terminating validation thread" in caplog.text
    assert widget.speechbrainValidationThread is None
    assert widget.speechbrainValidationWorker is None


def test_speechbrain_validation_success_is_ignored_while_closing(monkeypatch):
    widget, _updates = create_widget(monkeypatch)
    started = []
    widget.isClosing = True
    widget.speechbrainValidationThread = FakeQThread()
    widget.speechbrainValidationWorker = FakeWorkerForGui([])
    monkeypatch.setattr(widget, "start_script_execution", lambda: started.append(True))

    widget.speechbrain_runtime_validation_finished(True, "")

    assert started == []
    assert widget.speechbrainValidationThread is None
    assert widget.speechbrainValidationWorker is None
