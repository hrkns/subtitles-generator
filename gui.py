import sys
import os
import subprocess
import importlib
import logging
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QFileDialog, QMessageBox, QComboBox, QCheckBox
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from modules import load_app_config, update_app_config


SUPPORTED_CLEANING_MODES = ("off", "basic", "speechbrain")
DEFAULT_CLEANING_MODE = "off"
CLEANING_PERFORMANCE_WARNING = (
    "Audio cleanup performance is still unstable and may vary depending on the platform where it is executed."
)


def is_speechbrain_dependency_available():
    try:
        importlib.import_module("speechbrain.inference.enhancement")
        return True
    except ModuleNotFoundError:
        return False
    except Exception as e:
        logging.warning(
            f"SpeechBrain dependencies are installed but failed during import; runtime validation will report details. Error: {e}"
        )
        return True


def validate_speechbrain_runtime_ready():
    try:
        process_input_module = importlib.import_module("process_input")
        process_input_module.load_speechbrain_enhancer()
    except Exception as e:
        raise RuntimeError(
            f"SpeechBrain enhancement is unavailable: {str(e)}"
        ) from e


class SpeechBrainRuntimeValidationWorker(QObject):
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            validate_speechbrain_runtime_ready()
        except Exception as e:
            self.finished.emit(False, str(e))
            return

        self.finished.emit(True, "")


