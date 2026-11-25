"""Instalación de Atlachia: se ejecuta una sola vez con instalar.bat."""
import getpass
import secrets
import subprocess
import sys
import venv

from utilidades import ENV, RAIZ, error, leer_env, levantar_docker, ok, salir, titulo

VENV = RAIZ / ".venv"
PY_VENV = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

titulo("1/4 Revisando Python")
if sys.version_info < (3, 10):
    error(f"Tienes Python {sys.version.split()[0]}; se necesita 3.10 o más nuevo.")
    salir(1)
ok(f"Python {sys.version.split()[0]}")

titulo("2/4 Entorno e instalación de librerías")
if not PY_VENV.exists():
    print("  Creando entorno virtual .venv ...", flush=True)
    venv.create(VENV, with_pip=True)
ok("Entorno .venv")
r = subprocess.run([str(PY_VENV), "-m", "pip", "install", "--upgrade", "pip", "-q"])
r = subprocess.run([str(PY_VENV), "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")])
if r.returncode != 0:
    error("No se pudieron instalar las librerías (revisa tu internet y el mensaje de arriba).")
    salir(1)
ok("Librerías instaladas")

titulo("3/4 Configuración (.env)")
datos = leer_env()
nuevo = not ENV.exists()
datos.setdefault("DB_USUARIO", "atlachia")
datos.setdefault("DB_CLAVE", secrets.token_urlsafe(18))
datos.setdefault("DB_NOMBRE", "atlachia")
datos.setdefault("DB_PUERTO", "5433")
datos.setdefault("PGADMIN_CLAVE", secrets.token_urlsafe(12))
datos.setdefault("PUERTO_APP", "8000")
datos.setdefault("TELEGRAM_TOKEN", "")
if not datos["TELEGRAM_TOKEN"]:
    print("  Pega el token del bot de Telegram (el de @BotFather) y pulsa Enter.")
    print("  No se verá mientras lo pegas. Si no lo tienes a la mano, solo pulsa Enter.")
    datos["TELEGRAM_TOKEN"] = getpass.getpass("  Token: ").strip()
ENV.write_text(
    "# Atlachia · configuración local. NO compartas ni subas este archivo.\n"
    + "".join(f"{k}={v}\n" for k, v in datos.items()),
    encoding="utf-8",
)
ok(".env " + ("creado" if nuevo else "actualizado") + (" · token guardado" if datos["TELEGRAM_TOKEN"] else " · sin token (puedes volver a correr instalar.bat)"))

titulo("4/4 Base de datos en Docker")
if not levantar_docker():
    salir(1)

titulo("Listo")
print("  Para usar Atlachia: doble clic en iniciar.bat")
print("  pgAdmin (opcional): http://127.0.0.1:5051  ·  usuario admin@example.com")
print(f"  Contraseña de pgAdmin: {datos['PGADMIN_CLAVE']}")
