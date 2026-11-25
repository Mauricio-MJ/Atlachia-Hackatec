"""Funciones comunes de instalar.py e iniciar.py (solo librería estándar)."""
import hashlib
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ENV = RAIZ / ".env"


def titulo(texto):
    print(f"\n=== {texto} ===", flush=True)


def ok(texto):
    print(f"  [OK] {texto}", flush=True)


def error(texto):
    print(f"  [ERROR] {texto}", flush=True)


def leer_env():
    """Lee .env como diccionario (sin depender de librerías externas)."""
    datos = {}
    if ENV.exists():
        for linea in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip()
    return datos


def correr(cmd, **kw):
    return subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, **kw)


def docker_listo():
    """True si Docker Desktop está abierto y responde."""
    try:
        return correr(["docker", "info"]).returncode == 0
    except FileNotFoundError:
        return False


def levantar_docker():
    """Levanta los contenedores y espera a que la base esté lista."""
    if not docker_listo():
        error("Docker no responde. Abre Docker Desktop, espera a que diga 'Engine running' y vuelve a intentar.")
        return False
    print("  Levantando contenedores (la primera vez descarga y compila; puede tardar unos minutos)...", flush=True)
    r = subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=RAIZ)
    if r.returncode != 0:
        error("docker compose no pudo levantar los servicios (revisa el mensaje de arriba).")
        return False
    for _ in range(90):
        r = correr(["docker", "inspect", "--format", "{{.State.Health.Status}}", "atlachia_db"])
        if r.stdout.strip() == "healthy":
            ok("Base de datos lista (PostgreSQL + PostGIS)")
            return True
        time.sleep(2)
    error("La base de datos no terminó de arrancar. Revisa Docker Desktop > Containers > atlachia_db.")
    return False


def actualizar_librerias():
    """Si requirements.txt cambió desde la última vez, instala lo nuevo (sin intervención)."""
    req = RAIZ / "requirements.txt"
    marca = RAIZ / ".venv" / "requisitos.sha"
    huella = hashlib.sha256(req.read_bytes()).hexdigest()
    if marca.exists() and marca.read_text().strip() == huella:
        return True
    print("  Instalando librerías nuevas de esta versión...", flush=True)
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)], cwd=RAIZ)
    if r.returncode != 0:
        error("No se pudieron instalar las librerías nuevas (revisa tu internet).")
        return False
    marca.write_text(huella)
    ok("Librerías al día")
    return True


def salir(codigo=0):
    sys.exit(codigo)
