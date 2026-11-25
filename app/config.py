"""Configuración de Atlachia: lee .env y define los lugares fijos de la presa."""
import os
from pathlib import Path

from dotenv import load_dotenv

VERSION = "0.7.1"   # iniciar.py la compara para no confundirse con una copia vieja abierta
RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DB_USUARIO = os.getenv("DB_USUARIO", "atlachia")
DB_CLAVE = os.getenv("DB_CLAVE", "")
DB_NOMBRE = os.getenv("DB_NOMBRE", "atlachia")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PUERTO = int(os.getenv("DB_PUERTO", "5433"))
DATABASE_URL = f"postgresql://{DB_USUARIO}:{DB_CLAVE}@{DB_HOST}:{DB_PUERTO}/{DB_NOMBRE}"

ZONA_HORARIA = "America/Mexico_City"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
PUERTO_APP = int(os.getenv("PUERTO_APP", "8000"))

# Zonas de la presa de Valsequillo para reportes ciudadanos (lat, lon reales)
ZONAS = [
    {"id": "Entrada del Atoyac", "lat": 18.948, "lon": -98.250},
    {"id": "Entrada del Alseseca", "lat": 18.943, "lon": -98.185},
    {"id": "Centro de la presa", "lat": 18.915, "lon": -98.178},
    {"id": "Brazo sur", "lat": 18.890, "lon": -98.185},
    {"id": "Cortina y obra de toma", "lat": 18.912, "lon": -98.112},
]

# Sitios oficiales de monitoreo de Conagua (RENAMECA) dentro de la presa
SITIOS_CONAGUA = [
    {"clave": "DLPUE2057", "nombre": "Presa Manuel Ávila Camacho 1", "lat": 18.92408, "lon": -98.19187},
    {"clave": "DLPUE2065", "nombre": "Presa Manuel Ávila Camacho 5", "lat": 18.912953, "lon": -98.175772},
    {"clave": "DLPUE2068", "nombre": "Presa Manuel Ávila Camacho 6", "lat": 18.904056, "lon": -98.16672},
    {"clave": "DLPUE2070", "nombre": "Obra de toma", "lat": 18.91253, "lon": -98.10851},
]

# Límites del recorte de los mapas satelitales (para colocar los puntos encima)
MAPA_LIMITES = {"lon_oeste": -98.2634, "lon_este": -98.0984, "lat_norte": 18.959, "lat_sur": 18.871}

# Datos de laboratorio de Conagua (Calidad del Agua Superficial 2025 y 2012–2025)
CONAGUA_2025 = {
    "DLPUE2057": {"sst_2025": 135.7, "sst_historica": 17, "coliformes_2025": 460000, "semaforo_2025": "Amarillo"},
    "DLPUE2065": {"sst_2025": 174.7, "sst_historica": 15, "coliformes_2025": 69498, "semaforo_2025": "Rojo"},
    "DLPUE2068": {"sst_2025": 20.5, "sst_historica": 12, "coliformes_2025": 102859, "semaforo_2025": "Rojo"},
    "DLPUE2070": {"sst_2025": 17.3, "sst_historica": 16, "coliformes_2025": 189737, "semaforo_2025": "Rojo"},
}

# Sensores DFRobot de la fase 2 (parámetro = nombre que usan los simuladores C++)
SENSORES = [
    {"sku": "SEN0189", "parametro": "turbidez", "modelo": "Gravity Analog Turbidity Sensor", "unidad": "NTU", "precio_usd": 9.90},
    {"sku": "SEN0161-V2", "parametro": "pH", "modelo": "Gravity Analog pH Sensor Kit V2", "unidad": "pH", "precio_usd": 39.50},
    {"sku": "DFR0300", "parametro": "conductividad", "modelo": "Gravity Analog EC Sensor K=1", "unidad": "mS/cm", "precio_usd": 69.90},
    {"sku": "SEN0237-A", "parametro": "oxigeno_disuelto", "modelo": "Gravity Analog Dissolved Oxygen Sensor", "unidad": "mg/L", "precio_usd": 169.00},
    {"sku": "KIT0021", "parametro": "temperatura", "modelo": "Gravity Waterproof DS18B20 Kit", "unidad": "°C", "precio_usd": 7.50},
]

DATOS = RAIZ / "datos"

# Nodo IoT simulado (fase 2): en la entrada del Atoyac
NODO_IOT = {"id": "NODO-01", "zona": "Entrada del Atoyac", "lat": 18.948, "lon": -98.250}
