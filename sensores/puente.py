"""Puente de sensores de Atlachia (fase 2, simulada).

Corre los 5 simuladores C++ (uno por sensor DFRobot), lee cada línea JSON que imprimen
en el formato común y la guarda en la tabla 'observaciones'. Hace el papel que tendrá el
ESP32 en campo. También activa la "descarga simulada" cuando el operador la pide.
"""
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

import psycopg

BIN = Path(os.getenv("BIN_DIR", "/app/bin"))
DATABASE_URL = os.environ["DATABASE_URL"]
EVENTO = Path(os.getenv("EVENTO_ARCHIVO", "/tmp/atlachia_descarga"))
SIMULADORES = ["sen0189_turbidez", "sen0161_ph", "dfr0300_ec", "sen0237_do", "kit0021_temp"]
cola = queue.Queue()


def log(texto):
    print(time.strftime("%H:%M:%S"), texto, flush=True)


def correr_simulador(nombre):
    """Arranca un simulador y manda sus líneas a la cola; si se detiene, lo vuelve a arrancar."""
    while True:
        proc = subprocess.Popen([str(BIN / nombre)], stdout=subprocess.PIPE, text=True, env=os.environ)
        for linea in proc.stdout:
            cola.put(linea)
        log(f"{nombre} se detuvo; reiniciando en 2 s")
        time.sleep(2)


def conectar():
    """Espera a que la base exista y tenga las tablas (las crea la aplicación al arrancar)."""
    aviso = False
    while True:
        try:
            conn = psycopg.connect(DATABASE_URL, autocommit=True)
            ok = conn.execute("SELECT to_regclass('observaciones') IS NOT NULL AND "
                              "to_regclass('eventos_simulacion') IS NOT NULL").fetchone()[0]
            if ok:
                log("Conectado a la base de datos")
                return conn
            conn.close()
            if not aviso:
                log("Esperando a que la aplicación cree las tablas (abre iniciar.bat)...")
                aviso = True
        except psycopg.OperationalError:
            if not aviso:
                log("Esperando a la base de datos...")
                aviso = True
        time.sleep(3)


def guardar(conn, o):
    conn.execute(
        """INSERT INTO observaciones (fuente, sitio, fecha, parametro, valor, unidad, ubicacion, calidad)
           VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)""",
        (o["fuente"], o["sitio"], o["fecha"], o["parametro"], o["valor"], o["unidad"], o["lon"], o["lat"], o["calidad"]),
    )


def revisar_evento(conn):
    """Crea o borra el archivo que leen los simuladores según haya una descarga activa en la base."""
    activo = conn.execute("SELECT EXISTS (SELECT 1 FROM eventos_simulacion WHERE now() BETWEEN inicio AND fin)").fetchone()[0]
    if activo and not EVENTO.exists():
        EVENTO.touch()
        log("DESCARGA SIMULADA: activa")
    elif not activo and EVENTO.exists():
        EVENTO.unlink()
        log("Descarga simulada: terminó")


def main():
    log(f"Puente de sensores Atlachia · {len(SIMULADORES)} simuladores · cada {os.getenv('INTERVALO_S', '3')} s")
    EVENTO.unlink(missing_ok=True)
    conn = conectar()
    for nombre in SIMULADORES:
        threading.Thread(target=correr_simulador, args=(nombre,), daemon=True).start()
    ultimo_evento = 0.0
    while True:
        try:
            if time.time() - ultimo_evento > 1:
                revisar_evento(conn)
                ultimo_evento = time.time()
            try:
                linea = cola.get(timeout=1)
            except queue.Empty:
                continue
            try:
                o = json.loads(linea)
            except json.JSONDecodeError:
                log(f"Línea ignorada: {linea.strip()[:80]}")
                continue
            guardar(conn, o)
            log(f"{o['parametro']:<17} {o['valor']:>9} {o['unidad']:<6} {o['calidad']}")
        except psycopg.Error as e:
            log(f"Se perdió la base de datos ({type(e).__name__}); reconectando...")
            conn = conectar()


if __name__ == "__main__":
    main()
