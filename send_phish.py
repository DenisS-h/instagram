import requests
import json
import sys

def send_email(target_email, target_username):
    url = "http://127.0.0.1:8080/email-validator"
    data = {
        "email": target_email,
        "username": target_username
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"✅ Éxito: Correo enviado a {target_email}")
            print(response.json())
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("⚠️  Asegúrate de que 'app.py' esté ejecutándose en otra terminal.")

if __name__ == "__main__":
    print("--- 📨 Enviar Correo de Phishing Educativo ---")
    
    # Solo pedir el correo electrónico
    if len(sys.argv) < 2:
        email = input("Introduce el correo electrónico del objetivo: ").strip()
    else:
        email = sys.argv[1]

    if email:
        # Extraer un nombre de usuario básico del correo (lo que está antes del @)
        user = email.split('@')[0]
        send_email(email, user)
    else:
        print("❌ Error: Debes proporcionar un correo electrónico.")
