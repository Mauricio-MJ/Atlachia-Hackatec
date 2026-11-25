"""Bot de Telegram de Atlachia: un ciudadano reporta en 4 pasos (zona, problema, foto, descripción).

Corre dentro de la aplicación (no hace falta tener ningún navegador abierto). Se guarda dónde
y cuándo, nunca quién: del chat sólo se usa su número mientras dura la conversación.
"""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

from app import alertas, config, reportes
from app.db import conectar

log = logging.getLogger("atlachia")

API = os.getenv("TELEGRAM_API", "https://api.telegram.org")
ZONAS = [z["id"] for z in config.ZONAS]
TIPOS = reportes.TIPOS


class _Estado:
    estado = "sin token"   # sin token · conectando · conectado · reconectando · token inválido
    usuario = ""
    detalle = ""
    reportes = 0           # recibidos desde que arrancó la aplicación


E = _Estado()
_chats = {}                # conversaciones a medias: {chat_id: {"paso": ..., "zona": ..., ...}}


class ErrorTelegram(Exception):
    def __init__(self, codigo, texto):
        super().__init__(texto)
        self.codigo = codigo


def _llamar(metodo, datos=None, espera=30):
    pet = urllib.request.Request(f"{API}/bot{config.TELEGRAM_TOKEN}/{metodo}",
                                 data=json.dumps(datos or {}).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pet, timeout=espera) as r:
            j = json.load(r)
    except urllib.error.HTTPError as e:   # el mensaje nunca incluye la dirección (que lleva el token)
        try:
            texto = json.load(e).get("description", "")
        except Exception:
            texto = ""
        raise ErrorTelegram(e.code, texto or f"error {e.code} de Telegram") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErrorTelegram(0, "sin conexión con Telegram") from None
    if not j.get("ok"):
        raise ErrorTelegram(j.get("error_code", 0), j.get("description", "error de Telegram"))
    return j["result"]


def _enviar(chat, texto, botones=None):
    datos = {"chat_id": chat, "text": texto}
    if botones:
        datos["reply_markup"] = {"inline_keyboard": botones}
    _llamar("sendMessage", datos)


def _teclado(prefijo, opciones):
    return [[{"text": t, "callback_data": f"{prefijo}:{i}"}] for i, t in enumerate(opciones)]


# ---------- Conversación ----------
def _preguntar(chat):
    c = _chats[chat]
    if c["paso"] == "zona":
        _enviar(chat, "Hola, soy el bot de Atlachia. Gracias por ayudar a cuidar la presa de Valsequillo.\n\n"
                      "1/4 ¿En qué zona de la presa estás?", _teclado("z", ZONAS))
    elif c["paso"] == "tipo":
        _enviar(chat, f"2/4 Zona: {c['zona']}.\n¿Qué problema ves?", _teclado("t", TIPOS))
    elif c["paso"] == "foto":
        _enviar(chat, "3/4 Manda una foto del problema.", [[{"text": "Omitir foto", "callback_data": "f:0"}]])
    elif c["paso"] == "desc":
        _enviar(chat, "4/4 Describe en pocas palabras lo que ves.", [[{"text": "Omitir", "callback_data": "d:0"}]])


def _descargar_foto(file_id):
    """Descarga la foto desde Telegram y la guarda en datos/fotos (aquí no hay problema de CORS)."""
    f = _llamar("getFile", {"file_id": file_id})
    ruta = f["file_path"]
    pet = urllib.request.Request(f"{API}/file/bot{config.TELEGRAM_TOKEN}/{ruta}")
    with urllib.request.urlopen(pet, timeout=60) as r:
        contenido = r.read()
    return reportes.guardar_foto(contenido, ruta.rsplit(".", 1)[-1] if "." in ruta else "jpg")


def _terminar(chat):
    c = _chats.pop(chat)
    try:
        with conectar() as conn:
            reportes.crear(conn, c["zona"], c["tipo"], c.get("desc", ""), c.get("foto"), "telegram")
            alertas.sincronizar(conn)
    except Exception as e:
        log.error("Bot: no se pudo guardar el reporte (%s)", e)
        _enviar(chat, "⚠️ No pude guardar tu reporte por un problema del sistema. Intenta de nuevo con /start.")
        return
    E.reportes += 1
    log.warning("Reporte por Telegram: %s · %s%s", c["zona"], c["tipo"], " · con foto" if c.get("foto") else "")
    _enviar(chat, "✅ Reporte recibido. Ya aparece en el tablero de Atlachia.\n"
                  "Se guardó dónde y cuándo, nunca quién.\n\nPara otro reporte escribe /start.")


