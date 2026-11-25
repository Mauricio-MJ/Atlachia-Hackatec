# Atlachia · Guion de la presentación (20 minutos)

| Bloque | Tiempo | Quién habla |
| --- | --- | --- |
| Pitch | 7 min | Un integrante |
| Interacción con el prototipo | 7 min | Uno maneja la laptop, otro guía; el jurado usa el bot desde su teléfono |
| Preguntas y respuestas | 6 min | El jurado pregunta; responde el integrante que domina el tema |

## 1. Pitch (7 minutos)

| Minuto | Bloque | Qué se dice |
| --- | --- | --- |
| 0:00 – 0:45 | Gancho | Espuma tóxica y lirio en Valsequillo: todos lo ven, pero nadie sabe **cuándo** empezó ni **dónde**. |
| 0:45 – 1:45 | Problema | Las descargas al Atoyac y a la presa casi nunca se detectan cuando ocurren: la inspección es manual y esporádica. Cuando llega el muestreo, la descarga ya pasó. |
| 1:45 – 3:00 | Solución | Atlachia junta las fuentes en un tablero: satélite (Sentinel-2), datos oficiales de Conagua (RENAMECA), reportes ciudadanos por Telegram y, en la fase 2, sensores. Dice **dónde y cuándo** cambia el agua; la autoridad determina **quién**. |
| 3:00 – 4:15 | Cómo funciona | El satélite pasa cada pocos días y mide clorofila (NDCI), turbidez (NDTI) y lirio; se descartan las imágenes con nubes. Si un valor rebasa el umbral de su temporada (promedio + 2 desviaciones), sale una alerta, y pasa a **confirmada** cuando coincide con otra fuente. **Dos modelos de IA:** un Random Forest mide el lirio desde el satélite (94% en puntos de prueba) y un modelo de visión (CLIP ajustado con ejemplos propios) revisa las fotos de los reportes (73% de aciertos, contra 61% sin ajustar). La IA sugiere; una persona decide. |
| 4:15 – 5:15 | Por qué aquí y ahora | Desde junio de 2026 existe el rescate integral de Valsequillo (Gobierno de Puebla, Conagua, IPN y SECIHTI). Atlachia se propone como su capa de monitoreo abierto. Se replica en cualquier presa de México: basta cambiar el área y los sitios de Conagua. |
| 5:15 – 6:15 | Futuro | No es una maqueta: corre sobre una base de datos geoespacial (PostgreSQL + PostGIS), con una API y simuladores de los 5 sensores DFRobot que hablan el mismo formato que usará el hardware real. En la fase 2 se conecta un ESP32 en la entrada del Atoyac y del Alseseca (≈ 5,450 MXN en sensores por nodo), sin rehacer la plataforma. |
| 6:15 – 7:00 | Honestidad y cierre | Lo que el satélite **no** ve: pH, oxígeno disuelto, metales, ni el cauce angosto del río. Por eso se combina con ciudadanos y sensores. Frase de cierre y pase a la demo: "Ahora véanlo ustedes". |

## 2. Interacción con el prototipo (7 minutos)

El tablero es la **interfaz del operador** (personal de Conagua, Ceaspue o SECIHTI): muestra datos y acciones, sin explicaciones. **Lo que significa cada cosa lo explican ustedes en voz alta.** El jurado participa **desde su teléfono con el bot** (QR impreso y también en la pestaña Reportes).

Pestañas: **1 Resumen · 2 Histórico · 3 Alertas · 4 Reportes · 5 Sensores · 6 Configuración** (clic o teclas 1 a 6). Arriba a la derecha, **Sensores**, **Bot** e **IA de fotos** deben estar en verde. Los avisos salen abajo a la derecha.

