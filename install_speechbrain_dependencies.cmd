@echo off
setlocal

echo Installing optional SpeechBrain dependencies on top of the base install...
python -m pip install -r requirements-speechbrain.txt
if errorlevel 1 exit /b %errorlevel%

echo.
echo SpeechBrain cleaning mode is now available. Run install_dependencies.cmd first if the base runtime dependencies are not installed yet.

endlocal
