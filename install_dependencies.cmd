@echo off
setlocal

echo Installing core dependencies for the default transcription pipeline and the off/basic cleaning modes...
python -m pip install -r requirements.txt python-magic-bin
if errorlevel 1 exit /b %errorlevel%

echo.
echo Optional: run install_speechbrain_dependencies.cmd to enable the heavier SpeechBrain cleaning mode.

endlocal