| Tiempo | Pestaña | Qué hace el operador (y qué dicen ustedes) | Jurado |
| --- | --- | --- | --- |
| 1 min | **1 Resumen** | Abre en el 12 sep 2026: clorofila sobre el umbral ("Estado de la presa"). Cambiar a "Clasificación IA" (*"esto lo clasifica nuestro modelo de IA, 94% de exactitud"*). A la derecha, alertas y reportes pendientes | Mueve las fechas |
| 1 min | **2 Histórico** | Tres **gráficas de control** (clorofila, lirio, turbidez): la banda es el rango normal de cada temporada y los puntos rojos lo que sale de ella. Sitios de Conagua: *"los sitios con más sólidos suspendidos son los que el satélite ve con lirio"* | — |
| 1 min | **5 Sensores** | **"Simular descarga (60 s)"**: la turbidez se pone en rojo, baja el oxígeno, sube la conductividad. A los ~10 s sale **"⚠ Nueva alerta: Cambio brusco en el sensor"** (*"sensores simulados de la fase 2, con la misma electrónica que los reales"*) | — |
| 2 min | **4 Reportes** | El jurado escanea el QR y reporta **con foto** en la zona **Entrada del Atoyac** (ahí está el sensor). Llega **"📩 Nuevo reporte por Telegram"**, la tarjeta con la etiqueta de la IA (*"la IA sugiere"*) y **"🔴 Alerta confirmada"**. El operador pulsa **Válido** (*"una persona decide"*) | Reporta desde su teléfono |
| 1 min | **3 Alertas** | La alerta del sensor aparece **Confirmada** (Sensor IoT + Reporte ciudadano). **Marcar atendida** y mostrar el filtro "Atendidas" | — |
| 1 min | **1 Resumen** | Cierre: el reporte aparece en el mapa y no quedan pendientes nuevos. *"El día que haya sensores, sólo se conectan."* | — |

> Díganlo al empezar: los mapas, las series y las alertas del satélite son **datos reales** de Sentinel-2; los sensores son **simulados** (fase 2).
>
> Para que la alerta del sensor se confirme, el reporte debe ser de la **Entrada del Atoyac** y llegar en las 2 horas siguientes. Si el jurado elige otra zona, el reporte llega igual, pero la alerta queda *pendiente*: úsenlo para explicar que una sola fuente no basta.

### Arranque el día de la presentación

1. Abrir **Docker Desktop** y esperar a que diga que está corriendo.
2. Cerrar `tablero.html` si estaba abierto con el bot (o pulsar *Desconectar*): Telegram sólo atiende a un programa a la vez.
3. Doble clic en **`iniciar.bat`** (una sola ventana negra; si ya estaba abierto, sólo abre el navegador).
4. Revisar que **Sensores, Bot e IA de fotos** estén en verde. Si el bot dice *reconectando*, esperar 30 s.
5. Unos minutos antes de pasar: pestaña **6 Configuración → "Preparar demo"** (dos clics). Borra los reportes y alertas de prueba y reabre las alertas atendidas; el satélite, Conagua y los ejemplos de la IA se conservan.
6. Volver a la pestaña **1 Resumen**, pantalla completa (F11).

### Si algo falla

| Problema | Qué hacer |
| --- | --- |
| No hay internet (el bot no recibe) | Pestaña 4 → **Captura manual**: el operador captura el reporte del jurado con foto. Todo lo demás funciona sin internet |
| Sensores en gris | Docker Desktop no está abierto: abrirlo y esperar unos segundos |
| La alerta del sensor no sale | Esperar 15 s: la alerta compara contra las 5 lecturas anteriores (una cada 3 s) |
| Atlachia no arranca | Plan B: abrir `tablero.html` (versión anterior, con `ayudante_fotos.py` y el token) |

## 3. Preguntas probables del jurado (6 minutos)

Respuestas de 30 a 45 segundos para alcanzar a contestar varias.