def _atender(u):
    if "callback_query" in u:
        q = u["callback_query"]
        try:
            _llamar("answerCallbackQuery", {"callback_query_id": q["id"]})
        except ErrorTelegram:
            pass
        chat = (q.get("message") or {}).get("chat", {}).get("id")
        c = _chats.get(chat)
        if not c:
            return
        clave, _, valor = str(q.get("data", "")).partition(":")
        i = int(valor) if valor.isdigit() else -1
        if clave == "z" and c["paso"] == "zona":
            c["zona"], c["paso"] = ZONAS[i] if 0 <= i < len(ZONAS) else ZONAS[0], "tipo"
            return _preguntar(chat)
        if clave == "t" and c["paso"] == "tipo":
            c["tipo"], c["paso"] = TIPOS[i] if 0 <= i < len(TIPOS) else "Otro", "foto"
            return _preguntar(chat)
        if clave == "f" and c["paso"] == "foto":
            c["paso"] = "desc"
            return _preguntar(chat)
        if clave == "d" and c["paso"] == "desc":
            return _terminar(chat)
        return

    m = u.get("message")
    if not m or m.get("chat", {}).get("type") != "private":
        return
    chat, texto = m["chat"]["id"], (m.get("text") or "").strip()
    if texto.startswith("/start") or chat not in _chats:
        _chats[chat] = {"paso": "zona"}
        return _preguntar(chat)
    c = _chats[chat]
    if c["paso"] == "foto":
        archivo = None
        if m.get("photo"):
            archivo = m["photo"][-1]["file_id"]                       # la de mayor resolución
        elif (m.get("document") or {}).get("mime_type", "").startswith("image/"):
            archivo = m["document"]["file_id"]                       # foto enviada como archivo
        if archivo:
            try:
                c["foto"] = _descargar_foto(archivo)
            except Exception as e:
                log.error("Bot: no se pudo descargar la foto (%s)", e)
            c["paso"] = "desc"
            return _preguntar(chat)
    if c["paso"] == "desc" and texto:
        c["desc"] = texto
        return _terminar(chat)
    return _preguntar(chat)


# ---------- Escucha (long polling) ----------
def _explicar(e):
    if getattr(e, "codigo", 0) == 409:
        return ("Otra copia de Atlachia o el tablero.html está usando este bot. Ciérrala; "
                "si acabas de reiniciar Atlachia, espera 30 segundos y se conecta solo.")
    if getattr(e, "codigo", 0) in (401, 404):
        return "Telegram rechazó el token. Vuelve a ejecutar instalar.bat y pega el token correcto."
    return str(e)


def _escuchar():
    offset = None
    while True:
        try:
            if not E.usuario:
                E.estado = "conectando"
                E.usuario = _llamar("getMe")["username"]
                previos = _llamar("getUpdates", {"offset": -1})   # ignora lo que llegó con la app apagada
                offset = previos[-1]["update_id"] + 1 if previos else None
            if E.estado != "conectado":
                E.estado, E.detalle = "conectado", ""
                log.warning("Bot de Telegram conectado: @%s", E.usuario)
            datos = {"timeout": 25, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                datos["offset"] = offset
            for u in _llamar("getUpdates", datos, espera=35):
                offset = u["update_id"] + 1
                try:
                    _atender(u)
                except Exception as e:
                    log.error("Bot: %s", e)
        except Exception as e:
            invalido = getattr(e, "codigo", 0) in (401, 404)
            detalle = _explicar(e)
            if detalle != E.detalle:
                log.error("Bot de Telegram: %s", detalle)
            E.estado, E.detalle = ("token inválido" if invalido else "reconectando"), detalle
            time.sleep(60 if invalido else 5)


def iniciar():
    if not config.TELEGRAM_TOKEN:
        E.estado, E.detalle = "sin token", "Ejecuta instalar.bat para pegar el token del bot."
        return
    threading.Thread(target=_escuchar, daemon=True, name="bot-telegram").start()


def enlace():
    return f"https://t.me/{E.usuario}" if E.usuario else ""
