#!/usr/bin/env sh
set -eu

echo "Installing development dependencies..."
python -m pip install -r requirements-dev.txt
