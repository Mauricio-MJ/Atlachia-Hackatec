"""IA de fotos: CLIP (el mismo modelo que usaba el tablero) ajustado con los ejemplos del equipo.

Cada foto se convierte en una "huella" de 512 números. La huella se compara con
  1) descripciones en texto de cada clase (CLIP solo), y
  2) el promedio de las huellas de los ejemplos de cada clase (CLIP ajustado).
Así los ejemplos que se guardaron en el tablero (atlachia_ejemplos_fotos.json) siguen sirviendo.
"""
import base64
import io
import logging
import threading
import urllib.request

from app import config

log = logging.getLogger("atlachia")

MODELO = config.DATOS / "modelo_clip"
REPO = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/"
ARCHIVOS = {  # nombre local: ruta en Hugging Face (versión cuantizada, igual que en el navegador)
    "vision.onnx": "onnx/vision_model_quantized.onnx",
    "texto.onnx": "onnx/text_model_quantized.onnx",
    "tokenizer.json": "tokenizer.json",
}
EJEMPLOS_INICIALES = config.DATOS / "ejemplos_fotos.json"
AGENTE = "Atlachia/0.5 (HackaTec 2026; monitoreo de la presa de Valsequillo)"

CLASES = [
    {"id": "lirio", "nombre": "Lirio",
     "textos": ["a photo of water hyacinth covering a lake", "a lake covered with floating green aquatic plants"]},
    {"id": "espuma", "nombre": "Espuma",
     "textos": ["a photo of white foam floating on a polluted river", "detergent foam on the surface of water"]},
    {"id": "turbia", "nombre": "Agua con color o turbia",
     "textos": ["a photo of brown muddy polluted water", "dark discolored polluted river water"]},
    {"id": "normal", "nombre": "Agua sin problema visible",
     "textos": ["a photo of a calm lake with open water", "a landscape of a reservoir with clean water"]},
    {"id": "peces", "nombre": "Peces muertos",
     "textos": ["a photo of dead fish on the shore", "dead fish floating in water"]},
    {"id": "otro", "nombre": "No es de la presa",
     "textos": ["a photo of a person", "a photo of a city street", "a screenshot of a phone or a meme",
                "a photo of a room indoors"]},
]
NOMBRES = {c["id"]: c["nombre"] for c in CLASES}
TIPO_A_CLASE = {"Espuma": "espuma", "Color extraño": "turbia", "Peces muertos": "peces", "Lirio": "lirio"}

MEDIA = (0.48145466, 0.4578275, 0.40821073)
DESV = (0.26862954, 0.26130258, 0.27577711)


# ---------- Descarga del modelo (la usa iniciar.py; sólo la primera vez) ----------
def modelo_descargado():
    return all((MODELO / n).exists() for n in ARCHIVOS)


