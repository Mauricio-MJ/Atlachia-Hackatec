"""Arranque de Atlachia: se ejecuta con iniciar.bat cada vez que se usa."""
import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser

from app import config
from utilidades import ENV, actualizar_librerias, error, leer_env, levantar_docker, salir, titulo


def copias_abiertas(inicio):
    """Busca ventanas de Atlachia ya abiertas: [(puerto, es_esta_misma_version_y_carpeta)]."""
    copias = []
    for p in range(inicio, inicio + 20):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/salud", timeout=1) as r:
                s = json.load(r)
        except Exception:
            continue
        if s.get("app") == "ok":
            misma = s.get("version") == config.VERSION and s.get("carpeta") == str(config.RAIZ)
            copias.append((p, misma))
    return copias


def cerrar_puerto(puerto):
    """Cierra el programa que escucha en ese puerto (sólo se usa con copias viejas de Atlachia)."""
    if os.name != "nt":
        return False
    salida = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True).stdout
    pids = set()
    for linea in salida.splitlines():
        c = linea.split()
        if len(c) >= 5 and c[1].endswith(f":{puerto}") and c[3].upper() in ("LISTENING", "ESCUCHANDO"):
            pids.add(c[4])
    ok = False
    for pid in pids:
        ok |= subprocess.run(["taskkill", "/PID", pid, "/F", "/T"], capture_output=True).returncode == 0
    return ok


def puerto_libre(inicio):
    """Devuelve el primer puerto libre desde 'inicio' (por si otro programa ya usa el 8000)."""
    for p in range(inicio, inicio + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return None


if not ENV.exists():
    error("Falta la configuración. Primero ejecuta instalar.bat.")
    salir(1)

deseado = int(leer_env().get("PUERTO_APP", "8000"))
copias = copias_abiertas(deseado)
misma = next((p for p, m in copias if m), None)
if misma:
    print(f"\n  Atlachia ya está abierto en http://127.0.0.1:{misma} (en otra ventana negra). Abriendo el navegador…", flush=True)
    webbrowser.open(f"http://127.0.0.1:{misma}")
    salir(0)
for p, _ in copias:   # copias viejas (de pasos anteriores u otra carpeta): se cierran para que no choquen con el bot
    print(f"  Cerrando una copia vieja de Atlachia en el puerto {p}…", flush=True)
    if not cerrar_puerto(p):
        error(f"No pude cerrar la copia vieja del puerto {p}. Reinicia la computadora y vuelve a abrir iniciar.bat.")
        salir(1)
if copias:
    time.sleep(2)
titulo("Atlachia · arrancando")
if not actualizar_librerias():
    salir(1)
if not levantar_docker():
    salir(1)

import uvicorn  # noqa: E402  (se importa después de revisar que existe el entorno)

from app import ia_fotos  # noqa: E402

if not ia_fotos.modelo_descargado():
    print("\n  Descargando el modelo de la IA de fotos (unos 150 MB, sólo la primera vez)…", flush=True)
    try:
        ia_fotos.descargar_modelo(lambda nombre, pct: print(f"\r    {nombre:<15} {pct:5.1f} %", end="", flush=True))
        print("\n  Modelo descargado.", flush=True)
    except Exception as e:
        print(f"\n  No se pudo descargar el modelo ({e}). Atlachia arranca sin IA de fotos;", flush=True)
        print("  se volverá a intentar la próxima vez que abras iniciar.bat con internet.", flush=True)

puerto = puerto_libre(deseado)
if puerto is None:
    error(f"Los puertos {deseado} a {deseado + 19} están ocupados. Cierra otras ventanas de Atlachia y vuelve a intentar.")
    salir(1)
if puerto != deseado:
    print(f"  (El puerto {deseado} lo usa otro programa; Atlachia usará el {puerto}.)", flush=True)
url = f"http://127.0.0.1:{puerto}"
print(f"\n  Atlachia en {url}  ·  para detenerlo cierra esta ventana o pulsa Ctrl + C\n", flush=True)
threading.Timer(2.5, lambda: webbrowser.open(url)).start()
uvicorn.run("app.main:app", host="127.0.0.1", port=puerto, log_level="warning")
