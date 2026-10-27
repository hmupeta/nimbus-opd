#!/usr/bin/env bash
set -euo pipefail

echo "→ Upgrading pip..."
pip install --quiet --upgrade pip

echo "→ Installing dependencies..."
pip install -r requirements.txt

echo "→ Verifying Django installation..."
python -c "import django; print('Django', django.get_version())"

echo "→ Collecting static files..."
python manage.py collectstatic --no-input

echo "→ Build complete."
