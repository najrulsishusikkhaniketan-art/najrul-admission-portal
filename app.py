import os, io, csv, sqlite3, secrets, hmac, hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('ADMISSION_DB', os.path.join(BASE, 'admissions.db'))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(BASE, 'uploads'))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
ADMISSION_FEE = int(os.environ.get('ADMISSION_FEE_INR', '0'))
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'pdf'}

FIELDS = [
 ('student_name_bn','Student Name (Bengali)'), ('student_name_en','Student Name (English)'),
 ('dob','Date of Birth'), ('birth_reg_no','Birth Registration Number'), ('gender','Gender'), ('category','Social Category'),
 ('aadhaar','Aadhaar Number (optional)'), ('father_name_bn','Father’s Name (Bengali)'), ('father_name_en','Father’s Name (English)'),
 ('father_education','Father’s Educational Qualification'), ('father_phone','Father’s Phone Number'),
 ('mother_name_bn','Mother’s Name (Bengali)'), ('mother_name_en','Mother’s Name (English)'),
 ('mother_education','Mother’s Educational Qualification'), ('mother_phone','Mother’s Phone Number'),
 ('village','Village'), ('post_office','Post Office'), ('police_station','Police Station'), ('district','District'), ('pin','PIN Code'),
 ('guardian_name_address','Guardian’s Name and Address'), ('guardian_phone','Guardian’s Phone Number'), ('religion','Religion'),
 ('relationship_to_student','Relationship to Student'), ('father_guardian_occupation','Father/Guardian’s Occupation'),
 ('class_applied','Class Applying For'), ('previous_school_attended','Attended Another School?'), ('previous_school_name','Previous School Name'),
 ('admission_date_requested','Requested Admission Date'), ('school_van','School Van Required?'), ('photo_filename','Photo / Document Filename'),
 ('fee_amount','Admission Fee (INR)'), ('payment_status','Payment Status'), ('payment_reference','Payment Reference')
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, application_no TEXT UNIQUE, created_at TEXT,
            student_name_bn TEXT, student_name_en TEXT, dob TEXT, birth_reg_no TEXT, gender TEXT, category TEXT,
            aadhaar TEXT, father_name_bn TEXT, father_name_en TEXT, father_education TEXT, father_phone TEXT,
            mother_name_bn TEXT, mother_name_en TEXT, mother_education TEXT, mother_phone TEXT,
            village TEXT, post_office TEXT, police_station TEXT, district TEXT, pin TEXT,
            guardian_name_address TEXT, guardian_phone TEXT, religion TEXT, relationship_to_student TEXT,
            father_guardian_occupation TEXT, class_applied TEXT, previous_school_attended TEXT, previous_school_name TEXT,
            admission_date_requested TEXT, school_van TEXT, photo_filename TEXT, fee_amount INTEGER DEFAULT 0,
            payment_status TEXT DEFAULT 'Not Started', payment_reference TEXT DEFAULT '', status TEXT DEFAULT 'Submitted'
        )''')
        con.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, application_no TEXT, provider_order_id TEXT,
            provider_payment_id TEXT, amount INTEGER, status TEXT, created_at TEXT
        )''')
init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', fee=ADMISSION_FEE)

