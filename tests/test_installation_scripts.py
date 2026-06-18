from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_base_requirements_cover_default_runtime_and_lightweight_cleaning():
    requirements = read_project_file("requirements.txt")

    assert "whisper-timestamped" in requirements
    assert "pydub" in requirements
    assert "python-magic" in requirements
    assert "moviepy" in requirements
    assert "PyQt5" in requirements
    assert "audioop-lts" in requirements
    assert "speechbrain" not in requirements


def test_base_install_scripts_point_to_optional_speechbrain_install():
    install_dependencies_sh = read_project_file("install_dependencies.sh")
    install_dependencies_cmd = read_project_file("install_dependencies.cmd")

    assert "requirements.txt" in install_dependencies_sh
    assert "install_speechbrain_dependencies.sh" in install_dependencies_sh
    assert "off/basic cleaning modes" in install_dependencies_sh

    assert "requirements.txt" in install_dependencies_cmd
    assert "python-magic-bin" in install_dependencies_cmd
    assert "install_speechbrain_dependencies.cmd" in install_dependencies_cmd
    assert "off/basic cleaning modes" in install_dependencies_cmd


def test_dev_install_scripts_use_active_python_environment():
    install_dev_dependencies_sh = read_project_file("install_dev_dependencies.sh")
    install_dev_dependencies_cmd = read_project_file("install_dev_dependencies.cmd")

    assert install_dev_dependencies_sh.startswith("#!/usr/bin/env sh\nset -eu\n")
    assert "python -m pip install -r requirements-dev.txt" in install_dev_dependencies_sh
    assert "\npip install" not in install_dev_dependencies_sh

    assert install_dev_dependencies_cmd.startswith("@echo off\nsetlocal\n")
    assert "python -m pip install -r requirements-dev.txt" in install_dev_dependencies_cmd
    assert "if errorlevel 1 exit /b %errorlevel%" in install_dev_dependencies_cmd
    assert "\npip install" not in install_dev_dependencies_cmd


def test_optional_install_scripts_install_only_speechbrain_stack():
    install_speechbrain_dependencies_sh = read_project_file("install_speechbrain_dependencies.sh")
    install_speechbrain_dependencies_cmd = read_project_file("install_speechbrain_dependencies.cmd")
    speechbrain_requirements = read_project_file("requirements-speechbrain.txt")

    assert "requirements-speechbrain.txt" in install_speechbrain_dependencies_sh
    assert "optional SpeechBrain dependencies" in install_speechbrain_dependencies_sh
    assert "install_dependencies.sh" in install_speechbrain_dependencies_sh

    assert "requirements-speechbrain.txt" in install_speechbrain_dependencies_cmd
    assert "optional SpeechBrain dependencies" in install_speechbrain_dependencies_cmd
    assert "install_dependencies.cmd" in install_speechbrain_dependencies_cmd

    assert "torch" in speechbrain_requirements
    assert "torchaudio" in speechbrain_requirements
    assert "speechbrain" in speechbrain_requirements
