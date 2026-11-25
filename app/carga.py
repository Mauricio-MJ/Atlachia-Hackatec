"""Prepara la base: aplica el esquema y carga los datos reales (solo lo que falte)."""
import csv
import json
from collections import defaultdict
from pathlib import Path

from app import config, ia_fotos
from app.db import conectar

ESQUEMA = Path(__file__).with_name("esquema.sql")
PUNTO = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"


def _num(v):
    return float(v) if v not in ("", None) else None


def lirio_ia_por_sitio():
    """Resume datos/sitios_ia_2025.csv (export de Earth Engine, Parte E).

    Para cada sitio: fracción de imágenes despejadas de 2025 en que el modelo de IA ve lirio
    en al menos 10% del círculo de 60 m. Imagen despejada = al menos la mitad de los píxeles
    de agua que tiene ese sitio en su mejor fecha.
    """
    filas = defaultdict(list)
    with open(config.DATOS / "sitios_ia_2025.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["lirio_mean"] and int(r["agua_count"] or 0) > 0:
                filas[r["sitio"]].append((float(r["lirio_mean"]), int(r["agua_count"])))
    res = {}
    for sitio, v in filas.items():
        tope = max(n for _, n in v)
        utiles = [l for l, n in v if n >= 0.5 * tope]
        res[sitio] = (sum(1 for l in utiles if l >= 0.10) / len(utiles), len(utiles))
    return res


def preparar_base():
    """Se llama al arrancar la aplicación. Devuelve un resumen de lo que hay en la base."""
    with conectar() as conn:
        conn.execute(ESQUEMA.read_text(encoding="utf-8"))

        for z in config.ZONAS:
            conn.execute(f"INSERT INTO zonas (nombre, ubicacion) VALUES (%s, {PUNTO}) "
                         "ON CONFLICT (nombre) DO UPDATE SET ubicacion = EXCLUDED.ubicacion",
                         (z["id"], z["lon"], z["lat"]))

        lirio = lirio_ia_por_sitio()
        for s in config.SITIOS_CONAGUA:
            d = config.CONAGUA_2025[s["clave"]]
            frac, n = lirio.get(s["clave"], (None, None))
            conn.execute(f"""
                INSERT INTO sitios_conagua (clave, nombre, ubicacion, sst_2025, sst_historica, coliformes_2025,
                                            semaforo_2025, lirio_ia_2025, imagenes_ia_2025)
                VALUES (%s, %s, {PUNTO}, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (clave) DO UPDATE SET nombre = EXCLUDED.nombre, ubicacion = EXCLUDED.ubicacion,
                    sst_2025 = EXCLUDED.sst_2025, sst_historica = EXCLUDED.sst_historica,
                    coliformes_2025 = EXCLUDED.coliformes_2025, semaforo_2025 = EXCLUDED.semaforo_2025,
                    lirio_ia_2025 = EXCLUDED.lirio_ia_2025, imagenes_ia_2025 = EXCLUDED.imagenes_ia_2025""",
                (s["clave"], s["nombre"], s["lon"], s["lat"], d["sst_2025"], d["sst_historica"],
                 d["coliformes_2025"], d["semaforo_2025"], frac, n))

        for s in config.SENSORES:
            conn.execute("""INSERT INTO sensores (sku, parametro, modelo, unidad, precio_usd)
                            VALUES (%(sku)s, %(parametro)s, %(modelo)s, %(unidad)s, %(precio_usd)s)
                            ON CONFLICT (sku) DO UPDATE SET parametro = EXCLUDED.parametro, modelo = EXCLUDED.modelo,
                                unidad = EXCLUDED.unidad, precio_usd = EXCLUDED.precio_usd""", s)

        with open(config.DATOS / "serie_sentinel2.csv", encoding="utf-8") as fh:
            serie = list(csv.DictReader(fh))
        for r in serie:
            f = r["fecha"]
            sat = f"satelite/{f}.jpg" if (config.DATOS / "mapas" / "satelite" / f"{f}.jpg").exists() else None
            ia = f"ia/{f}.jpg" if (config.DATOS / "mapas" / "ia" / f"{f}.jpg").exists() else None
            conn.execute("""
                INSERT INTO imagenes_satelite (fecha, ndti, ndci, lirio_pct, lirio_ha, frac_despejada, mapa_satelite, mapa_ia)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fecha) DO UPDATE SET ndti = EXCLUDED.ndti, ndci = EXCLUDED.ndci, lirio_pct = EXCLUDED.lirio_pct,
                    lirio_ha = EXCLUDED.lirio_ha, frac_despejada = EXCLUDED.frac_despejada,
                    mapa_satelite = EXCLUDED.mapa_satelite, mapa_ia = EXCLUDED.mapa_ia""",
                (f, _num(r["ndti"]), _num(r["ndci"]), _num(r["lirio_pct"]), _num(r["lirio_ha"]),
                 _num(r["frac_despejada"]), sat, ia))

        # Formato común: cada imagen satelital también queda como observaciones (una sola vez)
        if conn.execute("SELECT count(*) AS n FROM observaciones WHERE fuente = 'satelite'").fetchone()["n"] == 0:
            for r in serie:
                for parametro, unidad in (("ndci", "índice"), ("ndti", "índice"), ("lirio_pct", "%")):
                    if _num(r[parametro]) is None:
                        continue
                    conn.execute("""INSERT INTO observaciones (fuente, sitio, fecha, parametro, valor, unidad, calidad)
                                    VALUES ('satelite', 'Toda la presa', %s, %s, %s, %s, 'validado')""",
                                 (f"{r['fecha']}T10:30:00-06:00", parametro, _num(r[parametro]), unidad))
        conn.commit()

        # Ejemplos de la IA de fotos que el equipo juntó en el tablero (sólo si la tabla está vacía)
        if ia_fotos.EJEMPLOS_INICIALES.exists() and \
                conn.execute("SELECT count(*) AS n FROM ejemplos_ia").fetchone()["n"] == 0:
            ia_fotos.importar(conn, json.loads(ia_fotos.EJEMPLOS_INICIALES.read_text(encoding="utf-8")))
    return resumen_base()


def resumen_base():
    """Cuántas filas hay en cada tabla."""
    tablas = ["zonas", "sitios_conagua", "sensores", "imagenes_satelite", "observaciones", "reportes", "alertas", "ejemplos_ia"]
    with conectar() as conn:
        return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in tablas}
