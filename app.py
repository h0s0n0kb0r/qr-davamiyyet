from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from datetime import datetime, timezone, timedelta
import calendar
import json

# ==============================================================================
# SİSTEM TƏNZİMLƏMƏLƏRİ
# ==============================================================================

# Admin Panel Giriş Məlumatları (İstədiyiniz kimi dəyişə bilərsiniz)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123"

# Azərbaycan Vaxt Qurşağı (UTC+4)
AZ_TZ = timezone(timedelta(hours=4))

app = Flask(__name__)
app.secret_key = "super_gizli_secret_key_bura_yazin"


# ==============================================================================
# CİHAZ (TELEFON MARKASI) TƏYİN EDƏN FUNKSİYA
# ==============================================================================

def detect_device(user_agent_str):
    ua = user_agent_str.lower()
    if "iphone" in ua:
        return "📱 Apple iPhone"
    elif "ipad" in ua:
        return "📱 Apple iPad"
    elif "samsung" in ua:
        return "📱 Samsung"
    elif "redmi" in ua:
        return "📱 Xiaomi Redmi"
    elif "xiaomi" in ua or "mi " in ua:
        return "📱 Xiaomi"
    elif "huawei" in ua or "honor" in ua:
        return "📱 Huawei / Honor"
    elif "pixel" in ua:
        return "📱 Google Pixel"
    elif "oppo" in ua:
        return "📱 OPPO"
    elif "vivo" in ua:
        return "📱 Vivo"
    elif "android" in ua:
        return "📱 Android Telefon"
    elif "windows" in ua:
        return "💻 Windows Kompüter"
    elif "macintosh" in ua or "mac os" in ua:
        return "💻 Mac Kompüter"
    else:
        return "❓ Məlum Olmayan Cihaz"


# ==============================================================================
# MƏLUMAT BAZASININ QURULMASI
# ==============================================================================

def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Davamiyyət Cədvəli (device sütunu əlavə olundu)
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
    
    conn.commit()
    conn.close()

init_db()


# ==============================================================================
# SƏHİFƏLƏR VƏ MARŞRUTLAR
# ==============================================================================

@app.route('/')
def home():
    user_email = session.get('user_email')
    return render_template('index.html', email=user_email)


# Google Login / Email Saxlama
@app.route('/login-google', methods=['POST'])
def google_login():
    data = request.json
    session['user_email'] = data.get('email')
    return jsonify({"status": "success", "email": session['user_email']})


# Məkana və Cihaza Görə Girişi Bazaya Yazacaq API
@app.route('/api/check-in', methods=['POST'])
def check_in():
    email = session.get('user_email')
    if not email:
        return jsonify({"status": "error", "message": "İlk öncə Gmail ilə daxil olun!"}), 401

    data = request.json
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    # Bakı vaxtı ilə saat
    now = datetime.now(AZ_TZ).strftime("%Y-%m-%d %H:%M:%S")

    # Telefon markasını / cihazı təyin edirik
    user_agent = request.headers.get('User-Agent', '')
    device_name = detect_device(user_agent)

    # Bazaya qeyd edirik
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attendance (email, latitude, longitude, timestamp, device)
        VALUES (?, ?, ?, ?, ?)
    ''', (email, lat, lng, now, device_name))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Girişiniz uğurla qeydə alındı!"})


# ==============================================================================
# ADMİN PANEL MARŞRUTLARI (Login, Logout, Təqvim & Cədvəl)
# ==============================================================================

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