class Worker(QObject):
    output = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.process = None

    def run(self):
        try:
            # Run the command in a subprocess and emit its output
            self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

            for stdout_line in iter(self.process.stdout.readline, ""):
                self.output.emit(stdout_line)

            self.process.stdout.close()
            return_code = self.process.wait()
            if return_code:
                raise subprocess.CalledProcessError(return_code, self.command)
        except Exception as e:
            logging.exception("Script execution failed.")
            self.output.emit(f"Script execution failed: {str(e)}")
        finally:
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

        self.cleaningModeStatusLabel = QLabel("")
        if hasattr(self.cleaningModeStatusLabel, "setWordWrap"):
            self.cleaningModeStatusLabel.setWordWrap(True)
        layout.addWidget(self.cleaningModeStatusLabel)

        self.autoApplyCleaningModeCheckBox = QCheckBox("Auto-apply preferred cleaning mode on startup")
        layout.addWidget(self.autoApplyCleaningModeCheckBox)

        self.saveCleaningModeCheckBox = QCheckBox("Save selected cleaning mode as default for future runs")
        layout.addWidget(self.saveCleaningModeCheckBox)

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

        self.appConfig = load_app_config()
        self.lastInputPath = self.appConfig.get("last_input_path", "")
        self.lastOutputPath = self.appConfig.get("last_output_path", "")
        self.speechbrainDependencyAvailable = is_speechbrain_dependency_available()
        self.speechbrainValidationWorker = None
        self.speechbrainValidationThread = None
        self.autoApplyCleaningModeCheckBox.setChecked(self.appConfig.get("auto_apply_cleaning_mode", False))
        self.cleaningModeComboBox.setCurrentText(self.resolve_initial_cleaning_mode())
        self.saveCleaningModeCheckBox.setChecked(False)
        self.update_cleaning_mode_status(self.cleaningModeComboBox.currentText())

    def resolve_initial_cleaning_mode(self):
        saved_mode = self.appConfig.get("preferred_cleaning_mode")
        should_preselect_saved_mode = self.appConfig.get("auto_apply_cleaning_mode", False)

        if should_preselect_saved_mode and saved_mode in SUPPORTED_CLEANING_MODES:
            return saved_mode

        return DEFAULT_CLEANING_MODE

    def update_app_config_safely(self, app_config_updates, error_prefix=None, show_in_log=False):
        try:
            self.appConfig = update_app_config(app_config_updates)
            return True
        except Exception as e:
            error_message = error_prefix or "Could not persist application configuration."
            full_error_message = f"{error_message} {str(e)}"
            logging.warning(full_error_message)
            if show_in_log:
                self.logTextEdit.append(full_error_message)
            return False

    def update_cleaning_mode_status(self, selected_mode):
        if selected_mode == "speechbrain":
            if self.speechbrainDependencyAvailable:
                self.cleaningModeStatusLabel.setText(
                    "SpeechBrain enhancement dependencies are available. Model readiness will be validated before launch, and the first run may download model assets.\n"
                    + CLEANING_PERFORMANCE_WARNING
                )
            else:
                self.cleaningModeStatusLabel.setText(
                    "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before using this mode.\n"
                    + CLEANING_PERFORMANCE_WARNING
                )
        elif selected_mode == "basic":
            self.cleaningModeStatusLabel.setText(
                "Basic cleaning uses the lightweight built-in preprocessing chain.\n"
                + CLEANING_PERFORMANCE_WARNING
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

        return command

    def persist_runtime_preferences(self):
        return self.update_app_config_safely(
            {
                "last_input_path": self.lastInputPath,
                "last_output_path": self.lastOutputPath,
                "auto_apply_cleaning_mode": self.autoApplyCleaningModeCheckBox.isChecked(),
            }
        )

    def persist_preferred_cleaning_mode(self):
        return self.update_app_config_safely(
            {
                "preferred_cleaning_mode": self.cleaningModeComboBox.currentText(),
                "auto_apply_cleaning_mode": self.autoApplyCleaningModeCheckBox.isChecked(),
            },
            error_prefix="Could not save preferred cleaning settings.",
            show_in_log=True,
        )

    def validate_selected_cleaning_mode(self):
        selected_mode = self.cleaningModeComboBox.currentText()

        if selected_mode != "speechbrain":
            return True

        if not self.speechbrainDependencyAvailable:
            self.logTextEdit.append(
                "SpeechBrain enhancement is unavailable. Install the optional SpeechBrain dependencies before running with this mode."
            )
            return False

        return True

    def should_validate_speechbrain_runtime_before_launch(self):
        if self.cleaningModeComboBox.currentText() != "speechbrain":
            return False

        return self.appConfig.get("speechbrain_strategy_settings", {}).get("validate_runtime_before_launch", True)

    def set_execution_controls_disabled(self, disabled):
        for control in (
            self.btnRunScript,
            self.btnSelectFile,
            self.btnSelectOutput,
            self.cleaningModeComboBox,
            self.autoApplyCleaningModeCheckBox,
            self.saveCleaningModeCheckBox,
        ):
            if hasattr(control, "setDisabled"):
                control.setDisabled(disabled)

    def start_qthread_worker(self, worker, finished_signal):
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        finished_signal.connect(lambda *_args: thread.quit())
        if hasattr(worker, "deleteLater"):
            finished_signal.connect(lambda *_args: worker.deleteLater())
        if hasattr(thread, "deleteLater"):
            thread.finished.connect(thread.deleteLater)
        thread.start()
        return thread

    def start_speechbrain_runtime_validation(self):
        self.logTextEdit.append("Validating SpeechBrain enhancement availability...")
        self.cleaningModeStatusLabel.setText(
            "Validating SpeechBrain enhancement runtime readiness. The first run may download model assets.\n"
            + CLEANING_PERFORMANCE_WARNING
        )
        self.set_execution_controls_disabled(True)
        self.btnCancelScript.hide()

        self.speechbrainValidationWorker = SpeechBrainRuntimeValidationWorker()
        self.speechbrainValidationWorker.finished.connect(self.speechbrain_runtime_validation_finished)
        self.speechbrainValidationThread = self.start_qthread_worker(
            self.speechbrainValidationWorker,
            self.speechbrainValidationWorker.finished,
        )

    def speechbrain_runtime_validation_finished(self, is_ready, message):
        self.speechbrainValidationWorker = None
        self.speechbrainValidationThread = None

        if not is_ready:
            self.logTextEdit.append(message)
            self.cleaningModeStatusLabel.setText(f"{message}\n" + CLEANING_PERFORMANCE_WARNING)
            self.set_execution_controls_disabled(False)
            self.btnCancelScript.hide()
            return

        self.logTextEdit.append("SpeechBrain enhancement is ready.")
        self.cleaningModeStatusLabel.setText(
            "SpeechBrain enhancement runtime is ready.\n"
            + CLEANING_PERFORMANCE_WARNING
        )
        self.start_script_execution()

    def select_file(self):
        # File selection dialog
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File", self.lastInputPath, "Audio/Video Files (*.mp3 *.wav *.mp4 *.avi)")
        if file_name:
            self.selectedFile = file_name
            self.selectedFileLabel.setText(f"Selected File: {file_name}")
            self.lastInputPath = os.path.dirname(file_name)
            self.persist_runtime_preferences()

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
            self.lastOutputPath = os.path.dirname(file_name)
            self.persist_runtime_preferences()

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.is_running():
            reply = QMessageBox.question(self, 'Message',
                                        "Are you sure to quit? The running process will be stopped.",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.thread.quit()
                self.thread.wait()
            else:
                event.ignore()
                return

        self.persist_runtime_preferences()
        super().closeEvent(event)

    def start_script_execution(self):
        self.persist_runtime_preferences()

        if self.saveCleaningModeCheckBox.isChecked():
            self.persist_preferred_cleaning_mode()

        self.logTextEdit.append("Running script...")

        # Disable the run button and show the cancel button
        self.set_execution_controls_disabled(True)
        self.btnCancelScript.show()

        # Prepare and start the script execution thread
        command = self.build_command()
        self.worker = Worker(command)
        self.worker.output.connect(self.logTextEdit.append)
        self.worker.finished.connect(self.script_finished)
        self.thread = self.start_qthread_worker(self.worker, self.worker.finished)

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

        if self.should_validate_speechbrain_runtime_before_launch():
            self.start_speechbrain_runtime_validation()
            return

        self.start_script_execution()

    def cancel_script(self):
        # Stop the script execution
        self.worker.stop()
        self.script_finished()

    def script_finished(self):
        # Re-enable the run button and hide the cancel button
        self.set_execution_controls_disabled(False)
        self.btnCancelScript.hide()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    demo = SubtitlesGeneratorGUI()
    demo.show()
    sys.exit(app.exec_())
