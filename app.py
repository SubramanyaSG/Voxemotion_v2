"""
app.py
======
VoxEmotion Flask Web Application
Azure App Service ready.

Startup:
  gunicorn --bind=0.0.0.0:8000 --timeout=600 app:app
"""

import os
import re
import uuid
import traceback
from pathlib import Path
from datetime import timedelta
from functools import wraps

from flask import (Flask, request, jsonify, render_template,
                   Response, redirect, url_for, session, flash, abort)
from flask_cors import CORS

# ── Project imports ───────────────────────────────────────────────────────────
from config import (BASE_DIR, OUTPUT_DIR, MODEL_DIR, EMOTIONS,
                    SECRET_KEY, PORT, DEBUG, SESSION_COOKIE_SECURE,
                    AZURE_STORAGE_CONNECTION_STRING, AZURE_BLOB_CONTAINER)

from utils.auth import (
    init_firebase, generate_csrf, validate_csrf,
    is_rate_allowed, get_reg_cooldown, set_reg_cooldown,
    create_reset_token, consume_reset_token, is_reset_token_valid,
    send_password_reset_email,
    valid_email, valid_password, valid_fullname, valid_dob,
    user_exists, create_user, verify_user, update_password
)
from utils.dataset import get_dataset_df
from utils.text_utils import normalize_text, extract_text_from_file
from models.synthesizer import EmotionSynthesizer
import soundfile as sf

# ── Azure Blob model downloader ──────────────────────────────────────────────
def _download_models_from_blob():
    """
    If AZURE_STORAGE_CONNECTION_STRING is set, downloads missing model
    files from Azure Blob Storage into ./models/ at startup.
    Safe to call even when blob storage is not configured.
    """
    if not AZURE_STORAGE_CONNECTION_STRING:
        return
    try:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container = client.get_container_client(AZURE_BLOB_CONTAINER)
        for blob in container.list_blobs():
            dest = os.path.join(MODEL_DIR, blob.name)
            if not os.path.exists(dest):
                print(f'[VoxEmotion] Downloading {blob.name} from Azure Blob …')
                with open(dest, 'wb') as f:
                    f.write(container.download_blob(blob.name).readall())
                print(f'[VoxEmotion] ✓  {blob.name} saved.')
    except Exception as e:
        print(f'[VoxEmotion] Azure Blob download skipped: {e}')

# ── Download models if needed ─────────────────────────────────────────────────
_download_models_from_blob()

# ── Initialize Firebase ───────────────────────────────────────────────────────
init_firebase()

# ── Initialize Synthesizer ────────────────────────────────────────────────────
print('[VoxEmotion] Initializing synthesizer …')
try:
    _df = get_dataset_df()
except Exception:
    import pandas as pd
    _df = pd.DataFrame()

_synthesizer = EmotionSynthesizer(dataset_df=_df, output_dir=OUTPUT_DIR)
print('[VoxEmotion] Synthesizer ready.\n')

# ── Flask application ─────────────────────────────────────────────────────────
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY  = True,
    SESSION_COOKIE_SAMESITE  = 'Lax',
    SESSION_COOKIE_SECURE    = SESSION_COOKIE_SECURE,   # True on Azure (HTTPS)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7),
    MAX_CONTENT_LENGTH       = 50 * 1024 * 1024,        # 50 MB
)

CORS(app, supports_credentials=True)

# ── Security headers ──────────────────────────────────────────────────────────
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'DENY'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    response.headers['Referrer-Policy']         = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']      = 'microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
        "https://fonts.gstatic.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "media-src 'self' blob:;"
    )
    return response

# ── Login required decorator ──────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            flash('Please log in to continue.', 'info')
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user_email' in session:
        return redirect(url_for('index'))

    csrf = session.get('csrf_token') or generate_csrf()

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token', '')):
            flash('Invalid request. Please try again.', 'error')
            return redirect(url_for('login_page'))

        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        if not is_rate_allowed(ip, limit=10, window=60):
            flash('Too many login attempts. Please wait 1 minute.', 'error')
            return render_template('login.html', csrf_token=csrf)

        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not valid_email(email) or not password:
            flash('Please enter a valid email and password.', 'error')
            return render_template('login.html', csrf_token=csrf)

        user = verify_user(email, password)
        if not user:
            flash('Incorrect email or password.', 'error')
            return render_template('login.html', csrf_token=csrf)

        session.permanent          = bool(request.form.get('remember'))
        session['user_email']      = user['email']
        session['user_fullname']   = user.get('fullname', '')
        session['user_role']       = user.get('role', 'user')
        session.pop('csrf_token', None)
        return redirect(url_for('index'))

    return render_template('login.html', csrf_token=csrf)


@app.route('/register', methods=['POST'])
def register():
    csrf = session.get('csrf_token') or generate_csrf()

    if not validate_csrf(request.form.get('csrf_token', '')):
        flash('Invalid request. Please try again.', 'error')
        return redirect(url_for('login_page'))

    ip   = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    wait = get_reg_cooldown(ip)
    if wait:
        flash(f'Please wait {wait} more seconds before registering again.', 'warning')
        return render_template('login.html', csrf_token=csrf)

    if not is_rate_allowed(ip, limit=3, window=3600):
        flash('Registration limit reached. Please try again later.', 'error')
        return render_template('login.html', csrf_token=csrf)

    fullname = request.form.get('fullname', '').strip()
    dob      = request.form.get('dob', '').strip()
    email    = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm  = request.form.get('confirm_password', '')

    errors = []
    if not valid_fullname(fullname):
        errors.append('Name must contain letters only — no spaces or special characters.')
    if not valid_dob(dob):
        errors.append('Invalid date of birth. Use DD/MM/YYYY.')
    if not valid_email(email):
        errors.append('Invalid email address.')
    if not valid_password(password):
        errors.append('Password must be 8+ characters with 1 uppercase letter and 1 number.')
    if password != confirm:
        errors.append('Passwords do not match.')
    if not request.form.get('agree_terms'):
        errors.append('You must accept the Terms & Conditions.')

    if errors:
        for err in errors:
            flash(err, 'error')
        return render_template('login.html', csrf_token=csrf)

    if user_exists(email):
        flash('An account with this email already exists.', 'error')
        return render_template('login.html', csrf_token=csrf)

    if not create_user(email, password, fullname, dob):
        flash('Registration failed. Please try again.', 'error')
        return render_template('login.html', csrf_token=csrf)

    set_reg_cooldown(ip)
    flash('Account created successfully! Please log in.', 'success')
    return redirect(url_for('login_page'))


