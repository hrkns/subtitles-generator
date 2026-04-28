import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "modules"

for path in (REPO_ROOT, MODULES_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _install_stub_modules():
    if "magic" not in sys.modules:
        magic_module = types.ModuleType("magic")

        class _Magic:
            def __init__(self, mime=True):
                self.mime = mime

            def from_file(self, _file_path):
                return "audio/mpeg"

        magic_module.Magic = _Magic
        sys.modules["magic"] = magic_module

    if "moviepy" not in sys.modules:
        moviepy_module = types.ModuleType("moviepy")

        class _AudioFileClip:
            def __init__(self, _video_path):
                self.video_path = _video_path

            def write_audiofile(self, _audio_path):
                return None

        moviepy_module.AudioFileClip = _AudioFileClip
        sys.modules["moviepy"] = moviepy_module

    if "whisper_timestamped" not in sys.modules:
        whisper_module = types.ModuleType("whisper_timestamped")
        whisper_module.load_audio = lambda file_path: file_path
        whisper_module.load_model = lambda model_name: {"name": model_name}
        whisper_module.transcribe = lambda model, audio, language=None: {"segments": []}
        sys.modules["whisper_timestamped"] = whisper_module

    if "pydub" not in sys.modules:
        pydub_module = types.ModuleType("pydub")

        class _AudioSegment:
            def __getitem__(self, _segment_slice):
                return self

            def export(self, _file_path, format="mp3"):
                return format

            @staticmethod
            def from_mp3(_file_path):
                return _AudioSegment()

        pydub_module.AudioSegment = _AudioSegment
        sys.modules["pydub"] = pydub_module

    if "pydub.exceptions" not in sys.modules:
        pydub_exceptions_module = types.ModuleType("pydub.exceptions")

        class CouldntDecodeError(Exception):
            pass

        pydub_exceptions_module.CouldntDecodeError = CouldntDecodeError
        sys.modules["pydub.exceptions"] = pydub_exceptions_module

    pyqt5_module = types.ModuleType("PyQt5")
    qtcore_module = types.ModuleType("PyQt5.QtCore")
    qtgui_module = types.ModuleType("PyQt5.QtGui")
    qtwidgets_module = types.ModuleType("PyQt5.QtWidgets")

    class _BoundSignal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, *args, **kwargs):
            for slot in list(self._slots):
                slot(*args, **kwargs)

    class _SignalDescriptor:
        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            if instance is None:
                return self

            signal = instance.__dict__.get(self.name)
            if signal is None:
                signal = _BoundSignal()
                instance.__dict__[self.name] = signal
            return signal

    def pyqtSignal(*_args, **_kwargs):
        return _SignalDescriptor()

    class QObject:
        def __init__(self, *_args, **_kwargs):
            pass

    class QWidget:
        def __init__(self, *_args, **_kwargs):
            self.window_title = ""
            self.window_icon = None
            self.layout = None

        def setWindowTitle(self, title):
            self.window_title = title

        def resize(self, *_args):
            return None

        def setWindowIcon(self, icon):
            self.window_icon = icon

        def setLayout(self, layout):
            self.layout = layout

        def show(self):
            return None

        def closeEvent(self, _event):
            return None

    class QVBoxLayout:
        def __init__(self):
            self.widgets = []

        def addWidget(self, widget):
            self.widgets.append(widget)

    class QPushButton(QWidget):
        def __init__(self, text=""):
            super().__init__()
            self.button_text = text
            self.clicked = _BoundSignal()
            self.disabled = False
            self.hidden = False

        def setDisabled(self, value):
            self.disabled = value

        def hide(self):
            self.hidden = True

        def show(self):
            self.hidden = False

    class QTextEdit(QWidget):
        def __init__(self):
            super().__init__()
            self._content = []

        def append(self, text):
            self._content.append(text)

        def clear(self):
            self._content = []

        def toPlainText(self):
            return "\n".join(self._content)

    class QLabel(QWidget):
        def __init__(self, text=""):
            super().__init__()
            self._text = text

        def setText(self, text):
            self._text = text

        def text(self):
            return self._text

    class QFileDialog:
        DontUseNativeDialog = 1

        @staticmethod
        def Options():
            return 0

        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            return "", ""

        @staticmethod
        def getSaveFileName(*_args, **_kwargs):
            return "", ""

    class QMessageBox:
        Yes = 1
        No = 0

        @staticmethod
        def question(*_args, **_kwargs):
            return QMessageBox.No

    class QApplication:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec_(self):
            return 0

    class QIcon:
        def __init__(self, path):
            self.path = path

    qtcore_module.pyqtSignal = pyqtSignal
    qtcore_module.QObject = QObject
    qtgui_module.QIcon = QIcon
    qtwidgets_module.QApplication = QApplication
    qtwidgets_module.QWidget = QWidget
    qtwidgets_module.QVBoxLayout = QVBoxLayout
    qtwidgets_module.QPushButton = QPushButton
    qtwidgets_module.QTextEdit = QTextEdit
    qtwidgets_module.QLabel = QLabel
    qtwidgets_module.QFileDialog = QFileDialog
    qtwidgets_module.QMessageBox = QMessageBox

    pyqt5_module.QtCore = qtcore_module
    pyqt5_module.QtGui = qtgui_module
    pyqt5_module.QtWidgets = qtwidgets_module

    sys.modules["PyQt5"] = pyqt5_module
    sys.modules["PyQt5.QtCore"] = qtcore_module
    sys.modules["PyQt5.QtGui"] = qtgui_module
    sys.modules["PyQt5.QtWidgets"] = qtwidgets_module


_install_stub_modules()
