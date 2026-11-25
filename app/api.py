"""Rutas de la API de Atlachia (/api/...)."""
import json
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app import alertas, bot, config, ia_fotos, reportes
from app.db import conectar

api = APIRouter(prefix="/api")


# ---------- Datos base ----------
@api.get("/zonas", tags=["Datos"])
def zonas():
    """Zonas de la presa para reportes ciudadanos."""
    with conectar() as conn:
        return conn.execute("""SELECT nombre, ST_Y(ubicacion::geometry) AS lat, ST_X(ubicacion::geometry) AS lon
                               FROM zonas ORDER BY id""").fetchall()


@api.get("/sitios", tags=["Datos"])
def sitios():
    """Sitios de Conagua: laboratorio (sólidos, semáforo) y lo que ve el satélite con IA."""
    with conectar() as conn:
        return conn.execute("""SELECT clave, nombre, ST_Y(ubicacion::geometry) AS lat, ST_X(ubicacion::geometry) AS lon,
                                      sst_2025, sst_historica, coliformes_2025, semaforo_2025,
                                      round(lirio_ia_2025 * 100) AS lirio_ia_pct, imagenes_ia_2025
                               FROM sitios_conagua ORDER BY sst_2025 DESC""").fetchall()


@api.get("/serie", tags=["Datos"])
def serie():
    """Serie satelital completa (una fila por imagen de Sentinel-2)."""
    with conectar() as conn:
        return conn.execute("SELECT * FROM imagenes_satelite ORDER BY fecha").fetchall()


@api.get("/umbrales", tags=["Datos"])
def umbrales():
    """Promedio, desviación y umbral de cada indicador por temporada (secas / lluvias)."""
    with conectar() as conn:
        u = alertas.umbrales(conn)
    return [{"indicador": i, "temporada": "lluvias" if t else "secas", **v} for (i, t), v in u.items()]


# ---------- Sensores (fase 2) ----------
@api.get("/sensores", tags=["Sensores"])
def sensores():
    """Catálogo de los 5 sensores de la fase 2."""
    with conectar() as conn:
        return conn.execute("SELECT * FROM sensores ORDER BY precio_usd DESC").fetchall()


@api.get("/sensores/ultimas", tags=["Sensores"])
def sensores_ultimas():
    """Última lectura de cada sensor del NODO-01."""
    with conectar() as conn:
        return conn.execute("""SELECT DISTINCT ON (parametro) parametro, valor, unidad, calidad, fecha
                               FROM observaciones WHERE fuente = 'iot' AND sitio = %s
                               ORDER BY parametro, fecha DESC""", (config.NODO_IOT["id"],)).fetchall()


@api.get("/sensores/serie", tags=["Sensores"])
def sensores_serie(parametro: str = "turbidez", minutos: int = 10):
    """Lecturas recientes de un sensor del NODO-01."""
    with conectar() as conn:
        return conn.execute("""SELECT fecha, valor, calidad FROM observaciones
                               WHERE fuente = 'iot' AND sitio = %s AND parametro = %s
                                 AND fecha > now() - make_interval(mins => %s)
                               ORDER BY fecha""", (config.NODO_IOT["id"], parametro, minutos)).fetchall()


def descarga_activa(conn):
    fila = conn.execute("SELECT max(fin) AS hasta FROM eventos_simulacion WHERE now() BETWEEN inicio AND fin").fetchone()
    return {"activa": fila["hasta"] is not None, "hasta": fila["hasta"]}


@api.get("/sensores/descarga", tags=["Sensores"])
def ver_descarga():
    """¿Hay una descarga simulada activa?"""
    with conectar() as conn:
        return descarga_activa(conn)


@api.post("/sensores/descarga", tags=["Sensores"])
def simular_descarga(segundos: int = 60):
    """Activa una descarga simulada: los 5 sensores reaccionan durante 'segundos'."""
    segundos = max(10, min(segundos, 600))
    with conectar() as conn:
        conn.execute("INSERT INTO eventos_simulacion (fin) VALUES (now() + make_interval(secs => %s))", (segundos,))
        conn.commit()
        return descarga_activa(conn)


class Observacion(BaseModel):
    """Formato común de Atlachia (el mismo que imprimen los sensores)."""
    fuente: Literal["satelite", "conagua", "ciudadano", "iot"]
    sitio: str
    fecha: datetime
    parametro: str
    valor: Optional[float] = None
    unidad: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    calidad: Literal["crudo", "validado", "descartado"] = "crudo"


@api.post("/observaciones", status_code=201, tags=["Sensores"])
def recibir_observacion(o: Observacion):
    """Entrada para hardware real (ESP32 por HTTP) con el formato común."""
    with conectar() as conn:
        fila = conn.execute(
            """INSERT INTO observaciones (fuente, sitio, fecha, parametro, valor, unidad, ubicacion, calidad)
               VALUES (%s, %s, %s, %s, %s, %s,
                       CASE WHEN %s::float IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography END, %s)
               RETURNING id""",
            (o.fuente, o.sitio, o.fecha, o.parametro, o.valor, o.unidad, o.lat, o.lon, o.lat, o.calidad)).fetchone()
        conn.commit()
    return {"id": fila["id"]}