@app.route('/apply', methods=['POST'])
def apply():
    required = ['student_name_en', 'dob', 'gender', 'category', 'father_phone', 'class_applied', 'village', 'district', 'pin']
    missing = [k for k in required if not request.form.get(k, '').strip()]
    if missing:
        flash('Please complete all required fields marked with *.', 'error')
        return redirect(url_for('index') + '#application')
    photo_name = ''
    uploaded = request.files.get('photo')
    if uploaded and uploaded.filename:
        if not allowed_file(uploaded.filename):
            flash('Upload JPG, PNG, WEBP or PDF files only.', 'error')
            return redirect(url_for('index') + '#application')
        safe = secure_filename(uploaded.filename)
        photo_name = datetime.now().strftime('%Y%m%d%H%M%S%f') + '_' + safe
        uploaded.save(os.path.join(UPLOAD_DIR, photo_name))
    vals = {k: request.form.get(k, '').strip() for k, _ in FIELDS if k not in ('photo_filename','fee_amount','payment_status','payment_reference')}
    vals['photo_filename'] = photo_name
    vals['fee_amount'] = ADMISSION_FEE
    vals['payment_status'] = 'Pending' if ADMISSION_FEE > 0 else 'Not Required'
    vals['payment_reference'] = ''
    vals['created_at'] = datetime.now().isoformat(timespec='seconds')
    with db() as con:
        cur = con.execute('INSERT INTO applications (' + ','.join(vals.keys()) + ') VALUES (' + ','.join('?' for _ in vals) + ')', list(vals.values()))
        app_id = cur.lastrowid
        app_no = f'NSN-{datetime.now().strftime("%y%m")}-{app_id:05d}'
        con.execute('UPDATE applications SET application_no=? WHERE id=?', (app_no, app_id))
    return redirect(url_for('confirmation', app_no=app_no))

@app.route('/confirmation/<app_no>')
def confirmation(app_no):
    with db() as con:
        item = con.execute('SELECT * FROM applications WHERE application_no=?', (app_no,)).fetchone()
    if not item: abort(404)
    return render_template('confirmation.html', item=item, fee=ADMISSION_FEE, payment_enabled=bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET))

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if not ADMIN_PASSWORD:
            flash('Admin password is not configured. Set ADMIN_PASSWORD in the environment first.', 'error')
        elif hmac.compare_digest(request.form.get('username',''), ADMIN_USER) and hmac.compare_digest(request.form.get('password',''), ADMIN_PASSWORD):
            session['admin_logged_in'] = True
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        else:
            flash('Incorrect username or password.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    q = request.args.get('q','').strip()
    with db() as con:
        if q:
            like = '%' + q + '%'
            rows = con.execute('''SELECT * FROM applications WHERE application_no LIKE ? OR student_name_en LIKE ? OR father_phone LIKE ? ORDER BY id DESC''', (like,like,like)).fetchall()
        else:
            rows = con.execute('SELECT * FROM applications ORDER BY id DESC LIMIT 500').fetchall()
        total = con.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
        paid = con.execute("SELECT COUNT(*) FROM applications WHERE payment_status='Paid'").fetchone()[0]
    return render_template('admin_dashboard.html', rows=rows, total=total, paid=paid, q=q)

@app.route('/admin/application/<app_no>', methods=['GET','POST'])
@admin_required
def admin_application(app_no):
    with db() as con:
        item = con.execute('SELECT * FROM applications WHERE application_no=?', (app_no,)).fetchone()
        if not item: abort(404)
        if request.method == 'POST':
            status = request.form.get('status','Submitted')
            if status not in ('Submitted','Under Review','Accepted','Waitlisted','Rejected'): status='Submitted'
            con.execute('UPDATE applications SET status=? WHERE application_no=?', (status,app_no))
            flash('Application status updated.', 'success')
            return redirect(url_for('admin_application', app_no=app_no))
        item = con.execute('SELECT * FROM applications WHERE application_no=?', (app_no,)).fetchone()
    return render_template('admin_application.html', item=item, fields=FIELDS)

@app.route('/admin/export.csv')
@admin_required
def export_csv():
    with db() as con:
        rows = con.execute('SELECT * FROM applications ORDER BY id DESC').fetchall()
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows: writer.writerow(dict(row))
    data = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    return send_file(data, mimetype='text/csv', as_attachment=True, download_name='nazrul_admission_applications.csv')

@app.route('/uploads/<filename>')
@admin_required
def private_upload(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

# Online payments are intentionally not marked as paid until a real provider order,
# signature verification, and webhook are configured. Configure the Razorpay SDK and
# implement its server-side signature verification before production launch.
@app.route('/payment-not-ready')
def payment_not_ready():
    return render_template('payment_not_ready.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT','5000')), debug=False)
