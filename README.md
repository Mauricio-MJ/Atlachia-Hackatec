# Atlachia · Centro de monitoreo de la presa de Valsequillo

"El vigía del agua", del náhuatl *atl* (agua) y *tlachia* (vigilar). Vigila Valsequillo con satélite, datos oficiales de Conagua, reportes ciudadanos y sensores IoT (simulados en la fase 2).

## Uso (Windows)

Requisitos: **Python 3.10+** y **Docker Desktop** abierto.

1. **Una sola vez:** doble clic en `instalar.bat`. Crea el entorno, instala las librerías, genera las contraseñas en `.env`, pide el token del bot (opcional) y levanta la base de datos en Docker.
2. **Cada vez:** doble clic en `iniciar.bat`. Arranca la base y la aplicación y abre el navegador en http://127.0.0.1:8000.

Para cambiar el token del bot, vuelve a ejecutar `instalar.bat`: no borra nada. Al actualizar Atlachia basta con reemplazar los archivos: `iniciar.bat` instala solo las librerías nuevas.

## Estructura

| Carpeta / archivo | Qué es |
| --- | --- |
| `app/` | Aplicación en Python (FastAPI + uvicorn): `api.py` (rutas), `alertas.py`, `reportes.py`, `ia_fotos.py`, `bot.py`, `carga.py` (datos) |
| `app/web/` | Tablero del operador: `index.html` (diseño) y `tablero.js` (lee todo de la API cada 3 s) |
| `app/esquema.sql` | Tablas de la base (se aplican solas al arrancar) |
| `datos/` | Datos reales: serie de Sentinel-2 (77 imágenes), 154 mapas (satélite e IA), lirio por sitio de Conagua con IA y `ejemplos_fotos.json` (ejemplos de la IA de fotos). `modelo_clip/` y `fotos/` se crean solos |
| `sensores/` | Fase 2: 5 simuladores C++ de los sensores DFRobot + `puente.py`, que guarda sus lecturas en la base. Corre en Docker (se compila solo) |
| `docker-compose.yml` | PostgreSQL 16 + PostGIS 3.4 y pgAdmin |
| `instalar.bat` / `instalar.py` | Instalación automática |
| `iniciar.bat` / `iniciar.py` | Arranque automático |
| `.env` | Contraseñas y token (se crea solo; **no se comparte**) |
| `GUION.md` | Guion de la presentación (pitch, demo paso a paso, preguntas) y arranque el día del evento |

## Base de datos

Al arrancar, la aplicación crea las tablas que falten y carga los datos de `datos/` sin duplicar nada.

| Tabla | Contenido |
| --- | --- |
| `zonas` | 5 zonas de la presa para reportes (con coordenadas PostGIS) |
| `sitios_conagua` | 4 sitios RENAMECA: sólidos 2025, histórico, coliformes, semáforo y lirio con IA |
| `sensores` | Los 5 sensores DFRobot de la fase 2 con su precio |
| `imagenes_satelite` | Una fila por imagen de Sentinel-2: clorofila, turbidez, lirio (IA), nubes y mapas |
| `observaciones` | Formato común: todas las fuentes (satélite, Conagua, ciudadanos, IoT) |
| `reportes` | Reportes ciudadanos con la etiqueta de la IA y la decisión del operador |
| `alertas` | Alertas calculadas, su estado y si ya se atendieron |
| `ejemplos_ia` | Huellas de CLIP de los ejemplos de la IA de fotos |
| `eventos_simulacion` | Descargas simuladas (los sensores reaccionan mientras están activas) |
| `ajustes` | Ajustes de operación (desde cuándo cuentan las alertas del sensor tras "Preparar demo") |

## Sensores (fase 2, simulados)

El contenedor `atlachia_sensores` compila los 5 simuladores C++ y corre `puente.py`, que hace el papel del ESP32: lee cada lectura (formato común) y la guarda en `observaciones` con `fuente = iot` y `sitio = NODO-01` (entrada del Atoyac). Una lectura cada 3 s por sensor (en campo serían 5 min).

Cada simulador reproduce la parte eléctrica del sensor real (voltaje, ruido, ADC del ESP32 y curva de calibración de DFRobot) y marca la lectura como `validado` o `descartado`.

**Descarga simulada:** `POST /api/sensores/descarga?segundos=60` (o el botón del tablero). Durante ese tiempo los 5 sensores reaccionan juntos: turbidez +150 NTU, oxígeno −3 mg/L, conductividad +0.6 mS/cm, pH −0.6 y temperatura +0.8 °C.

Ver lo que hace el puente: `docker logs -f atlachia_sensores`.

## Alertas

La aplicación revisa las alertas cada 5 s (`app/alertas.py`) y guarda su estado en la tabla `alertas`:

- **Satélite:** una imagen genera alerta si la clorofila (NDCI) o el lirio (IA) rebasan el umbral de su temporada (promedio + 2 desviaciones; lluvias = junio a octubre). Umbrales en `/api/umbrales`.
- **Sensor IoT:** cambio brusco de turbidez en el NODO-01 (más de 2.5 veces el promedio de sus 5 lecturas anteriores y más de 80 NTU).
- **Confirmación cruzada:** una alerta pasa de *pendiente* a *confirmada* si coincide un reporte ciudadano no descartado (±3 días para el satélite; ±2 horas y en la entrada del Atoyac para el sensor). Si el operador descarta el reporte, la alerta vuelve a *pendiente*.
- **Operador:** marca alertas como atendidas (`POST /api/alertas/{clave}/atender`) y reportes como válidos o descartados (`PATCH /api/reportes/{id}`).

