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
        pydub_effects_module = types.ModuleType("pydub.effects")

        class _AudioSegment:
            def __getitem__(self, _segment_slice):
                return self

            def export(self, _file_path, format="wav"):
                return format

            @staticmethod
            def from_file(_file_path):
                return _AudioSegment()

            @staticmethod
            def from_mp3(_file_path):
                return _AudioSegment()

        pydub_effects_module.normalize = lambda audio: audio
        pydub_effects_module.compress_dynamic_range = lambda audio: audio
        pydub_effects_module.high_pass_filter = lambda audio, _cutoff: audio
        pydub_effects_module.low_pass_filter = lambda audio, _cutoff: audio

        pydub_module.AudioSegment = _AudioSegment
        pydub_module.effects = pydub_effects_module
        sys.modules["pydub"] = pydub_module
        sys.modules["pydub.effects"] = pydub_effects_module

    if "pydub.exceptions" not in sys.modules:
        pydub_exceptions_module = types.ModuleType("pydub.exceptions")

        class CouldntDecodeError(Exception):
            pass

        pydub_exceptions_module.CouldntDecodeError = CouldntDecodeError
        sys.modules["pydub.exceptions"] = pydub_exceptions_module

    if "PyQt5" not in sys.modules:
        pyqt5_module = types.ModuleType("PyQt5")
        qtcore_module = types.ModuleType("PyQt5.QtCore")
        qtgui_module = types.ModuleType("PyQt5.QtGui")
        qtwidgets_module = types.ModuleType("PyQt5.QtWidgets")

        class _BoundSignal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args, **kwargs):
                for callback in list(self._callbacks):
                    callback(*args, **kwargs)

        class _SignalDescriptor:
            def __set_name__(self, owner, name):
                self.name = name

            def __get__(self, instance, owner):
                if instance is None:
                    return self

                if self.name not in instance.__dict__:
                    instance.__dict__[self.name] = _BoundSignal()

                return instance.__dict__[self.name]

        def pyqtSignal(*_args, **_kwargs):
            return _SignalDescriptor()

        class QObject:
            def __init__(self, *_args, **_kwargs):
                return None

        class QWidget:
            def __init__(self, *_args, **_kwargs):
                self.window_title = None
                self.window_size = None
                self.window_icon = None
                self.layout = None

            def setWindowTitle(self, title):
                self.window_title = title

            def resize(self, width, height):
                self.window_size = (width, height)

            def setWindowIcon(self, icon):
                self.window_icon = icon

            def setLayout(self, layout):
                self.layout = layout

            def closeEvent(self, _event):
                return None

        class QVBoxLayout:
            def __init__(self):
                self.widgets = []

            def addWidget(self, widget):
                self.widgets.append(widget)

        class QPushButton:
            def __init__(self, text=""):
                self.text = text
                self.clicked = _BoundSignal()
                self.disabled = False
                self.visible = True

            def setDisabled(self, value):
                self.disabled = value

            def hide(self):
                self.visible = False

            def show(self):
                self.visible = True

        class QTextEdit:
            def __init__(self):
                self.lines = []

            def append(self, text):
                self.lines.append(text)

            def clear(self):
                self.lines.clear()

        class QLabel:
            def __init__(self, text=""):
                self.text = text

            def setText(self, text):
                self.text = text

        class QFileDialog:
            DontUseNativeDialog = 1

            @staticmethod
            def Options():
                return 0

            @staticmethod
            def getOpenFileName(*_args, **_kwargs):
                return ("", "")

            @staticmethod
            def getSaveFileName(*_args, **_kwargs):
                return ("", "")

        class QMessageBox:
            Yes = 1
            No = 0

            @staticmethod
            def question(*_args, **_kwargs):
                return QMessageBox.No

        class QApplication:
            def __init__(self, args):
                self.args = args

            def exec_(self):
                return 0

        class QIcon:
            def __init__(self, path):
                self.path = path

        qtcore_module.QObject = QObject
        qtcore_module.pyqtSignal = pyqtSignal
        qtgui_module.QIcon = QIcon
        qtwidgets_module.QApplication = QApplication
        qtwidgets_module.QFileDialog = QFileDialog
        qtwidgets_module.QLabel = QLabel
        qtwidgets_module.QMessageBox = QMessageBox
        qtwidgets_module.QPushButton = QPushButton
        qtwidgets_module.QTextEdit = QTextEdit
        qtwidgets_module.QVBoxLayout = QVBoxLayout
        qtwidgets_module.QWidget = QWidget

        pyqt5_module.QtCore = qtcore_module
        pyqt5_module.QtGui = qtgui_module
        pyqt5_module.QtWidgets = qtwidgets_module

        sys.modules["PyQt5"] = pyqt5_module
        sys.modules["PyQt5.QtCore"] = qtcore_module
        sys.modules["PyQt5.QtGui"] = qtgui_module
        sys.modules["PyQt5.QtWidgets"] = qtwidgets_module


_install_stub_modules()
