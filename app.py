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
    
    # Əgər əvvəldən yaranmış bazadırsa və sütun yoxdursa əlavə edirik
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN registered_device TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()


@app.route('/')
def home():
    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('login_page'))
    return render_template('index.html', email=user_email)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        name = request.form.get('name')
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
        return redirect(url_for('home'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute('SELECT email FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session.permanent = True
            session['user_email'] = user[0]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Gmail və ya şifrə yanlışdır!")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_email', None)
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

    # İstifadəçinin qeydiyyatlı cihazını yoxlayırıq
    cursor.execute('SELECT registered_device FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "İstifadəçi tapılmadı!"}), 404

    saved_device_id = row[0]

    # Əgər ilk girişdirsə, bu cihazı hesaba bağlayırıq
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
        INSERT INTO attendance (email, latitude, longitude, timestamp, device)
        VALUES (?, ?, ?, ?, ?)
    ''', (email, lat, lng, now, client_device_id))
    
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
    cursor.execute('''
        SELECT email, latitude, longitude, timestamp, device 
        FROM attendance 
        WHERE timestamp LIKE ? 
        ORDER BY id DESC
    ''', (f"{selected_date}%",))
    records = cursor.fetchall()

    # Qeydiyyatlı işçilərin cihaz siyahısı (Sıfırlamaq üçün)
    cursor.execute('SELECT email, registered_device FROM users')
    registered_users = cursor.fetchall()
    conn.close()

    return render_template(
        'admin.html', 
        records=records, 
        days=days_in_month, 
        selected_date=selected_date,
        current_month_str=f"{year}-{month:02d}",
        registered_users=registered_users
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
