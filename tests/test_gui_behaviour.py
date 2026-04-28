import pytest

import gui


class DummyCache(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.closed = False

    def close(self):
        self.closed = True


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


def create_widget(monkeypatch, cache=None):
    fake_cache = cache or DummyCache()
    monkeypatch.setattr(gui.shelve, "open", lambda _path: fake_cache)
    return gui.SubtitlesGeneratorGUI(), fake_cache


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


def test_select_file_updates_selected_input_and_cache(monkeypatch):
    widget, cache = create_widget(monkeypatch, DummyCache({"lastInputPath": "/old"}))
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("/tmp/input.mp3", ""))

    widget.select_file()

    assert widget.selectedFile == "/tmp/input.mp3"
    assert widget.selectedFileLabel.text == "Selected File: /tmp/input.mp3"
    assert widget.lastInputPath == "/tmp"
    assert cache["lastInputPath"] == "/tmp"


def test_select_output_file_appends_extension_and_updates_cache(monkeypatch):
    widget, cache = create_widget(monkeypatch, DummyCache({"lastOutputPath": "/old"}))
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("/tmp/output", ""))

    widget.select_output_file()

    assert widget.outputPath == "/tmp/output.srt"
    assert widget.outputPathLabel.text == "Output File: /tmp/output.srt"
    assert widget.lastOutputPath == "/tmp"
    assert cache["lastOutputPath"] == "/tmp"


def test_run_script_requires_input_and_output(monkeypatch):
    widget, _cache = create_widget(monkeypatch)

    widget.run_script()

    assert widget.logTextEdit.lines == ["No input or output file selected."]
    assert widget.btnRunScript.disabled is False


def test_run_script_starts_worker_and_disables_controls(monkeypatch):
    widget, _cache = create_widget(monkeypatch)
    widget.selectedFile = "/tmp/input.mp3"
    widget.outputPath = "/tmp/output.srt"

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
    assert created["worker"].command == [
        "python",
        "main.py",
        "--input",
        "/tmp/input.mp3",
        "--output",
        "/tmp/output.srt",
        "--checkpoints",
        "30s",
    ]
    assert created["thread"].started is True


def test_cancel_script_stops_worker_and_restores_controls(monkeypatch):
    widget, _cache = create_widget(monkeypatch)
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
    widget, cache = create_widget(monkeypatch)
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
    assert cache.closed is False


def test_close_event_stops_running_process_and_closes_cache(monkeypatch):
    widget, cache = create_widget(monkeypatch)
    worker = FakeWorkerForGui([])
    worker.is_running = lambda: True
    thread = FakeThread(None)
    widget.worker = worker
    widget.thread = thread
    event = DummyEvent()

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args, **kwargs: gui.QMessageBox.Yes)

    widget.closeEvent(event)

    assert event.ignored is False
    assert worker.stopped is True
    assert thread.joined is True
    assert cache.closed is True
