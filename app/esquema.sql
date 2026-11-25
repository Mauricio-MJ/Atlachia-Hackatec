-- =====================================================================
-- Atlachia · esquema de la base de datos (PostgreSQL 16 + PostGIS)
-- Se aplica solo al arrancar la aplicación; se puede correr muchas veces sin romper nada.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS postgis;

-- Zonas de la presa donde la ciudadanía reporta
CREATE TABLE IF NOT EXISTS zonas (
    id         SERIAL PRIMARY KEY,
    nombre     TEXT NOT NULL UNIQUE,
    ubicacion  GEOGRAPHY(Point, 4326) NOT NULL
);

-- Sitios oficiales de Conagua (RENAMECA) con sus datos de laboratorio y lo que ve el satélite
CREATE TABLE IF NOT EXISTS sitios_conagua (
    clave                TEXT PRIMARY KEY,
    nombre               TEXT NOT NULL,
    ubicacion            GEOGRAPHY(Point, 4326) NOT NULL,
    sst_2025             NUMERIC,          -- sólidos suspendidos totales, mediana 2025 (mg/L)
    sst_historica        NUMERIC,          -- mediana 2012–2025 (mg/L)
    coliformes_2025      NUMERIC,          -- coliformes fecales, mediana 2025 (NMP/100 mL)
    semaforo_2025        TEXT,             -- clasificación de Conagua
    lirio_ia_2025        NUMERIC,          -- fracción de imágenes 2025 con lirio (modelo de IA, 60 m)
    imagenes_ia_2025     INT               -- imágenes despejadas usadas para esa fracción
);

-- Catálogo de los 5 sensores DFRobot de la fase 2
CREATE TABLE IF NOT EXISTS sensores (
    sku         TEXT PRIMARY KEY,
    parametro   TEXT NOT NULL UNIQUE,      -- mismo nombre que usa el formato común
    modelo      TEXT NOT NULL,
    unidad      TEXT NOT NULL,
    precio_usd  NUMERIC(8,2) NOT NULL
);

-- Serie satelital: una fila por imagen de Sentinel-2 (promedios sobre la presa)
CREATE TABLE IF NOT EXISTS imagenes_satelite (
    fecha           DATE PRIMARY KEY,
    ndti            DOUBLE PRECISION NOT NULL,   -- turbidez
    ndci            DOUBLE PRECISION NOT NULL,   -- clorofila
    lirio_pct       DOUBLE PRECISION,            -- % del espejo de agua con lirio (IA); vacío si hay nubes
    lirio_ha        DOUBLE PRECISION,            -- hectáreas de lirio (IA)
    frac_despejada  DOUBLE PRECISION NOT NULL,   -- fracción de la presa sin nubes
    mapa_satelite   TEXT,                        -- archivo del mapa (vista satélite)
    mapa_ia         TEXT                         -- archivo del mapa (clasificación de la IA)
);

-- Formato común: TODAS las fuentes (satélite, Conagua, ciudadanos, IoT) se guardan igual
CREATE TABLE IF NOT EXISTS observaciones (
    id          BIGSERIAL PRIMARY KEY,
    fuente      TEXT NOT NULL CHECK (fuente IN ('satelite', 'conagua', 'ciudadano', 'iot')),
    sitio       TEXT NOT NULL,
    fecha       TIMESTAMPTZ NOT NULL,
    parametro   TEXT NOT NULL,
    valor       DOUBLE PRECISION,
    valor_texto TEXT,                      -- para valores que no son número (p. ej. tipo de reporte)
    unidad      TEXT,
    ubicacion   GEOGRAPHY(Point, 4326),
    calidad     TEXT NOT NULL DEFAULT 'crudo' CHECK (calidad IN ('crudo', 'validado', 'descartado')),
    recibido    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS observaciones_busqueda ON observaciones (fuente, sitio, parametro, fecha DESC);
CREATE INDEX IF NOT EXISTS observaciones_ubicacion ON observaciones USING GIST (ubicacion);

-- Reportes ciudadanos (Telegram o captura manual). Se guarda dónde y cuándo, nunca quién.
CREATE TABLE IF NOT EXISTS reportes (
    id           BIGSERIAL PRIMARY KEY,
    fecha        TIMESTAMPTZ NOT NULL DEFAULT now(),
    zona         TEXT NOT NULL REFERENCES zonas(nombre),
    tipo         TEXT NOT NULL,
    descripcion  TEXT,
    foto         TEXT,                      -- archivo de la foto guardada
    via          TEXT NOT NULL DEFAULT 'captura' CHECK (via IN ('telegram', 'captura')),
    ia_nivel     TEXT CHECK (ia_nivel IN ('ok', 'pend', 'alerta')),
    ia_texto     TEXT,
    estado       TEXT NOT NULL DEFAULT 'revisar' CHECK (estado IN ('revisar', 'valido', 'descartado')),
    revisado     TIMESTAMPTZ
);

-- Alertas: las calcula la aplicación; aquí se guarda su estado y la decisión del operador
CREATE TABLE IF NOT EXISTS alertas (
    clave        TEXT PRIMARY KEY,          -- fecha|indicador|zona
    fecha        DATE NOT NULL,
    indicador    TEXT NOT NULL,             -- ndci, lirio, iot_turbidez, ...
    zona         TEXT NOT NULL,
    valor        DOUBLE PRECISION,
    umbral       DOUBLE PRECISION,
    fuentes      TEXT[] NOT NULL,
    estado       TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'confirmada')),
    atendida     BOOLEAN NOT NULL DEFAULT FALSE,
    atendida_en  TIMESTAMPTZ,
    creada       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ejemplos de la IA de fotos (huellas de CLIP por clase)
CREATE TABLE IF NOT EXISTS ejemplos_ia (
    id         BIGSERIAL PRIMARY KEY,
    clase      TEXT NOT NULL,
    origen     TEXT,                        -- URL de Commons o 'propia'
    miniatura  TEXT,                        -- URL o imagen pequeña en base64
    huella     REAL[] NOT NULL
);
CREATE INDEX IF NOT EXISTS ejemplos_ia_clase ON ejemplos_ia (clase);

-- Descarga simulada (fase 2): mientras esté activa, los simuladores C++ alteran sus lecturas
CREATE TABLE IF NOT EXISTS eventos_simulacion (
    id      SERIAL PRIMARY KEY,
    tipo    TEXT NOT NULL DEFAULT 'descarga',
    inicio  TIMESTAMPTZ NOT NULL DEFAULT now(),
    fin     TIMESTAMPTZ NOT NULL
);

-- Columnas agregadas en el paso 3
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS detalle TEXT;

-- Ajustes de la operación (p. ej. desde cuándo cuentan las alertas del sensor después de "Preparar demo")
CREATE TABLE IF NOT EXISTS ajustes (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);
