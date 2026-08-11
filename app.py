from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from datetime import datetime, timezone, timedelta 
import calendar
import json

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
    # İşçinin daxil olduğu əsas səhifə
    user_email = session.get('user_email')
    return render_template('index.html', email=user_email)


# Fake/Simulyasiya edilmiş Google Login (Test üçün)
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
    
    # Bakı saatı ilə qeyd
    now = datetime.now(AZ_TZ).strftime("%Y-%m-%d %H:%M:%S")

    # Bazaya qeyd edirik
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attendance (email, latitude, longitude, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (email, lat, lng, now))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Girişiniz uğurla qeydə alındı!"})


# --- 3. ADMİN PANEL VƏ AYLIQ TƏQVİM ---
@app.route('/admin')
def admin_panel():
    selected_date = request.args.get('date')  # Format: YYYY-MM-DD
    
    # Cari vaxt, il və ay
    now = datetime.now(AZ_TZ)
    year = request.args.get('year', type=int, default=now.year)
    month = request.args.get('month', type=int, default=now.month)
    
    # Ayın neçə gündən ibarət olduğunu hesablayırıq
    num_days = calendar.monthrange(year, month)[1]
    
    # Ayın bütün tarixlərini siyahı şəklində hazırlayırıq
    days_in_month = []
    for day in range(1, num_days + 1):
        day_str = f"{year}-{month:02d}-{day:02d}"
        days_in_month.append({
            "day_number": day,
            "date_str": day_str
        })

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    if selected_date:
        cursor.execute('''
            SELECT email, latitude, longitude, timestamp 
            FROM attendance 
            WHERE timestamp LIKE ? 
            ORDER BY id DESC
        ''', (f"{selected_date}%",))
    else:
        # Əgər tarix seçilməyibsə, defolt olaraq bugünkü qeydləri göstərir
        today_str = now.strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT email, latitude, longitude, timestamp 
            FROM attendance 
            WHERE timestamp LIKE ? 
            ORDER BY id DESC
        ''', (f"{today_str}%",))
        selected_date = today_str

    records = cursor.fetchall()
    conn.close()

    return render_template(
        'admin.html', 
        records=records, 
        days=days_in_month, 
        selected_date=selected_date,
        current_month=f"{year}-{month:02d}"
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
