import os, secrets, uuid, shutil
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ROOT = os.path.dirname(__file__)

# ── Database setup: PostgreSQL (Render) yoki SQLite (local) ──────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    # Render bergan URL ba'zan "postgres://" bilan keladi, psycopg2 "postgresql://" talab qiladi
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    def db():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    PH = '%s'  # PostgreSQL placeholder
else:
    import sqlite3
    DB_PATH = os.path.join(ROOT, 'data.sqlite3')
    def db():
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        return c
    PH = '?'  # SQLite placeholder

# ── Upload dir: localda static/uploads ────────────────────────────────────────
UPLOAD_DIR = os.path.join(ROOT, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=35 * 1024 * 1024
)

# ── DB init ────────────────────────────────────────────────────────────────────
def init():
    with db() as conn:
        if USE_PG:
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS teachers(
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, subject TEXT NOT NULL,
                bio TEXT NOT NULL, image TEXT NOT NULL DEFAULT '')''')
            cur.execute('''CREATE TABLE IF NOT EXISTS plans(
                id SERIAL PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                description TEXT NOT NULL, duration TEXT NOT NULL DEFAULT '',
                file TEXT NOT NULL DEFAULT '', file_name TEXT NOT NULL DEFAULT '')''')
            cur.execute('''CREATE TABLE IF NOT EXISTS admins(
                id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT NOT NULL)''')
            cur.execute("SELECT COUNT(*) FROM admins")
            if cur.fetchone()['count'] == 0:
                pwd = os.environ.get('ADMIN_PASSWORD')
                if not pwd:
                    pwd = secrets.token_urlsafe(12)
                    print(f'\n*** FIRST ADMIN PASSWORD: {pwd} ***\n', flush=True)
                cur.execute("INSERT INTO admins(username,password) VALUES(%s,%s)",
                            ('admin', generate_password_hash(pwd)))
            conn.commit()
        else:
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS teachers(
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, subject TEXT NOT NULL,
                bio TEXT NOT NULL, image TEXT NOT NULL DEFAULT "")''')
            cur.execute('''CREATE TABLE IF NOT EXISTS plans(
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                description TEXT NOT NULL, duration TEXT NOT NULL DEFAULT "",
                file TEXT NOT NULL DEFAULT "", file_name TEXT NOT NULL DEFAULT "")''')
            cur.execute('''CREATE TABLE IF NOT EXISTS admins(
                id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT NOT NULL)''')
            # Migration: add file columns if missing
            cols = [r[1] for r in cur.execute('PRAGMA table_info(plans)').fetchall()]
            if 'file' not in cols:
                cur.execute('ALTER TABLE plans ADD COLUMN file TEXT NOT NULL DEFAULT ""')
            if 'file_name' not in cols:
                cur.execute('ALTER TABLE plans ADD COLUMN file_name TEXT NOT NULL DEFAULT ""')
            if not cur.execute('SELECT COUNT(*) FROM admins').fetchone()[0]:
                pwd = os.environ.get('ADMIN_PASSWORD')
                if not pwd:
                    pwd = secrets.token_urlsafe(12)
                    print(f'\n*** FIRST ADMIN PASSWORD: {pwd} ***\n', flush=True)
                cur.execute('INSERT INTO admins(username,password) VALUES(?,?)',
                            ('admin', generate_password_hash(pwd)))
            conn.commit()

init()

