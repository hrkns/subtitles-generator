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


_install_stub_modules()
