from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from datetime import datetime, timezone, timedelta 
import calendar
import json

# --- ADMİN GİRİŞ MƏLUMATLARI (İstədiyiniz kimi dəyişin) ---
ADMIN_USERNAME = "elshad"
ADMIN_PASSWORD = "3lsh@d"

# Azərbaycan vaxt zonası (UTC+4) təyin olundu
AZ_TZ = timezone(timedelta(hours=4))

app = Flask(__name__)
app.secret_key = "super_gizli_secret_key_bura_yazin"


# --- 1. MƏLUMAT BAZASININ QURULMASI ---
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# --- 2. SƏHİFƏLƏR VƏ MARŞRUTLAR (ROUTES) ---

@app.route('/')
def home():
    user_email = session.get('user_email')
    return render_template('index.html', email=user_email)


# Google Login Simulyasiyası
@app.route('/login-google', methods=['POST'])
def google_login():
    data = request.json
    session['user_email'] = data.get('email')
    return jsonify({"status": "success", "email": session['user_email']})


# Məkana görə girişi bazaya yazan API
@app.route('/api/check-in', methods=['POST'])
def check_in():
    email = session.get('user_email')
    if not email:
        return jsonify({"status": "error", "message": "İlk öncə Gmail ilə daxil olun!"}), 401

    data = request.json
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    now = datetime.now(AZ_TZ).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attendance (email, latitude, longitude, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (email, lat, lng, now))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Girişiniz uğurla qeydə alındı!"})


# --- 3. ADMİN GİRİŞ VƏ ÇIXIŞ MARŞRUTLARI ---

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


# --- 4. ADMİN PANEL VƏ AYLIQ TƏQVİM (QORUNAN SƏHİFƏ) ---
@app.route('/admin')
def admin_panel():
    # Admin giriş etməyibsə login səhifəsinə yönləndir
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    now = datetime.now(AZ_TZ)
    selected_date = request.args.get('date')          # Format: YYYY-MM-DD
    month_str = request.args.get('month_picker')      # Format: YYYY-MM

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
    
    days_in_month = []
    for day in range(1, num_days + 1):
        day_str = f"{year}-{month:02d}-{day:02d}"
        days_in_month.append({
            "day_number": day,
            "date_str": day_str
        })

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT email, latitude, longitude, timestamp 
        FROM attendance 
        WHERE timestamp LIKE ? 
        ORDER BY id DESC
    ''', (f"{selected_date}%",))

    records = cursor.fetchall()
    conn.close()

    return render_template(
        'admin.html', 
        records=records, 
        days=days_in_month, 
        selected_date=selected_date,
        current_month_str=f"{year}-{month:02d}"
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