# ── Auth decorator ─────────────────────────────────────────────────────────────
def auth(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('admin'):
            return jsonify(error='Admin login talab qilinadi'), 401
        return fn(*args, **kwargs)
    return wrapped

# ── Helper: fetch rows as list of dicts ───────────────────────────────────────
def fetchall(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def fetchone(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get('/')
def home(): return send_from_directory(ROOT, 'index.html')

@app.get('/admin')
def admin_page(): return send_from_directory(ROOT, 'admin.html')

@app.post('/api/login')
def login():
    x = request.get_json(silent=True) or {}
    with db() as conn:
        row = fetchone(conn, f'SELECT * FROM admins WHERE username={PH}', (x.get('username', ''),))
    if not row or not check_password_hash(row['password'], x.get('password', '')):
        return jsonify(error="Login yoki parol noto'g'ri"), 401
    session.clear()
    session['admin'] = row['id']
    return jsonify(ok=True)

@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get('/api/me')
def me():
    return jsonify(admin=bool(session.get('admin')))

@app.route('/api/<kind>', methods=['GET', 'POST'])
def collection(kind):
    if kind not in ('teachers', 'plans'):
        return jsonify(error='Not found'), 404
    if request.method == 'GET':
        with db() as conn:
            rows = fetchall(conn, f'SELECT * FROM {kind} ORDER BY id DESC')
        return jsonify(rows)
    if not session.get('admin'):
        return jsonify(error='Unauthorized'), 401
    x = request.get_json(silent=True) or {}
    if kind == 'teachers':
        if not str(x.get('name', '')).strip(): return jsonify(error='Ustoz ism-familiyasini kiriting'), 400
        if not str(x.get('subject', '')).strip(): return jsonify(error='Ustoz fani nomini kiriting'), 400
        if not str(x.get('bio', '')).strip(): return jsonify(error='Ustoz haqida qisqa ma\'lumot kiriting'), 400
        fields = ['name', 'subject', 'bio', 'image']
    else:
        if not str(x.get('title', '')).strip(): return jsonify(error='Reja nomini kiriting'), 400
        if not str(x.get('category', '')).strip(): return jsonify(error='Yo\'nalish yoki fanni kiriting'), 400
        if not str(x.get('description', '')).strip(): return jsonify(error='Reja haqida ma\'lumot kiriting'), 400
        fields = ['title', 'category', 'description', 'duration', 'file', 'file_name']
    vals = [str(x.get(f, ''))[:1200] for f in fields]
    placeholders = ', '.join(PH for _ in fields)
    col_str = ', '.join(fields)
    with db() as conn:
        cur = conn.cursor()
        if USE_PG:
            cur.execute(f'INSERT INTO {kind} ({col_str}) VALUES ({placeholders}) RETURNING id', vals)
            new_id = cur.fetchone()['id']
        else:
            cur.execute(f'INSERT INTO {kind} ({col_str}) VALUES ({placeholders})', vals)
            new_id = cur.lastrowid
        conn.commit()
    return jsonify(id=new_id), 201

@app.route('/api/<kind>/<int:item_id>', methods=['PUT', 'DELETE'])
@auth
def item(kind, item_id):
    if kind not in ('teachers', 'plans'):
        return jsonify(error='Not found'), 404
    with db() as conn:
        cur = conn.cursor()
        if request.method == 'DELETE':
            cur.execute(f'DELETE FROM {kind} WHERE id={PH}', (item_id,))
            conn.commit()
            return jsonify(ok=True)
        x = request.get_json(silent=True) or {}
        if kind == 'teachers':
            if not str(x.get('name', '')).strip(): return jsonify(error='Ustoz ism-familiyasini kiriting'), 400
            if not str(x.get('subject', '')).strip(): return jsonify(error='Ustoz fani nomini kiriting'), 400
            if not str(x.get('bio', '')).strip(): return jsonify(error='Ustoz haqida qisqa ma\'lumot kiriting'), 400
            fields = ['name', 'subject', 'bio', 'image']
        else:
            if not str(x.get('title', '')).strip(): return jsonify(error='Reja nomini kiriting'), 400
            if not str(x.get('category', '')).strip(): return jsonify(error='Yo\'nalish yoki fanni kiriting'), 400
            if not str(x.get('description', '')).strip(): return jsonify(error='Reja haqida ma\'lumot kiriting'), 400
            fields = ['title', 'category', 'description', 'duration', 'file', 'file_name']
        vals = [str(x.get(f, ''))[:1200] for f in fields]
        set_str = ', '.join(f + f'={PH}' for f in fields)
        cur.execute(f'UPDATE {kind} SET {set_str} WHERE id={PH}', vals + [item_id])
        conn.commit()
    return jsonify(ok=True)

@app.post('/api/upload')
@auth
def upload():
    f = request.files.get('file')
    if not f:
        return jsonify(error='Fayl tanlanmagan'), 400
    raw_name = f.filename or 'fayl'
    ext = os.path.splitext(raw_name)[1].lower()
    allowed_img = ('.jpg', '.jpeg', '.png', '.webp')
    allowed_doc = ('.pdf', '.docx', '.doc', '.pptx', '.ppt')
    if ext not in allowed_img and ext not in allowed_doc:
        return jsonify(error='Faqat rasm (JPG, PNG, WEBP) yoki hujjat (PDF, DOCX, PPTX) yuklash mumkin'), 400
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if ext in allowed_img:
        from PIL import Image
        try:
            img = Image.open(f.stream)
            img.verify()
            f.stream.seek(0)
            img = Image.open(f.stream)
            img.thumbnail((1200, 1200))
            name = uuid.uuid4().hex + '.webp'
            img.convert('RGB').save(os.path.join(UPLOAD_DIR, name), 'WEBP', quality=86)
            return jsonify(url='/static/uploads/' + name, name=raw_name, type='image')
        except Exception:
            return jsonify(error='Rasmni o\'qib bo\'lmadi'), 400
    else:
        try:
            name = uuid.uuid4().hex + ext
            f.save(os.path.join(UPLOAD_DIR, name))
            return jsonify(url='/static/uploads/' + name, name=raw_name, type='doc', ext=ext)
        except Exception:
            return jsonify(error='Hujjatni saqlashda xatolik yuz berdi'), 400

@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')))
