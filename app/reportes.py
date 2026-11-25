"""Reportes ciudadanos: se guarda dónde y cuándo, nunca quién."""
import uuid

from app import config

TIPOS = ["Espuma", "Color extraño", "Olor", "Peces muertos", "Lirio", "Otro"]
FOTOS = config.DATOS / "fotos"


def guardar_foto(contenido, extension="jpg"):
    """Guarda la foto en datos/fotos y devuelve su nombre de archivo."""
    FOTOS.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}.{extension.lower().lstrip('.') or 'jpg'}"
    (FOTOS / nombre).write_bytes(contenido)
    return nombre


def crear(conn, zona, tipo, descripcion="", foto=None, via="captura"):
    """Registra el reporte y su observación en el formato común."""
    if tipo not in TIPOS:
        tipo = "Otro"
    fila = conn.execute(
        """INSERT INTO reportes (zona, tipo, descripcion, foto, via) VALUES (%s, %s, %s, %s, %s)
           RETURNING id, fecha""", (zona, tipo, (descripcion or "").strip()[:200] or None, foto, via)).fetchone()
    conn.execute(
        """INSERT INTO observaciones (fuente, sitio, fecha, parametro, valor_texto, ubicacion, calidad)
           SELECT 'ciudadano', nombre, %s, 'reporte', %s, ubicacion, 'crudo' FROM zonas WHERE nombre = %s""",
        (fila["fecha"], tipo, zona))
    conn.commit()
    return fila["id"]


def listar(conn, estado="revisar"):
    cond = "TRUE" if estado == "todos" else "estado = %(estado)s"
    return conn.execute(f"""SELECT id, fecha, zona, tipo, descripcion, foto, via, ia_nivel, ia_texto, estado, revisado
                            FROM reportes WHERE {cond} ORDER BY fecha DESC""", {"estado": estado}).fetchall()


def cambiar_estado(conn, id_reporte, estado):
    fila = conn.execute("""UPDATE reportes SET estado = %s, revisado = CASE WHEN %s = 'revisar' THEN NULL ELSE now() END
                           WHERE id = %s RETURNING id""", (estado, estado, id_reporte)).fetchone()
    conn.commit()
    return fila is not None
