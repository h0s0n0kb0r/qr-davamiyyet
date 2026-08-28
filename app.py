from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from datetime import datetime, timezone, timedelta
import calendar

# Admin Panel Giriş Məlumatları
ADMIN_USERNAME = "elshad"
ADMIN_PASSWORD = "Baku2025@"

# Azərbaycan Vaxt Qurşağı (UTC+4)
AZ_TZ = timezone(timedelta(hours=4))

app = Flask(__name__)
app.secret_key = "super_gizli_secret_key_bura_yazin"
app.permanent_session_lifetime = timedelta(days=90)


def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            device TEXT DEFAULT 'Bilinmir'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            registered_device TEXT
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN registered_device TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN name TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()


@app.route('/')
def home():
    user_email = session.get('user_email')
    user_name = session.get('user_name', '')
    if not user_email:
        return redirect(url_for('login_page'))
    return render_template('index.html', email=user_email, name=user_name)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return render_template('register.html', error="Bu Gmail adresi artıq qeydiyyatdan keçib!")

        cursor.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, password))
        conn.commit()
        conn.close()

        session.permanent = True
        session['user_email'] = email
        session['user_name'] = name
        return redirect(url_for('home'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute('SELECT email, name FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session.permanent = True
            session['user_email'] = user[0]
            session['user_name'] = user[1]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Gmail və ya şifrə yanlışdır!")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_name', None)
    return redirect(url_for('login_page'))


@app.route('/api/check-in', methods=['POST'])
def check_in():
    email = session.get('user_email')
    if not email:
        return jsonify({"status": "error", "message": "İlk öncə daxil olun!"}), 401

    data = request.json or {}
    lat = data.get('latitude')
    lng = data.get('longitude')
    client_device_id = data.get('device_id')

    if not client_device_id:
        return jsonify({"status": "error", "message": "Cihaz imzası tapılmadı! Səhifəni yeniləyin."}), 400

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    # 1. Bu cihaz artıq BAŞQA bir istifadəçiyə bağlanıbmı?
    cursor.execute('SELECT email, name FROM users WHERE registered_device = ? AND email != ?', (client_device_id, email))
    other_user = cursor.fetchone()
    if other_user:
        conn.close()
        return jsonify({
            "status": "error", 
            "message": f"❌ Bu telefon artıq başqa işçinin ({other_user[1]}) hesabına bağlıdır! Eyni cihazdan başqasının yerinə giriş etmək qadağandır."
        }), 403

    # 2. İstifadəçinin öz qeydiyyatlı cihazını yoxlayırıq
    cursor.execute('SELECT name, registered_device FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "İstifadəçi tapılmadı!"}), 404

    user_name, saved_device_id = row[0], row[1]

    # Əgər hesaba cihaz hələ bağlanmayıbsa, bu cihazı bağlayırıq
    if not saved_device_id:
        cursor.execute('UPDATE users SET registered_device = ? WHERE email = ?', (client_device_id, email))
    elif saved_device_id != client_device_id:
        conn.close()
        return jsonify({
            "status": "error", 
            "message": "❌ Bu hesab başqa cihaza bağlıdır! Yalnız öz telefonunuzdan giriş edə bilərsiniz."
        }), 403

    now = datetime.now(AZ_TZ).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT INTO attendance (name, email, latitude, longitude, timestamp, device)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_name, email, lat, lng, now, client_device_id))
    
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Girişiniz uğurla qeydə alındı!"})


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            error = "İstifadəçi adı və ya şifrə yanlışdır!"
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    now = datetime.now(AZ_TZ)
    selected_date = request.args.get('date')
    month_str = request.args.get('month_picker')

    if selected_date:
        parts = selected_date.split('-')
        year, month = int(parts[0]), int(parts[1])
    elif month_str:
        parts = month_str.split('-')
        year, month = int(parts[0]), int(parts[1])
        selected_date = f"{year}-{month:02d}-01"
    else:
        year, month = now.year, now.month
        selected_date = now.strftime("%Y-%m-%d")

    num_days = calendar.monthrange(year, month)[1]
    days_in_month = [{"day_number": d, "date_str": f"{year}-{month:02d}-{d:02d}"} for d in range(1, num_days + 1)]

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Seçilmiş günün qeydləri
    cursor.execute('''
        SELECT name, email, latitude, longitude, timestamp, device 
        FROM attendance 
        WHERE timestamp LIKE ? 
        ORDER BY id DESC
    ''', (f"{selected_date}%",))
    records = cursor.fetchall()

    # Qeydiyyatlı işçilərin siyahısı
    cursor.execute('SELECT name, email, registered_device FROM users')
    registered_users = cursor.fetchall()
    conn.close()

    # Günün qeydlərində təkrar olunan cihaz ID-lərini tapırıq (fərqli emaillər tərəfindən istifadə edilən)
    device_emails_today = {}
    for r in records:
        dev = r[5]
        em = r[1]
        if dev and dev != 'Bilinmir':
            if dev not in device_emails_today:
                device_emails_today[dev] = set()
            device_emails_today[dev].add(em)
    
    # Birdən çox fərqli email tərəfindən istifadə edilən cihaz ID-ləri
    flagged_devices = {dev for dev, emails in device_emails_today.items() if len(emails) > 1}

    # Qeydiyyatlı istifadəçilər arasında da təkrar cihazları tapırıq
    user_devices = {}
    for u in registered_users:
        dev = u[2]
        if dev:
            user_devices[dev] = user_devices.get(dev, 0) + 1
    flagged_registered_devices = {dev for dev, count in user_devices.items() if count > 1}

    return render_template(
        'admin.html', 
        records=records, 
        days=days_in_month, 
        selected_date=selected_date,
        current_month_str=f"{year}-{month:02d}",
        registered_users=registered_users,
        flagged_devices=flagged_devices,
        flagged_registered_devices=flagged_registered_devices
    )


@app.route('/admin/reset-device/<email>', methods=['POST'])
def reset_device(email):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET registered_device = NULL WHERE email = ?', (email,))
    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for('admin_panel'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
