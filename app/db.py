"""Conexión a PostgreSQL + PostGIS."""
import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL, ZONA_HORARIA


def conectar():
    """Abre una conexión que devuelve filas como diccionarios."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5,
                           options=f"-c TimeZone={ZONA_HORARIA}")


def estado_base():
    """Revisa que la base responda y que PostGIS esté activo."""
    try:
        with conectar() as conn:
            pg = conn.execute("SHOW server_version").fetchone()["server_version"]
            gis = conn.execute("SELECT PostGIS_Lib_Version() AS v").fetchone()["v"]
        return {"estado": "ok", "postgresql": pg, "postgis": gis}
    except Exception as e:  # la app sigue viva aunque la base no responda
        return {"estado": "sin conexión", "detalle": str(e).splitlines()[0]}