def descargar_modelo(avance=None):
    """Descarga los archivos que falten. 'avance(nombre, porcentaje)' sirve para mostrar el progreso."""
    MODELO.mkdir(parents=True, exist_ok=True)
    for nombre, ruta in ARCHIVOS.items():
        destino = MODELO / nombre
        if destino.exists():
            continue
        parcial = destino.with_suffix(destino.suffix + ".part")
        pet = urllib.request.Request(REPO + ruta, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(pet, timeout=60) as r, open(parcial, "wb") as f:
            total, hecho = int(r.headers.get("Content-Length") or 0), 0
            while bloque := r.read(1 << 20):
                f.write(bloque)
                hecho += len(bloque)
                if avance and total:
                    avance(nombre, 100 * hecho / total)
        parcial.replace(destino)


# ---------- Modelo en memoria ----------
class _Estado:
    estado = "sin cargar"      # sin cargar · cargando · lista · sin modelo · error
    detalle = ""
    compatibilidad = None      # resultado de comparar con las huellas guardadas en el tablero


E = _Estado()
_M = {}
_candado = threading.Lock()


def lista():
    return E.estado == "lista"


def cargar():
    """Carga CLIP en memoria (unos segundos) y prepara las huellas de texto de cada clase."""
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    with _candado:
        if lista():
            return
        if not modelo_descargado():
            E.estado, E.detalle = "sin modelo", "El modelo se descarga al iniciar con internet (iniciar.bat)."
            return
        E.estado, E.detalle = "cargando", ""
        try:
            op = ort.SessionOptions()
            op.log_severity_level = 3
            _M["vision"] = ort.InferenceSession(str(MODELO / "vision.onnx"), op, providers=["CPUExecutionProvider"])
            _M["texto"] = ort.InferenceSession(str(MODELO / "texto.onnx"), op, providers=["CPUExecutionProvider"])
            _M["tok"] = Tokenizer.from_file(str(MODELO / "tokenizer.json"))
            _M["T"] = {c["id"]: _normal(np.mean([huella_texto(t) for t in c["textos"]], axis=0)) for c in CLASES}
            E.estado, E.detalle = "lista", ""
            log.warning("IA de fotos lista")
        except Exception as e:
            E.estado, E.detalle = "error", str(e)
            log.error("IA de fotos: %s", e)


def cargar_en_segundo_plano():
    def trabajo():
        cargar()
        if lista():
            try:
                from app.db import conectar
                with conectar() as conn:
                    verificar_compatibilidad(conn)
            except Exception as e:
                log.error("IA de fotos (compatibilidad): %s", e)
    threading.Thread(target=trabajo, daemon=True).start()


def _normal(v):
    import numpy as np
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n else v


def _salida(sesion, nombre):
    nombres = [o.name for o in sesion.get_outputs()]
    return nombre if nombre in nombres else nombres[0]


def huella_imagen(contenido):
    """Foto (bytes) → huella normalizada de 512 números, con el mismo preprocesado de CLIP."""
    import numpy as np
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido))).convert("RGB")
    w, h = img.size
    k = 224 / min(w, h)
    nw, nh = max(224, round(w * k)), max(224, round(h * k))
    img = img.resize((nw, nh), Image.BICUBIC)
    x0, y0 = (nw - 224) // 2, (nh - 224) // 2
    img = img.crop((x0, y0, x0 + 224, y0 + 224))
    x = (np.asarray(img, dtype=np.float32) / 255.0 - np.array(MEDIA, np.float32)) / np.array(DESV, np.float32)
    x = x.transpose(2, 0, 1)[None]
    s = _M["vision"]
    return _normal(s.run([_salida(s, "image_embeds")], {s.get_inputs()[0].name: x})[0][0])


def huella_texto(texto):
    import numpy as np

    enc = _M["tok"].encode(texto)
    datos = {"input_ids": np.array([enc.ids], dtype=np.int64),
             "attention_mask": np.ones((1, len(enc.ids)), dtype=np.int64)}
    s = _M["texto"]
    entradas = {i.name: datos[i.name] for i in s.get_inputs() if i.name in datos}
    return _normal(s.run([_salida(s, "text_embeds")], entradas)[0][0])


# ---------- Clasificación (idéntica a la del tablero) ----------
def _softmax(d):
    import math
    m = max(d.values())
    e = {k: math.exp(v - m) for k, v in d.items()}
    t = sum(e.values())
    return sorted(((k, v / t) for k, v in e.items()), key=lambda x: -x[1])


def prototipos(ejemplos, usar=None):
    """Promedio de las huellas de cada clase (se necesitan al menos 3 ejemplos)."""
    import numpy as np
    P = {}
    for c, filas in ejemplos.items():
        v = [h for i, h in enumerate(filas) if usar is None or usar(i)]
        if len(v) >= 3:
            P[c] = _normal(np.mean(v, axis=0))
    return P