# ---------- Alertas ----------
@api.get("/alertas", tags=["Alertas"])
def ver_alertas(filtro: Literal["activas", "atendidas", "todas"] = "activas"):
    """Alertas del satélite y del sensor, con su estado (pendiente / confirmada) y si ya se atendieron."""
    with conectar() as conn:
        return alertas.listar(conn, filtro)


@api.post("/alertas/{clave}/atender", tags=["Alertas"])
def atender(clave: str, atendida: bool = True):
    """El operador marca una alerta como atendida (o la reabre con atendida=false)."""
    with conectar() as conn:
        fila = conn.execute("""UPDATE alertas SET atendida = %s, atendida_en = CASE WHEN %s THEN now() END
                               WHERE clave = %s RETURNING clave""", (atendida, atendida, clave)).fetchone()
        conn.commit()
    if not fila:
        raise HTTPException(404, "No existe esa alerta")
    return {"clave": clave, "atendida": atendida}


# ---------- Reportes ciudadanos ----------
@api.get("/reportes", tags=["Reportes"])
def ver_reportes(estado: Literal["revisar", "valido", "descartado", "todos"] = "revisar"):
    """Bandeja de reportes ciudadanos."""
    with conectar() as conn:
        return reportes.listar(conn, estado)


@api.post("/reportes", status_code=201, tags=["Reportes"])
async def crear_reporte(zona: str = Form(...), tipo: str = Form(...), descripcion: str = Form(""),
                        foto: Optional[UploadFile] = File(None)):
    """Captura manual de un reporte (el bot de Telegram usa la misma lógica)."""
    nombre = None
    if foto is not None and foto.filename:
        nombre = reportes.guardar_foto(await foto.read(), foto.filename.rsplit(".", 1)[-1] if "." in foto.filename else "jpg")
    with conectar() as conn:
        if not conn.execute("SELECT 1 FROM zonas WHERE nombre = %s", (zona,)).fetchone():
            raise HTTPException(400, "Zona desconocida")
        id_rep = reportes.crear(conn, zona, tipo, descripcion, nombre, "captura")
        alertas.sincronizar(conn)
    return {"id": id_rep}


class CambioEstado(BaseModel):
    estado: Literal["revisar", "valido", "descartado"]


@api.patch("/reportes/{id_reporte}", tags=["Reportes"])
def revisar_reporte(id_reporte: int, cambio: CambioEstado):
    """El operador decide: válido, descartado o de vuelta a revisar."""
    with conectar() as conn:
        if not reportes.cambiar_estado(conn, id_reporte, cambio.estado):
            raise HTTPException(404, "No existe ese reporte")
        alertas.sincronizar(conn)
    return {"id": id_reporte, "estado": cambio.estado}


@api.post("/reportes/{id_reporte}/reanalizar", tags=["Reportes"])
def reanalizar_reporte(id_reporte: int):
    """Borra el veredicto de la IA para que vuelva a analizar la foto (p. ej. después de agregar ejemplos)."""
    with conectar() as conn:
        fila = conn.execute("UPDATE reportes SET ia_nivel = NULL, ia_texto = NULL WHERE id = %s AND foto IS NOT NULL "
                            "RETURNING id", (id_reporte,)).fetchone()
        conn.commit()
        if not fila:
            raise HTTPException(404, "No existe ese reporte o no tiene foto")
        ia_fotos.analizar_pendientes(conn)
        return conn.execute("SELECT id, ia_nivel, ia_texto FROM reportes WHERE id = %s", (id_reporte,)).fetchone()


# ---------- IA de fotos ----------
def _modelo_listo():
    if not ia_fotos.lista():
        raise HTTPException(503, f"La IA de fotos no está lista ({ia_fotos.E.estado}). {ia_fotos.E.detalle}".strip())


@api.get("/ia/estado", tags=["IA de fotos"])
def ia_estado():
    """Estado del modelo, ejemplos por clase y compatibilidad con las huellas del tablero."""
    with conectar() as conn:
        n = ia_fotos.conteo_ejemplos(conn)
    return {"estado": ia_fotos.E.estado, "detalle": ia_fotos.E.detalle,
            "compatibilidad": ia_fotos.E.compatibilidad,
            "ejemplos": [{"clase": c["id"], "nombre": c["nombre"], "n": n[c["id"]]} for c in ia_fotos.CLASES]}


@api.get("/ia/ejemplos", tags=["IA de fotos"])
def ia_ejemplos():
    """Miniaturas de los ejemplos por clase (sin huellas, para mostrarlas en el tablero)."""
    with conectar() as conn:
        filas = conn.execute("SELECT id, clase, origen, miniatura FROM ejemplos_ia ORDER BY id").fetchall()
    out = {c["id"]: [] for c in ia_fotos.CLASES}
    for f in filas:
        out.setdefault(f["clase"], []).append({"id": f["id"], "miniatura": f["miniatura"], "origen": f["origen"]})
    return out


