import sys
import subprocess
import threading
import shelve
import importlib
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QFileDialog, QMessageBox, QComboBox, QCheckBox
from PyQt5.QtCore import pyqtSignal, QObject 
from modules import load_cleaning_settings


SUPPORTED_CLEANING_MODES = ("off", "basic", "speechbrain")
DEFAULT_CLEANING_MODE = "off"


def is_speechbrain_dependency_available():
    try:
        importlib.import_module("speechbrain.inference.enhancement")
        return True
    except Exception:
        return False


def validate_speechbrain_runtime_ready():
    try:
        process_input_module = importlib.import_module("process_input")
        process_input_module.load_speechbrain_enhancer()
    except Exception as e:
        raise RuntimeError(
            f"SpeechBrain enhancement is unavailable: {str(e)}"
        ) from e

class Worker(QObject):
    output = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.process = None

    def run(self):
        # Run the command in a subprocess and emit its output
        self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        for stdout_line in iter(self.process.stdout.readline, ""):
            self.output.emit(stdout_line)

        self.process.stdout.close()
        return_code = self.process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, self.command)
        self.finished.emit()

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        # Terminate the subprocess if it is running
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

class SubtitlesGeneratorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subtitles Generator")
        self.resize(500, 300)
        self.setWindowIcon(QIcon('./assets/img/icon.png'))

        layout = QVBoxLayout()

        # Setup UI components
        self.label = QLabel("Select an audio/video file to generate subtitles.")
        layout.addWidget(self.label)

        self.btnSelectFile = QPushButton("Select File")
        self.btnSelectFile.clicked.connect(self.select_file)
        layout.addWidget(self.btnSelectFile)

        self.selectedFileLabel = QLabel("Selected File: None")
        layout.addWidget(self.selectedFileLabel)

        self.outputPathLabel = QLabel("Output File: Not Set")
        layout.addWidget(self.outputPathLabel)

        self.btnSelectOutput = QPushButton("Select Output File")
        self.btnSelectOutput.clicked.connect(self.select_output_file)
        layout.addWidget(self.btnSelectOutput)

        self.cleaningModeTitleLabel = QLabel("Cleaning Mode")
        layout.addWidget(self.cleaningModeTitleLabel)

        self.cleaningModeComboBox = QComboBox()
        self.cleaningModeComboBox.addItems(list(SUPPORTED_CLEANING_MODES))
        self.cleaningModeComboBox.currentTextChanged.connect(self.update_cleaning_mode_status)
        layout.addWidget(self.cleaningModeComboBox)

        self.saveCleaningModeCheckBox = QCheckBox("Save selected cleaning mode as default for future runs")
        layout.addWidget(self.saveCleaningModeCheckBox)

        self.cleaningModeStatusLabel = QLabel("")
        layout.addWidget(self.cleaningModeStatusLabel)

        self.logTextEdit = QTextEdit()
        layout.addWidget(self.logTextEdit)

        self.btnRunScript = QPushButton('Generate Subtitles')
        self.btnRunScript.clicked.connect(self.run_script)
        layout.addWidget(self.btnRunScript)

        self.btnCancelScript = QPushButton('Cancel')
        self.btnCancelScript.clicked.connect(self.cancel_script)
        self.btnCancelScript.hide()  # Initially hidden
        layout.addWidget(self.btnCancelScript)

        self.setLayout(layout)

        self.outputPath = ""
        self.selectedFile = ""

        # Load cached paths
        self.cache = shelve.open(".cache")
        try:
            self.lastInputPath = self.cache.get("lastInputPath", "")
        except Exception as e:
            self.lastInputPath = ""
        try:
            self.lastOutputPath = self.cache.get("lastOutputPath", "")
        except Exception as e:
            self.lastOutputPath = ""

        self.speechbrainDependencyAvailable = is_speechbrain_dependency_available()
        self.cleaningSettings = load_cleaning_settings()
        self.cleaningModeComboBox.setCurrentText(self.resolve_initial_cleaning_mode())
        self.saveCleaningModeCheckBox.setChecked(False)
        self.update_cleaning_mode_status(self.cleaningModeComboBox.currentText())

    def resolve_initial_cleaning_mode(self):
        saved_mode = self.cleaningSettings.get("default_cleaning_mode")
        should_preselect_saved_mode = self.cleaningSettings.get("preselect_saved_cleaning_mode", False)

        if should_preselect_saved_mode and saved_mode in SUPPORTED_CLEANING_MODES:
            return saved_mode

        return DEFAULT_CLEANING_MODE

    def update_cleaning_mode_status(self, selected_mode):
        if selected_mode == "speechbrain":
            if self.speechbrainDependencyAvailable:
                self.cleaningModeStatusLabel.setText(
                    "SpeechBrain enhancement dependencies are available. Model readiness will be validated before launch, and the first run may download model assets."
                )
            else:
                self.cleaningModeStatusLabel.setText(
                    "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before using this mode."
                )
        elif selected_mode == "basic":
            self.cleaningModeStatusLabel.setText(
                "Basic cleaning uses the lightweight built-in preprocessing chain."
            )
        else:
            self.cleaningModeStatusLabel.setText(
                "Off uses the normalized working WAV without additional cleaning."
            )

    def build_command(self):
        command = [
            sys.executable,
            "main.py",
            "--input",
            self.selectedFile,
            "--output",
            self.outputPath,
            "--checkpoints",
            "30s",
            "--cleaning-mode",
            self.cleaningModeComboBox.currentText(),
        ]

        if self.saveCleaningModeCheckBox.isChecked():
            command.append("--save-cleaning-mode")

        return command

    def validate_selected_cleaning_mode(self):
        selected_mode = self.cleaningModeComboBox.currentText()

        if selected_mode != "speechbrain":
            return True

        if not self.speechbrainDependencyAvailable:
            self.logTextEdit.append(
                "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before running with this mode."
            )
            return False

        self.logTextEdit.append("Validating SpeechBrain enhancement availability...")

        try:
            validate_speechbrain_runtime_ready()
        except RuntimeError as e:
            self.logTextEdit.append(str(e))
            return False

        return True

    def select_file(self):
        # File selection dialog
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File", self.lastInputPath, "Audio/Video Files (*.mp3 *.wav *.mp4 *.avi)")
        if file_name:
            self.selectedFile = file_name
            self.selectedFileLabel.setText(f"Selected File: {file_name}")
            self.lastInputPath = "/".join(file_name.split("/")[:-1])
            self.cache["lastInputPath"] = self.lastInputPath

    def select_output_file(self):
        # Output file selection dialog
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.lastOutputPath, "Subtitle Files (*.srt)", options=options)
        if file_name:
            if not file_name.endswith('.srt'):
                file_name += '.srt'
            self.outputPath = file_name
            self.outputPathLabel.setText(f"Output File: {file_name}")
            self.lastOutputPath = "/".join(file_name.split("/")[:-1])
            self.cache["lastOutputPath"] = self.lastOutputPath

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.is_running():
            reply = QMessageBox.question(self, 'Message',
                                        "Are you sure to quit? The running process will be stopped.",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.thread.join()
            else:
                event.ignore()
                return

        self.cache.close()
        super().closeEvent(event)

    def run_script(self):
        # Check for file selection
        if not self.selectedFile or not self.outputPath:
            self.logTextEdit.append("No input or output file selected.")
            return
        else:
            # Clear the log text edit and initialize it back
            self.logTextEdit.clear()

        if not self.validate_selected_cleaning_mode():
            return

        self.logTextEdit.append("Running script...")

        # Disable the run button and show the cancel button
        self.btnRunScript.setDisabled(True)
        self.btnSelectFile.setDisabled(True)
        self.btnSelectOutput.setDisabled(True)
        self.btnCancelScript.show()

        # Prepare and start the script execution thread
        command = self.build_command()
        self.worker = Worker(command)
        self.worker.output.connect(self.logTextEdit.append)
        self.worker.finished.connect(self.script_finished)
        self.thread = threading.Thread(target=self.worker.run)
        self.thread.start()

    def cancel_script(self):
        # Stop the script execution
        self.worker.stop()
        self.script_finished()

    def script_finished(self):
        # Re-enable the run button and hide the cancel button
        self.btnRunScript.setDisabled(False)
        self.btnSelectFile.setDisabled(False)
        self.btnSelectOutput.setDisabled(False)
        self.btnCancelScript.hide()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    demo = SubtitlesGeneratorGUI()
    demo.show()
    sys.exit(app.exec_())