| Pregunta | Respuesta corta |
| --- | --- |
| ¿Por qué no trajeron hardware? | El piloto es 100% software, con datos abiertos y costo casi cero. Pero la fase 2 ya está integrada: los 5 simuladores reproducen la parte eléctrica de los sensores DFRobot (voltaje, ruido, ADC del ESP32 y su curva de calibración) y mandan el mismo registro que mandará el hardware real. El botón "Simular descarga" lo demuestra. |
| ¿Qué tan confiable es el satélite? | Es una **estimación**, no una medición de laboratorio. Lo comparamos con Conagua: los dos sitios con más sólidos suspendidos en 2025 son los únicos donde nuestro modelo de IA ve lirio (56–60% de las imágenes); en los otros dos, 0%. La turbidez no sirve aquí (la dominan las algas), por eso usamos clorofila y lirio. Sirve para decidir dónde y cuándo muestrear. |
| ¿Funciona en el río Atoyac? | Con satélite no: el río es demasiado angosto para los píxeles de 10 a 20 m. Ahí entran los reportes ciudadanos y, en la fase 2, los sensores en las entradas del Atoyac y del Alseseca. |
| ¿Y en temporada de lluvias, con nubes? | De junio a octubre se descartan muchas imágenes. Los reportes ciudadanos y los sensores cubren esos huecos. |
| ¿Cómo evitan reportes falsos? | Una IA de visión revisa cada foto: si no parece de la presa o no coincide con lo reportado, la marca para revisión. Acierta 73% (61% sin nuestros ejemplos) en 41 fotos de prueba; por eso **sugiere** y una persona decide. Además, un reporte solo no confirma nada: una alerta se confirma cuando coinciden dos fuentes. |
| ¿Por qué 73% y no más? | Son pocas fotos y ninguna es de Valsequillo. Medimos honestamente: quitamos fotos repetidas que inflaban el resultado. El siguiente paso es juntar fotos reales de la presa; el tablero ya permite agregarlas como ejemplos. |
| ¿Por qué no señalan a las empresas? | El sistema dice dónde y cuándo; determinar quién le toca a la autoridad. Así se protege a quien reporta y se evitan acusaciones sin prueba. |
| ¿El lirio no confunde al satélite? | Por eso entrenamos un Random Forest que separa agua, lirio, vegetación de tierra y tierra: 94% de exactitud en puntos de prueba (kappa 0.92). Según el modelo, el lirio cubre en promedio 53% del espejo de agua. |
| ¿Dónde usaron inteligencia artificial? | En el lirio: Random Forest con 10 bandas de Sentinel-2 y 4 índices, entrenado con puntos etiquetados a mano en tres temporadas (la primera versión, sólo con lluvias, acertaba 51% en secas; con las tres, 89–98%). Y en las fotos: CLIP, un modelo de visión preentrenado, ajustado con ejemplos nuestros (61% → 73%). |
| ¿Cómo está construido? ¿Escala? | Python (FastAPI) con PostgreSQL + PostGIS en Docker; el bot y la IA corren en el servidor. Un ESP32 real sólo tiene que mandar su lectura a `/api/observaciones` con el formato común. Para otra presa se cambia el área y los sitios de Conagua. |
| ¿Cuánto cuesta y cómo se sostiene? | Earth Engine es gratis para uso académico y no comercial; para operar como servicio se migra a Copernicus Data Space. El software es abierto. Los sensores cuestan ≈ 5,450 MXN por nodo, sin ESP32, batería ni caja. |
| ¿Qué pasa con la privacidad? | Se registra dónde y cuándo, no quién. Del chat de Telegram no se guarda nada y no se publican datos personales. |

## 4. Lista de preparación

- [ ] Revisar si las reglas del HackaTec permiten preparar datos antes del evento
- [x] Datos reales: Sentinel-2 (77 imágenes), Conagua (4 sitios) y modelo de lirio
- [x] Atlachia en Python: base de datos, sensores, alertas, IA de fotos, bot y tablero
- [x] Ensayo completo de la interacción (descarga → alerta → reporte → confirmada → atendida)
- [ ] Imprimir el código QR del bot (descargarlo de http://127.0.0.1:8000/api/bot/qr.png)
- [ ] Grabar un video de respaldo de la demo (por si falla internet)
- [ ] Juntar fotos propias de espuma y agua turbia y agregarlas como ejemplos (pestaña 6)
- [ ] Ensayar el pitch con cronómetro (7 min exactos) y repartir quién responde cada tema
- [ ] Pasar a quien lleva el plan de negocio las cifras nuevas (IA de fotos: 61% → 73%)
