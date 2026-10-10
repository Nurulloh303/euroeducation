import os,sqlite3,secrets,uuid,shutil
from functools import wraps
from flask import Flask,request,jsonify,send_from_directory,session
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
ROOT=os.path.dirname(__file__)
IS_VERCEL=bool(os.environ.get('VERCEL'))
if IS_VERCEL:
 TMP='/tmp'
 DB=os.path.join(TMP,'data.sqlite3')
 orig_db=os.path.join(ROOT,'data.sqlite3')
 if not os.path.exists(DB) and os.path.exists(orig_db):
  try:shutil.copy2(orig_db,DB)
  except Exception:pass
 UPLOAD_DIR=os.path.join(TMP,'uploads')
else:
 DB=os.path.join(ROOT,'data.sqlite3')
 UPLOAD_DIR=os.path.join(ROOT,'static','uploads')
os.makedirs(UPLOAD_DIR,exist_ok=True)
app=Flask(__name__,static_folder='static',static_url_path='/static')
app.secret_key=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',MAX_CONTENT_LENGTH=35*1024*1024)
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 with db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS teachers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,subject TEXT NOT NULL,bio TEXT NOT NULL,image TEXT NOT NULL DEFAULT "")')
  c.execute('CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,duration TEXT NOT NULL DEFAULT "")')
  c.execute('CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT NOT NULL)')
  cols=[r[1] for r in c.execute('PRAGMA table_info(plans)').fetchall()]
  if 'file' not in cols:c.execute('ALTER TABLE plans ADD COLUMN file TEXT NOT NULL DEFAULT ""')
  if 'file_name' not in cols:c.execute('ALTER TABLE plans ADD COLUMN file_name TEXT NOT NULL DEFAULT ""')
  if not c.execute('SELECT COUNT(*) FROM admins').fetchone()[0]:
   pwd=os.environ.get('ADMIN_PASSWORD')
   if not pwd: pwd=secrets.token_urlsafe(12);print('\n*** FIRST ADMIN PASSWORD:',pwd,'***\n',flush=True)
   c.execute('INSERT INTO admins(username,password) VALUES(?,?)',('admin',generate_password_hash(pwd)))
init()
def auth(fn):
 @wraps(fn)
 def wrapped(*args,**kwargs):
  if not session.get('admin'):return jsonify(error='Admin login talab qilinadi'),401
  return fn(*args,**kwargs)
 return wrapped
@app.get('/')
def home():return send_from_directory(ROOT,'index.html')
@app.get('/admin')
def admin():return send_from_directory(ROOT,'admin.html')
@app.post('/api/login')
def login():
 x=request.get_json(silent=True) or {};c=db();row=c.execute('SELECT * FROM admins WHERE username=?',(x.get('username',''),)).fetchone();c.close()
 if not row or not check_password_hash(row['password'],x.get('password','')):return jsonify(error='Login yoki parol noto‘g‘ri'),401
 session.clear();session['admin']=row['id'];return jsonify(ok=True)
@app.post('/api/logout')
def logout():session.clear();return jsonify(ok=True)
@app.get('/api/me')
def me():return jsonify(admin=bool(session.get('admin')))
@app.route('/api/<kind>',methods=['GET','POST'])
def collection(kind):
 if kind not in ('teachers','plans'):return jsonify(error='Not found'),404
 if request.method=='GET':
  with db() as c:return jsonify([dict(x) for x in c.execute(f'SELECT * FROM {kind} ORDER BY id DESC')])
 if not session.get('admin'):return jsonify(error='Unauthorized'),401
 x=request.get_json(silent=True) or {};fields=['name','subject','bio','image'] if kind=='teachers' else ['title','category','description','duration','file','file_name']
 if any(not str(x.get(f,'')).strip() for f in fields[:3]):return jsonify(error='Majburiy maydonlarni to‘ldiring'),400
 vals=[str(x.get(f,''))[:1200] for f in fields]
 with db() as c:
  cur=c.execute(f'INSERT INTO {kind} ({",".join(fields)}) VALUES ({",".join("?" for _ in fields)})',vals)
  return jsonify(id=cur.lastrowid),201
@app.route('/api/<kind>/<int:item_id>',methods=['PUT','DELETE'])
@auth
def item(kind,item_id):
 if kind not in ('teachers','plans'):return jsonify(error='Not found'),404
 with db() as c:
  if request.method=='DELETE':c.execute(f'DELETE FROM {kind} WHERE id=?',(item_id,));return jsonify(ok=True)
  x=request.get_json(silent=True) or {};fields=['name','subject','bio','image'] if kind=='teachers' else ['title','category','description','duration','file','file_name']
  if any(not str(x.get(f,'')).strip() for f in fields[:3]):return jsonify(error='Majburiy maydonlarni to‘ldiring'),400
  vals=[str(x.get(f,''))[:1200] for f in fields];c.execute(f'UPDATE {kind} SET {",".join(f+"=?" for f in fields)} WHERE id=?',vals+[item_id]);return jsonify(ok=True)
@app.post('/api/upload')
@auth
def upload():
 f=request.files.get('file')
 if not f:return jsonify(error='Fayl tanlanmagan'),400
 fname=secure_filename(f.filename) or 'file'
 ext=os.path.splitext(fname)[1].lower()
 allowed_img=('.jpg','.jpeg','.png','.webp')
 allowed_doc=('.pdf','.docx','.doc','.pptx','.ppt')
 if ext not in allowed_img and ext not in allowed_doc:
  return jsonify(error='Faqat rasm (JPG, PNG, WEBP) yoki hujjat (PDF, DOCX, PPTX) yuklash mumkin'),400
 os.makedirs(UPLOAD_DIR,exist_ok=True)
 if ext in allowed_img:
  from PIL import Image
  try:
   img=Image.open(f.stream);img.verify();f.stream.seek(0)
   img=Image.open(f.stream);img.thumbnail((1200,1200));name=uuid.uuid4().hex+'.webp';img.convert('RGB').save(os.path.join(UPLOAD_DIR,name),'WEBP',quality=86)
   return jsonify(url='/static/uploads/'+name,name=f.filename,type='image')
  except Exception:return jsonify(error='Rasmni o‘qib bo‘lmadi'),400
 else:
  try:
   name=uuid.uuid4().hex+ext
   f.save(os.path.join(UPLOAD_DIR,name))
   return jsonify(url='/static/uploads/'+name,name=f.filename,type='doc',ext=ext)
  except Exception:return jsonify(error='Hujjatni saqlashda xatolik yuz berdi'),400
@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
 if os.path.exists(os.path.join(UPLOAD_DIR,filename)):return send_from_directory(UPLOAD_DIR,filename)
 return send_from_directory(os.path.join(ROOT,'static','uploads'),filename)
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')))