def clasificar(huella, P):
    import numpy as np
    e = _normal(huella)
    solo, mezcla = {}, {}
    for c in CLASES:
        t = 100 * float(np.dot(e, _M["T"][c["id"]]))
        solo[c["id"]] = t
        mezcla[c["id"]] = t + (100 * float(np.dot(e, P[c["id"]])) if c["id"] in P else t)
    return {"solo": _softmax(solo), "ajustado": _softmax(mezcla)}


def veredicto(tipo, resultado):
    """Nivel y texto que ve el operador junto al reporte."""
    c, p = resultado["ajustado"][0]
    esperado = TIPO_A_CLASE.get(tipo)
    if c == "otro":
        return "alerta", f"IA: no parece de la presa ({round(p * 100)}%)"
    if esperado and c != esperado:
        return "pend", f"IA: parece “{NOMBRES[c]}” ({round(p * 100)}%)"
    return "ok", f"IA: coincide · {NOMBRES[c]} {round(p * 100)}%"


# ---------- Ejemplos (tabla ejemplos_ia) ----------
def leer_ejemplos(conn):
    import numpy as np
    ej = {c["id"]: [] for c in CLASES}
    for f in conn.execute("SELECT clase, huella FROM ejemplos_ia ORDER BY id").fetchall():
        if f["clase"] in ej:
            ej[f["clase"]].append(np.asarray(f["huella"], dtype=np.float32))
    return ej


def conteo_ejemplos(conn):
    n = {c["id"]: 0 for c in CLASES}
    for f in conn.execute("SELECT clase, count(*) AS n FROM ejemplos_ia GROUP BY clase").fetchall():
        n[f["clase"]] = f["n"]
    return n


def importar(conn, datos, reemplazar=False):
    """Carga el archivo del tablero ({clase: [{s, p, e}]}). Sin 'reemplazar', sólo agrega los nuevos."""
    if not isinstance(datos, dict):
        raise ValueError("El archivo no tiene el formato de ejemplos de Atlachia")
    if reemplazar:
        conn.execute("DELETE FROM ejemplos_ia")
    existentes = {(f["clase"], f["miniatura"]) for f in conn.execute("SELECT clase, miniatura FROM ejemplos_ia").fetchall()}
    nuevos = repetidos = 0
    for clase, lista_ej in datos.items():
        if clase not in NOMBRES or not isinstance(lista_ej, list):
            continue
        for x in lista_ej:
            huella = x.get("e") if isinstance(x, dict) else None
            if not huella or len(huella) != 512:
                continue
            mini = x.get("s") or "foto propia"
            if mini != "foto propia" and (clase, mini) in existentes:
                repetidos += 1
                continue
            conn.execute("INSERT INTO ejemplos_ia (clase, origen, miniatura, huella) VALUES (%s, %s, %s, %s)",
                         (clase, x.get("p") or "propia", mini, [float(v) for v in huella]))
            existentes.add((clase, mini))
            nuevos += 1
    conn.commit()
    return {"agregados": nuevos, "repetidos": repetidos}


def exportar(conn):
    """Mismo formato que 'Guardar ejemplos en archivo' del tablero (se puede cargar en ambos)."""
    out = {c["id"]: [] for c in CLASES}
    for f in conn.execute("SELECT clase, origen, miniatura, huella FROM ejemplos_ia ORDER BY id").fetchall():
        if f["clase"] in out:
            out[f["clase"]].append({"s": f["miniatura"], "p": "" if f["origen"] == "propia" else f["origen"],
                                    "e": [round(v, 4) for v in f["huella"]]})
    return out


