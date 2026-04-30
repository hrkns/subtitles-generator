#!/usr/bin/env sh
set -eu

echo "Installing optional SpeechBrain dependencies on top of the base install..."
python -m pip install -r requirements-speechbrain.txt

echo
echo "SpeechBrain cleaning mode is now available. Run ./install_dependencies.sh first if the base runtime dependencies are not installed yet."