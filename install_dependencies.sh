#!/usr/bin/env sh
set -eu

echo "Installing core dependencies for the default transcription pipeline and the off/basic cleaning modes..."
python -m pip install -r requirements.txt

echo
echo "Optional: run ./install_speechbrain_dependencies.sh to enable the heavier SpeechBrain cleaning mode."