@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    csrf = session.get('csrf_token') or generate_csrf()

    if not validate_csrf(request.form.get('csrf_token', '')):
        flash('Invalid request.', 'error')
        return redirect(url_for('login_page'))

    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if not is_rate_allowed(ip, limit=3, window=300):
        flash('Too many reset requests. Please wait 5 minutes.', 'error')
        return render_template('login.html', csrf_token=csrf)

    email = request.form.get('email', '').strip().lower()
    if not valid_email(email):
        flash('Please enter a valid email address.', 'error')
        return render_template('login.html', csrf_token=csrf)

    if user_exists(email):
        token = create_reset_token(email)
        send_password_reset_email(email, token)

    flash('If that email is registered, a reset link has been sent.', 'success')
    return redirect(url_for('login_page'))


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        if not is_reset_token_valid(token):
            flash('This reset link is invalid or has expired.', 'error')
            return redirect(url_for('login_page'))
        csrf = session.get('csrf_token') or generate_csrf()
        return render_template('reset_password.html', token=token, csrf_token=csrf)

    csrf = session.get('csrf_token') or generate_csrf()

    if not validate_csrf(request.form.get('csrf_token', '')):
        flash('Invalid request.', 'error')
        return redirect(url_for('login_page'))

    password = request.form.get('password', '')
    confirm  = request.form.get('confirm_password', '')

    if not valid_password(password):
        flash('Password must be 8+ characters with 1 uppercase letter and 1 number.', 'error')
        return render_template('reset_password.html', token=token, csrf_token=csrf)

    if password != confirm:
        flash('Passwords do not match.', 'error')
        return render_template('reset_password.html', token=token, csrf_token=csrf)

    email = consume_reset_token(token)
    if not email:
        flash('Reset link expired or already used.', 'error')
        return redirect(url_for('login_page'))

    if update_password(email, password):
        flash('Password updated successfully! Please log in.', 'success')
    else:
        flash('Could not update password. Please try again.', 'error')

    return redirect(url_for('login_page'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'info')
    return redirect(url_for('login_page'))


# ════════════════════════════════════════════════════════════════════════════
# MAIN APP ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/')
@login_required
def index():
    return render_template(
        'index.html',
        emotions=EMOTIONS,
        user=session.get('user_fullname', '')
    )


@app.route('/synthesize', methods=['POST'])
@login_required
def synthesize():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if not is_rate_allowed(ip, limit=20, window=60):
        return jsonify({'error': 'Rate limit exceeded. Please slow down.'}), 429
    try:
        data    = request.get_json(force=True)
        text    = data.get('text', '').strip()
        emotion = data.get('emotion', 'neutral')

        if not text:
            return jsonify({'error': 'No text provided.'}), 400

        result = _synthesizer.synthesize(text, emotion)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/upload', methods=['POST'])
@login_required
def upload():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if not is_rate_allowed(ip, limit=10, window=60):
        return jsonify({'error': 'Rate limit exceeded. Please slow down.'}), 429
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded.'}), 400

        f       = request.files['file']
        emotion = request.form.get('emotion', 'neutral')
        ext     = Path(f.filename).suffix.lower()

        if ext not in {'.txt', '.pdf', '.docx'}:
            return jsonify({'error': f'Unsupported file type: {ext}'}), 400

        tmp = os.path.join(OUTPUT_DIR, f'upload_{uuid.uuid4().hex}{ext}')
        f.save(tmp)
        text = extract_text_from_file(tmp)
        os.remove(tmp)

        if not text.strip():
            return jsonify({'error': 'No text could be extracted from this file.'}), 400

        result = _synthesizer.synthesize(text, emotion)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/audio/<filename>')
@login_required
def serve_audio(filename):
    filename = os.path.basename(filename)
    if not re.match(r'^tts_[a-z]+_[a-f0-9]+\.wav$', filename):
        abort(403)

    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Audio file not found.'}), 404

    with open(filepath, 'rb') as f:
        data = f.read()

    resp = Response(data, mimetype='audio/wav')
    resp.headers['Content-Length']  = len(data)
    resp.headers['Accept-Ranges']   = 'bytes'
    resp.headers['Cache-Control']   = 'no-cache, no-store, must-revalidate'
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('login.html', csrf_token=generate_csrf()), 404

@app.errorhandler(403)
def forbidden(e):
    return jsonify({'error': 'Forbidden'}), 403

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 50 MB.'}), 413

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Too many requests. Please slow down.'}), 429

# ════════════════════════════════════════════════════════════════════════════
# Entry point (local dev only — Azure uses gunicorn)
# ════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('=' * 55)
    print('  VoxEmotion – Web App (Local Dev)')
    print('=' * 55)
    print(f'  URL     : http://127.0.0.1:{PORT}')
    print(f'  Outputs : {OUTPUT_DIR}')
    print('  Press Ctrl+C to stop')
    print('=' * 55 + '\n')
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=DEBUG,
        use_reloader=False
    )
