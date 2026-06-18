@echo off
setlocal

echo Installing development dependencies...
python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b %errorlevel%

endlocal
