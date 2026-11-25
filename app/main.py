"""Atlachia · aplicación principal (FastAPI + uvicorn)."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import alertas, bot, config, ia_fotos, reportes
from app.api import api
from app.carga import preparar_base, resumen_base
from app.db import conectar, estado_base

log = logging.getLogger("atlachia")
WEB = Path(__file__).with_name("web")


def revisar_alertas():
    with conectar() as conn:
        nuevas = alertas.sincronizar(conn)
    if nuevas:
        log.warning("Alertas nuevas: %s", ", ".join(nuevas))


def revisar_fotos():
    with conectar() as conn:
        n = ia_fotos.analizar_pendientes(conn)
    if n:
        log.warning("IA de fotos: %s reporte(s) analizado(s)", n)


async def vigilante():
    """Cada 5 s recalcula las alertas (sensores, reportes, decisiones) y analiza las fotos nuevas."""
    while True:
        try:
            await run_in_threadpool(revisar_alertas)
        except Exception as e:
            log.error("Revisión de alertas: %s", e)
        try:
            await run_in_threadpool(revisar_fotos)
        except Exception as e:
            log.error("Revisión de fotos: %s", e)
        await asyncio.sleep(5)


@asynccontextmanager
async def arranque(app):
    try:
        log.warning("Base preparada: %s", preparar_base())
    except Exception as e:  # si la base no responde, la app arranca igual y lo muestra en /salud
        log.error("No se pudo preparar la base: %s", e)
    ia_fotos.cargar_en_segundo_plano()
    bot.iniciar()
    tarea = asyncio.create_task(vigilante())
    yield
    tarea.cancel()


app = FastAPI(title="Atlachia", description="Centro de monitoreo de la presa de Valsequillo",
              version=config.VERSION, lifespan=arranque)
reportes.FOTOS.mkdir(parents=True, exist_ok=True)
app.mount("/mapas", StaticFiles(directory=config.DATOS / "mapas"), name="mapas")
app.mount("/fotos", StaticFiles(directory=reportes.FOTOS), name="fotos")
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.include_router(api)


@app.get("/salud", tags=["Estado"])
def salud():
    """Estado de la aplicación y de la base de datos."""
    b = estado_base()
    return {
        "app": "ok",
        "version": config.VERSION,
        "carpeta": str(config.RAIZ),
        "base_de_datos": b,
        "tablas": resumen_base() if b["estado"] == "ok" else None,
        "bot_telegram": bot.E.estado + (f" (@{bot.E.usuario})" if bot.E.usuario else ""),
        "ia_fotos": ia_fotos.E.estado,
    }


@app.get("/", include_in_schema=False)
def tablero():
    """Tablero del operador (app/web)."""
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})
