#!/bin/bash
# Azure App Service startup script for VoxEmotion
# This file is referenced in Azure Portal → Configuration → Startup Command
# Startup Command to enter in Azure Portal:
#   gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=1 --threads=2 app:app

echo "=== VoxEmotion Azure Startup ==="
echo "Python: $(python --version)"
echo "Working dir: $(pwd)"
echo "Models dir contents:"
ls -lh models/ 2>/dev/null || echo "(models folder empty or missing)"
echo "================================"

# Start gunicorn
gunicorn \
    --bind=0.0.0.0:8000 \
    --timeout=600 \
    --workers=1 \
    --threads=2 \
    --log-level=info \
    --access-logfile=- \
    --error-logfile=- \
    app:app
