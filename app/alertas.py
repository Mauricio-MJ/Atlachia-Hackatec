"""Lógica de alertas de Atlachia.

Satélite: una imagen genera alerta si la clorofila (NDCI) o el lirio (IA) rebasan el umbral
de su temporada (promedio + 2 desviaciones estándar; lluvias = junio a octubre).
Sensor IoT: alerta si la turbidez del NODO-01 sube más de 2.5 veces el promedio de sus
5 lecturas anteriores (cambio brusco, típico de una descarga).
Confirmación cruzada: una alerta pasa a "confirmada" cuando otra fuente coincide:
un reporte ciudadano no descartado (±3 días para el satélite; ±2 horas y en la entrada del
Atoyac para el sensor). La decisión del operador (atendida) nunca se pierde al recalcular.
"""
from statistics import mean, stdev

from app import config

ZONA_PRESA = "Toda la presa (promedio)"
INDICADORES = {"ndci": "Clorofila (NDCI)", "lirio_pct": "Lirio (IA, % del espejo)"}


def lluvias(fecha):
    return 6 <= fecha.month <= 10


def umbrales(conn):
    """Promedio, desviación y umbral por indicador y temporada."""
    filas = conn.execute("SELECT fecha, ndci, lirio_pct FROM imagenes_satelite ORDER BY fecha").fetchall()
    res = {}
    for ind in INDICADORES:
        for temporada in (False, True):
            v = [f[ind] for f in filas if f[ind] is not None and lluvias(f["fecha"]) == temporada]
            if len(v) >= 3:
                m, d = mean(v), stdev(v)
                res[(ind, temporada)] = {"promedio": m, "desviacion": d, "umbral": m + 2 * d, "n": len(v)}
    return res


def _alertas_satelite(conn, u):
    filas = conn.execute("SELECT fecha, ndci, lirio_pct FROM imagenes_satelite ORDER BY fecha").fetchall()
    out = []
    for f in filas:
        for ind in INDICADORES:
            t = u.get((ind, lluvias(f["fecha"])))
            if t and f[ind] is not None and f[ind] > t["umbral"]:
                rep = conn.execute("""SELECT count(*) AS n FROM reportes WHERE estado <> 'descartado'
                                      AND fecha::date BETWEEN %s::date - 3 AND %s::date + 3""",
                                   (f["fecha"], f["fecha"])).fetchone()["n"]
                out.append({"clave": f"{f['fecha']}|{ind}|presa", "fecha": f["fecha"], "indicador": ind,
                            "zona": ZONA_PRESA, "valor": f[ind], "umbral": t["umbral"],
                            "fuentes": ["Satélite"] + (["Reporte ciudadano"] if rep else []),
                            "detalle": f"{INDICADORES[ind]}: {f[ind]:.3f} contra umbral {t['umbral']:.3f}"})
    return out


def _alertas_iot(conn):
    """Busca cambios bruscos de turbidez en las últimas 24 h del NODO-01."""
    lect = conn.execute("""SELECT fecha, valor FROM observaciones
                           WHERE fuente = 'iot' AND sitio = %s AND parametro = 'turbidez' AND calidad = 'validado'
                             AND fecha > now() - interval '24 hours' ORDER BY fecha""",
                        (config.NODO_IOT["id"],)).fetchall()
    desde = conn.execute("SELECT valor::timestamptz AS t FROM ajustes WHERE clave = 'alertas_iot_desde'").fetchone()
    desde = desde["t"] if desde else None   # lo fija "Preparar demo": antes de eso no se generan alertas
    out = []
    for i in range(5, len(lect)):
        if desde and lect[i]["fecha"] <= desde:
            continue
        previo = mean(l["valor"] for l in lect[i - 5:i])
        v = lect[i]["valor"]
        if v > 80 and v > 2.5 * previo:
            t = lect[i]["fecha"]
            oxigeno = conn.execute("""SELECT valor FROM observaciones WHERE fuente = 'iot' AND sitio = %s
                                      AND parametro = 'oxigeno_disuelto' AND fecha BETWEEN %s - interval '30 seconds'
                                      AND %s + interval '30 seconds' ORDER BY fecha DESC LIMIT 1""",
                                   (config.NODO_IOT["id"], t, t)).fetchone()
            rep = conn.execute("""SELECT count(*) AS n FROM reportes WHERE estado <> 'descartado' AND zona = %s
                                  AND fecha BETWEEN %s - interval '2 hours' AND %s + interval '2 hours'""",
                               (config.NODO_IOT["zona"], t, t)).fetchone()["n"]
            det = f"Turbidez {v:.0f} NTU (antes ~{previo:.0f})"
            if oxigeno:
                det += f" · oxígeno {oxigeno['valor']:.1f} mg/L"
            out.append({"clave": f"{t:%Y-%m-%d %H:%M}|iot|{config.NODO_IOT['zona']}", "fecha": t.date(),
                        "indicador": "iot", "zona": config.NODO_IOT["zona"], "valor": v, "umbral": 2.5 * previo,
                        "fuentes": ["Sensor IoT"] + (["Reporte ciudadano"] if rep else []), "detalle": det})
    return out


def sincronizar(conn):
    """Recalcula todas las alertas y las guarda; conserva lo que decidió el operador."""
    u = umbrales(conn)
    nuevas = []
    for a in _alertas_satelite(conn, u) + _alertas_iot(conn):
        estado = "confirmada" if len(a["fuentes"]) > 1 else "pendiente"
        fila = conn.execute(
            """INSERT INTO alertas (clave, fecha, indicador, zona, valor, umbral, fuentes, estado, detalle)
               VALUES (%(clave)s, %(fecha)s, %(indicador)s, %(zona)s, %(valor)s, %(umbral)s, %(fuentes)s, %(estado)s, %(detalle)s)
               ON CONFLICT (clave) DO UPDATE SET fuentes = EXCLUDED.fuentes, estado = EXCLUDED.estado,
                   valor = GREATEST(alertas.valor, EXCLUDED.valor), detalle = CASE WHEN EXCLUDED.valor >= alertas.valor
                   THEN EXCLUDED.detalle ELSE alertas.detalle END
               RETURNING (xmax = 0) AS insertada""", {**a, "estado": estado}).fetchone()
        if fila["insertada"]:
            nuevas.append(a["clave"])
    conn.commit()
    return nuevas


def listar(conn, filtro="activas"):
    cond = {"activas": "NOT atendida", "atendidas": "atendida", "todas": "TRUE"}.get(filtro, "NOT atendida")
    return conn.execute(f"""SELECT clave, fecha, indicador, zona, valor, umbral, fuentes, estado, atendida, atendida_en, detalle, creada
                            FROM alertas WHERE {cond} ORDER BY fecha DESC, creada DESC""").fetchall()
