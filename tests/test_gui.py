import gui


class FakeCache(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.closed = False

    def close(self):
        self.closed = True


class DummySignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


def create_window(monkeypatch, cache=None):
    fake_cache = cache or FakeCache()
    monkeypatch.setattr(gui.shelve, "open", lambda _path: fake_cache)
    window = gui.SubtitlesGeneratorGUI()
    return window, fake_cache


def test_worker_run_emits_output_and_finished(monkeypatch):
    outputs = []
    finished = []

    class FakeStdout:
        def __init__(self):
            self.lines = iter(["line 1\n", "line 2\n", ""])

        def readline(self):
            return next(self.lines)

        def close(self):
            return None

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout()

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(gui.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    worker = gui.Worker(["python", "main.py"])
    worker.output.connect(outputs.append)
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert outputs == ["line 1\n", "line 2\n"]
    assert finished == [True]


def test_worker_stop_terminates_running_process():
    class FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    worker = gui.Worker(["python", "main.py"])
    worker.process = FakeProcess()

    assert worker.is_running() is True
    worker.stop()
    assert worker.process.terminated is True


def test_select_file_updates_selection_and_cache(monkeypatch):
    window, cache = create_window(monkeypatch)
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("C:/media/input.mp3", ""))

    window.select_file()

    assert window.selectedFile == "C:/media/input.mp3"
    assert window.selectedFileLabel.text() == "Selected File: C:/media/input.mp3"
    assert cache["lastInputPath"] == "C:/media"


def test_select_output_file_appends_extension_and_updates_cache(monkeypatch):
    window, cache = create_window(monkeypatch)
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("C:/output/subtitles", ""))

    window.select_output_file()

    assert window.outputPath == "C:/output/subtitles.srt"
    assert window.outputPathLabel.text() == "Output File: C:/output/subtitles.srt"
    assert cache["lastOutputPath"] == "C:/output"


def test_run_script_requires_selected_input_and_output(monkeypatch):
    window, _cache = create_window(monkeypatch)

    window.run_script()

    assert "No input or output file selected." in window.logTextEdit.toPlainText()
    assert window.btnRunScript.disabled is False


def test_run_script_configures_worker_thread_and_button_state(monkeypatch):
    window, _cache = create_window(monkeypatch)
    thread_state = {}

    class FakeWorker:
        def __init__(self, command):
            self.command = command
            self.output = DummySignal()
            self.finished = DummySignal()
            self.stopped = False

        def run(self):
            return None

        def stop(self):
            self.stopped = True

        def is_running(self):
            return True

    class FakeThread:
        def __init__(self, target):
            self.target = target
            self.started = False
            self.joined = False
            thread_state["thread"] = self

        def start(self):
            self.started = True

        def join(self):
            self.joined = True

    monkeypatch.setattr(gui, "Worker", FakeWorker)
    monkeypatch.setattr(gui.threading, "Thread", FakeThread)

    window.selectedFile = "C:/media/input.mp3"
    window.outputPath = "C:/output/subtitles.srt"

    window.run_script()

    assert window.worker.command == [
        "python",
        "main.py",
        "--input",
        "C:/media/input.mp3",
        "--output",
        "C:/output/subtitles.srt",
        "--checkpoints",
        "30s",
    ]
    assert window.btnRunScript.disabled is True
    assert window.btnSelectFile.disabled is True
    assert window.btnSelectOutput.disabled is True
    assert window.btnCancelScript.hidden is False
    assert thread_state["thread"].started is True
    assert "Running script..." in window.logTextEdit.toPlainText()


def test_cancel_script_stops_worker_and_restores_buttons(monkeypatch):
    window, _cache = create_window(monkeypatch)

    class FakeWorker:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

        def is_running(self):
            return True

    window.worker = FakeWorker()
    window.btnRunScript.setDisabled(True)
    window.btnSelectFile.setDisabled(True)
    window.btnSelectOutput.setDisabled(True)
    window.btnCancelScript.show()

    window.cancel_script()

    assert window.worker.stopped is True
    assert window.btnRunScript.disabled is False
    assert window.btnSelectFile.disabled is False
    assert window.btnSelectOutput.disabled is False
    assert window.btnCancelScript.hidden is True


def test_close_event_stops_running_worker_and_closes_cache(monkeypatch):
    window, cache = create_window(monkeypatch)
    state = {}

    class FakeWorker:
        def __init__(self):
            self.stopped = False

        def is_running(self):
            return True

        def stop(self):
            self.stopped = True

    class FakeThread:
        def __init__(self):
            self.joined = False

        def join(self):
            self.joined = True

    class FakeEvent:
        def __init__(self):
            self.ignored = False

        def ignore(self):
            self.ignored = True

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *args, **kwargs: gui.QMessageBox.Yes)
    window.worker = FakeWorker()
    window.thread = FakeThread()
    event = FakeEvent()

    window.closeEvent(event)

    assert window.worker.stopped is True
    assert window.thread.joined is True
    assert cache.closed is True
    assert event.ignored is False