def miniatura(contenido):
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido))).convert("RGB")
    img.thumbnail((96, 96))
    b = io.BytesIO()
    img.save(b, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def agregar_propia(conn, clase, contenido):
    huella = huella_imagen(contenido)
    conn.execute("INSERT INTO ejemplos_ia (clase, origen, miniatura, huella) VALUES (%s, 'propia', %s, %s)",
                 (clase, miniatura(contenido), [float(v) for v in huella]))
    conn.commit()


def borrar_clase(conn, clase):
    n = conn.execute("DELETE FROM ejemplos_ia WHERE clase = %s", (clase,)).rowcount
    conn.commit()
    return n


# ---------- Uso ----------
def probar(conn, contenido):
    return clasificar(huella_imagen(contenido), prototipos(leer_ejemplos(conn)))


def evaluar(conn):
    """Igual que 'Evaluar' del tablero: aparta 3 de cada 10 ejemplos y mide los aciertos."""
    ej = leer_ejemplos(conn)
    P, prueba = {}, []
    for c, v in ej.items():
        if len(v) < 4:
            continue
        P.update(prototipos({c: v}, usar=lambda i: i % 10 < 7))
        prueba += [(c, h) for i, h in enumerate(v) if i % 10 >= 7]
    if len(prueba) < 3:
        return None
    clases, a1, a2 = {}, 0, 0
    for c, h in prueba:
        r = clasificar(h, P)
        ok1, ok2 = r["solo"][0][0] == c, r["ajustado"][0][0] == c
        a1, a2 = a1 + ok1, a2 + ok2
        pc = clases.setdefault(c, {"clase": NOMBRES[c], "fotos": 0, "clip_solo": 0, "clip_ajustado": 0})
        pc["fotos"] += 1
        pc["clip_solo"] += ok1
        pc["clip_ajustado"] += ok2
    pct = lambda x, n: round(100 * x / n)  # noqa: E731
    filas = [{**v, "clip_solo": pct(v["clip_solo"], v["fotos"]), "clip_ajustado": pct(v["clip_ajustado"], v["fotos"])}
             for v in clases.values()]
    return {"clases": filas, "total": {"fotos": len(prueba), "clip_solo": pct(a1, len(prueba)),
                                       "clip_ajustado": pct(a2, len(prueba))}}


def analizar_pendientes(conn):
    """Analiza las fotos de reportes que todavía no tienen veredicto de la IA."""
    if not lista():
        return 0
    pend = conn.execute("""SELECT id, tipo, foto FROM reportes WHERE foto IS NOT NULL AND ia_nivel IS NULL
                           ORDER BY fecha LIMIT 10""").fetchall()
    if not pend:
        return 0
    P = prototipos(leer_ejemplos(conn))
    from app.reportes import FOTOS
    for r in pend:
        try:
            nivel, texto = veredicto(r["tipo"], clasificar(huella_imagen((FOTOS / r["foto"]).read_bytes()), P))
        except Exception as e:
            log.error("IA de fotos, reporte %s: %s", r["id"], e)
            nivel, texto = "pend", "IA: no se pudo analizar la foto"
        conn.execute("UPDATE reportes SET ia_nivel = %s, ia_texto = %s WHERE id = %s", (nivel, texto, r["id"]))
        conn.commit()
    return len(pend)


def verificar_compatibilidad(conn, n=6):
    """Vuelve a calcular la huella de algunos ejemplos de Commons y la compara con la que guardó el tablero.
    Si se parecen (≥ 0.95), los ejemplos del tablero valen igual aquí."""
    import numpy as np
    filas = conn.execute("""SELECT miniatura, huella FROM ejemplos_ia WHERE miniatura LIKE 'https://%%'
                            ORDER BY id""").fetchall()
    if not filas:
        E.compatibilidad = None
        return None
    paso = max(1, len(filas) // n)
    sims = []
    for f in filas[::paso][:n]:
        try:
            pet = urllib.request.Request(f["miniatura"], headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(pet, timeout=20) as r:
                h = huella_imagen(r.read())
            sims.append(float(np.dot(h, _normal(f["huella"]))))
        except Exception:
            continue
    E.compatibilidad = ({"fotos": len(sims), "promedio": round(sum(sims) / len(sims), 3), "minimo": round(min(sims), 3)}
                        if sims else {"fotos": 0, "detalle": "sin internet para comprobar"})
    log.warning("IA de fotos, compatibilidad con el tablero: %s", E.compatibilidad)
    return E.compatibilidad