## IA de fotos

Cada reporte con foto se analiza solo, unos segundos después de llegar (`app/ia_fotos.py`), con **CLIP ViT-B/32**: el mismo modelo cuantizado que usaba el tablero (`Xenova/clip-vit-base-patch32`), ahora en Python con ONNX Runtime. Se descarga una sola vez (~150 MB) al abrir `iniciar.bat` con internet y queda en `datos/modelo_clip/`.

- **CLIP solo:** compara la foto con descripciones en texto de 6 clases (lirio, espuma, agua turbia, sin problema, peces muertos, no es de la presa).
- **CLIP ajustado:** además la compara con el promedio de los ejemplos de cada clase (tabla `ejemplos_ia`). Los ejemplos del tablero se cargan solos la primera vez desde `datos/ejemplos_fotos.json`; las fotos repetidas se ignoran.
- **Veredicto:** *coincide* (verde), *parece otra cosa* (amarillo, el operador revisa) o *no parece de la presa* (rojo).
- **Compatibilidad:** al cargar el modelo, vuelve a calcular la huella de algunas fotos de Commons y la compara con la que guardó el tablero (≥ 0.95 = los ejemplos valen igual).
- **Rutas:** `/api/ia/estado`, `/api/ia/evaluar`, `/api/ia/probar`, `/api/ia/ejemplos/importar`, `/api/ia/ejemplos/exportar` (mismo formato que el tablero), `/api/ia/ejemplos/{clase}` y `/api/reportes/{id}/reanalizar`.

## Tablero del operador

Se abre solo en http://127.0.0.1:8000 con `iniciar.bat`. Seis pestañas (teclas 1 a 6):

1. **Resumen:** mapa de Sentinel-2 (satélite o clasificación IA) con sitios de Conagua, reportes y el NODO-01; estado de la presa en la fecha elegida, alertas activas y reportes por revisar.
2. **Histórico:** gráficas de control de clorofila, lirio y turbidez (rango normal por temporada) y comparación con los sitios de Conagua.
3. **Alertas:** activas, atendidas o todas; *Ver en mapa*, *Ver sensor*, *Marcar atendida* y *Reabrir*.
4. **Reportes:** QR del bot, captura manual y bandeja con foto, veredicto de la IA y la decisión del operador (válido / descartar / deshacer).
5. **Sensores:** las 5 lecturas del NODO-01, turbidez de los últimos 5 minutos y el botón *Simular descarga (60 s)*.
6. **Configuración:** estado del sistema, **Preparar demo** (borra reportes y alertas de prueba, reabre las atendidas; conserva satélite, Conagua y ejemplos) y la IA de fotos (ejemplos, fotos propias, importar / guardar, evaluar y probar).

Los avisos (nueva alerta, alerta confirmada, nuevo reporte) aparecen abajo a la derecha. El indicador de la cabecera muestra si los sensores, el bot y la IA están funcionando.

## Bot de Telegram

`app/bot.py` corre dentro de la aplicación con el token de `.env` (no hace falta ningún navegador abierto). El ciudadano reporta en 4 pasos: zona, problema, foto (opcional) y descripción (opcional). La foto se descarga en el servidor, el reporte se guarda con `via = telegram` y la IA de fotos lo analiza a los pocos segundos.

- Sólo atiende chats privados y no guarda quién reporta: sólo dónde y cuándo.
- Estado y QR para imprimir: `/api/bot/estado` y `/api/bot/qr.png`.
- **Sólo una copia a la vez:** Telegram entrega los mensajes a un solo programa. Si `tablero.html` (plan B) u otra ventana de Atlachia está conectada al mismo bot, el tablero lo avisa en Configuración.

## Accesos locales

- Tablero: http://127.0.0.1:8000
- Estado: http://127.0.0.1:8000/salud
- API completa, probable desde el navegador: http://127.0.0.1:8000/docs (datos, sensores, alertas, reportes, IA de fotos y `POST /api/observaciones` para hardware real)
- pgAdmin (opcional): http://127.0.0.1:5051 · usuario `admin@example.com` · contraseña en `.env` (`PGADMIN_CLAVE`). Para ver la base, agrega un servidor con host `db`, puerto `5432`, usuario y contraseña de `.env` (`DB_USUARIO`, `DB_CLAVE`).

## Avance

- [x] Paso 0 · Base del proyecto
- [x] Paso 1 · Base de datos y datos reales
- [x] Paso 2 · Sensores (C++ en Docker + puente en Python)
- [x] Paso 3 · API y alertas
- [x] Paso 4 · IA de fotos (el lirio con IA ya viene en los datos del paso 1)
- [x] Paso 5 · Bot de Telegram
- [x] Paso 6 · Tablero
- [x] Paso 7 · Integración y ensayo
