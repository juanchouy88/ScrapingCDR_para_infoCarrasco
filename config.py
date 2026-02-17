import os
import json

# --- 1. CREDENCIALES Y ACCESOS ---
# Si vas a probar en TU PC, puedes poner las claves entre las comillas.
# Si lo subes a GitHub, DÉJALAS VACÍAS (leerá de los Secrets automáticamente).

CDR_USER = os.getenv("CDR_USER", "")  # Ej: "juan@empresa.com"
CDR_PASS = os.getenv("CDR_PASS", "")  # Ej: "Contraseña123"

WOO_URL = os.getenv("WOO_URL", "")    # Ej: "https://mitienda.com"
WOO_KEY = os.getenv("WOO_KEY", "")    # Ej: "ck_xxxxxxxxxxxx"
WOO_SECRET = os.getenv("WOO_SECRET", "") # Ej: "cs_xxxxxxxxxxxx"

# --- 2. CONFIGURACIÓN DE PRECIOS (¡ESTO FALTABA!) ---
# Estas son las variables que usará woo_manager.py para calcular precios.
IVA_RATE = 1.22    # 22% de IVA
MARGIN_RATE = 1.30 # 30% de Ganancia
# Fórmula final: (Precio * 1.22) * 1.30

# --- 3. LISTA DE URLS A ESCANEAR ---
# Intenta leer la lista desde GitHub Actions (formato texto).
# Si falla o está vacío, usa una lista vacía por defecto.
urls_env = os.getenv("TARGET_URLS", '[]')

try:
    TARGET_URLS = json.loads(urls_env)
except (json.JSONDecodeError, TypeError):
    print("⚠️  No se detectaron URLs en las variables de entorno.")
    TARGET_URLS = []

# --- 4. VALIDACIÓN DE SEGURIDAD ---
# Pequeña comprobación para avisarte si faltan datos al arrancar.
if not CDR_USER or not WOO_KEY:
    print("⚠️  AVISO: Faltan credenciales en config.py. El script podría fallar al loguearse.")