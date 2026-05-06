"""
config.py
=========
Central configuration for VoxEmotion.
Azure App Service ready — all paths use env vars.
"""

import os
import secrets

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

# ── Base directory (project root) ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# ⚙️  PATHS  –  Azure-safe (NO Windows hardcoded paths)
# ============================================================

# On Azure App Service, dataset is NOT present — inference only.
DATASET_ROOT = os.environ.get('DATASET_ROOT', '')

# Azure App Service writable temp storage — use /tmp for outputs
_default_output = os.path.join(BASE_DIR, 'outputs')
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', _default_output)
MODEL_DIR  = os.path.join(BASE_DIR, 'models')

# ── Audio settings ────────────────────────────────────────────────────────────
SAMPLE_RATE  = 22050
HOP_LENGTH   = 256
N_MELS       = 80
N_FFT        = 1024
WIN_LENGTH   = 1024
MAX_FRAMES   = 300

EMOTIONS = ['angry', 'happy', 'neutral', 'sad', 'surprise']

# ── Tacotron2 settings ────────────────────────────────────────────────────────
T2_MAX_CHARS    = 150
SILENCE_MS      = 180
SILENCE_SAMPLES = int(SAMPLE_RATE * SILENCE_MS / 1000)

# ── Emotion prosody transform parameters ─────────────────────────────────────
EMOTION_PARAMS = {
    'angry'   : ( 2.0, 1.30, 1.05),
    'happy'   : ( 3.5, 1.20, 1.10),
    'neutral' : ( 0.0, 1.00, 1.00),
    'sad'     : (-3.0, 0.75, 0.88),
    'surprise': ( 4.5, 1.15, 1.15),
}

# ── Flask / Azure settings ────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
PORT       = int(os.environ.get('PORT', 8000))   # Azure uses 8000 by default
DEBUG      = False

# ── SESSION COOKIE — must be Secure=True on Azure (HTTPS) ────────────────────
SESSION_COOKIE_SECURE = os.environ.get('AZURE_DEPLOYMENT', 'false').lower() == 'true'

# ── Firebase (optional) ────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS = os.path.join(BASE_DIR, 'firebase_credentials.json')

# ── SMTP Email ────────────────────────────────────────────────────────────────
SMTP_EMAIL    = os.environ.get('SMTP_EMAIL', 'support.voxemotion@gmail.com')
SMTP_PASSWORD = os.environ.get('SMTP_APP_PASSWORD', '')
APP_BASE_URL  = os.environ.get('APP_BASE_URL', f'http://127.0.0.1:{PORT}')

# ── Azure Blob Storage (for model files — optional) ──────────────────────────
AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING', '')
AZURE_BLOB_CONTAINER            = os.environ.get('AZURE_BLOB_CONTAINER', 'voxemotion-models')

# ── Ensure output/model directories exist ────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR,  exist_ok=True)