@api.get("/ia/ejemplos/exportar", tags=["IA de fotos"])
def ia_exportar():
    """Descarga los ejemplos en el mismo formato que usa el tablero."""
    with conectar() as conn:
        datos = ia_fotos.exportar(conn)
    return JSONResponse(datos, headers={"Content-Disposition": 'attachment; filename="atlachia_ejemplos_fotos.json"'})


@api.post("/ia/ejemplos/importar", tags=["IA de fotos"])
async def ia_importar(archivo: UploadFile = File(...), reemplazar: bool = Form(False)):
    """Carga un atlachia_ejemplos_fotos.json. Sin 'reemplazar' sólo agrega los que no estén."""
    try:
        datos = json.loads((await archivo.read()).decode("utf-8"))
        with conectar() as conn:
            return ia_fotos.importar(conn, datos, reemplazar)
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"No es un archivo de ejemplos válido: {e}")


@api.post("/ia/ejemplos/{clase}", tags=["IA de fotos"])
async def ia_agregar(clase: str, foto: UploadFile = File(...)):
    """Agrega una foto propia como ejemplo de una clase."""
    if clase not in ia_fotos.NOMBRES:
        raise HTTPException(400, "Clase desconocida")
    _modelo_listo()
    contenido = await foto.read()
    with conectar() as conn:
        await run_in_threadpool(ia_fotos.agregar_propia, conn, clase, contenido)
        return {"clase": clase, "n": ia_fotos.conteo_ejemplos(conn)[clase]}


@api.delete("/ia/ejemplos/{clase}", tags=["IA de fotos"])
def ia_borrar(clase: str):
    with conectar() as conn:
        return {"borrados": ia_fotos.borrar_clase(conn, clase)}


@api.post("/ia/evaluar", tags=["IA de fotos"])
def ia_evaluar():
    """Aparta 3 de cada 10 ejemplos y compara CLIP solo contra CLIP ajustado."""
    _modelo_listo()
    with conectar() as conn:
        r = ia_fotos.evaluar(conn)
    if r is None:
        raise HTTPException(400, "Faltan ejemplos: se necesitan al menos 4 en varias clases")
    return r


@api.post("/ia/probar", tags=["IA de fotos"])
async def ia_probar(foto: UploadFile = File(...)):
    """Clasifica una foto sin guardarla."""
    _modelo_listo()
    contenido = await foto.read()
    with conectar() as conn:
        r = await run_in_threadpool(ia_fotos.probar, conn, contenido)
    nombres = lambda lista: [{"clase": ia_fotos.NOMBRES[c], "probabilidad": round(p, 3)} for c, p in lista[:3]]  # noqa: E731
    return {"ajustado": nombres(r["ajustado"]), "solo": nombres(r["solo"])}


# ---------- Bot de Telegram ----------
@api.get("/bot/estado", tags=["Bot de Telegram"])
def bot_estado():
    """Si el bot está escuchando, su usuario y cuántos reportes llegaron desde que arrancó la app."""
    return {"estado": bot.E.estado, "usuario": bot.E.usuario, "enlace": bot.enlace(),
            "detalle": bot.E.detalle, "reportes_recibidos": bot.E.reportes}


@api.get("/bot/qr.png", tags=["Bot de Telegram"])
def bot_qr():
    """Código QR que abre el bot (para imprimir o mostrar en pantalla)."""
    import io

    import qrcode
    if not bot.enlace():
        raise HTTPException(503, "El bot todavía no está conectado")
    img = qrcode.make(bot.enlace(), border=2, box_size=12)
    b = io.BytesIO()
    img.save(b, "PNG")
    return Response(b.getvalue(), media_type="image/png")


# ---------- Demo ----------
@api.post("/demo/preparar", tags=["Estado"])
def preparar_demo():
    """Deja el tablero limpio para presentar: borra los reportes (y sus fotos), las lecturas de los sensores,
    las descargas simuladas y las alertas del sensor, y reabre las alertas atendidas.
    Conserva la serie satelital, Conagua y los ejemplos de la IA."""
    with conectar() as conn:
        fotos = [f["foto"] for f in conn.execute("SELECT foto FROM reportes WHERE foto IS NOT NULL").fetchall()]
        n_rep = conn.execute("DELETE FROM reportes").rowcount
        conn.execute("DELETE FROM observaciones WHERE fuente = 'ciudadano'")
        conn.execute("DELETE FROM eventos_simulacion")
        # Las lecturas del sensor se quedan (la alerta compara contra las 5 anteriores); sólo cuentan
        # los cambios bruscos que pasen a partir de ahora.
        conn.execute("""INSERT INTO ajustes (clave, valor) VALUES ('alertas_iot_desde', now()::text)
                        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor""")
        n_al = conn.execute("DELETE FROM alertas WHERE indicador = 'iot'").rowcount
        conn.execute("UPDATE alertas SET atendida = FALSE, atendida_en = NULL")
        conn.commit()
        alertas.sincronizar(conn)
    for f in fotos:
        (reportes.FOTOS / f).unlink(missing_ok=True)
    bot.E.reportes = 0
    return {"reportes_borrados": n_rep, "alertas_del_sensor_borradas": n_al}
