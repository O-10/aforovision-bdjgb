# AforoVision · BDJGB

Aplicación web de **visión computarizada para medir y controlar el aforo** en la Biblioteca Departamental Jorge Garcés Borrero (Santiago de Cali), con alertas automáticas cuando se supera el límite autorizado.

**Desarrollado por:** Oscar Iván Solarte Cerón · 3154013707 · Profesional en Seguridad y Salud en el Trabajo · Resolución 3702 de 2023.

## Aforos parametrizados

| Zona | Aforo autorizado | Soporte técnico |
|---|---:|---|
| Comicteca (Piso 2) | **60 personas** | 302 m² / 4,6 m² por persona = 66 teóricos; margen preventivo de 6 por mobiliario y circulación (SiGPRO / Positiva ARL; Mapa Maestro SG-SST). |
| El Domo · Piso 2 (ARTECA) | **56 personas** | 257,66 m² netos / 4,6 m² por persona. NSR-10 Título K, galería cultural. |
| El Domo · Piso 3 (ARTECA) | **54 personas** | 250,00 m² netos / 4,6 m² por persona. Combinado P2+P3 = 110. |
| Plazoleta de Cultura | **80 personas** | Valor parametrizado por instrucción de la Biblioteca. ⚠ El concepto de SST (Angela Berrío, 28/10/2026) recomienda 70–75 sentados, 60–65 en movimiento y limita el ingreso a 60 por las gradas; la app muestra esta nota y debe validarse antes de operar. |

El Domo opera por defecto en **modo alterno** (Piso 2 → Piso 3 cada 15 minutos, configurable) y permite también el **modo ambos pisos** con control del aforo combinado de 110.

## Puesta en marcha

```powershell
cd "C:\Users\Oscar\Documents\Default Project\aforovision_bdjgb"
.\iniciar.bat
```

Luego abrir <http://127.0.0.1:8000>.

Alternativamente:

```powershell
py -m uvicorn server:app --host 127.0.0.1 --port 8000
```

La primera pantalla usa el **modo DEMO** (escena sintética etiquetada como *SIMULACIÓN*) para que puedas probar tableros, alertas y reportes sin cámaras. Para operar con visión real, en el panel *Configuración de la fuente* selecciona:

- `camara` con valor `0` (webcam) o una URL `rtsp://...`;
- `video` o `imagen` con una ruta local;
- ROI normalizado (0–1) para contar solo dentro del área útil;
- FPS y confianza según el caso.

También existe el **conteo manual verificable** (+/−, fijar valor y restaurar automático), pensado como respaldo cuando la cámara falla o el operario debe confirmar.

## Consulta por área

El panel **Consultar aforo por área** muestra cuatro botones (Comicteca, Domo P2, Domo P3 y Plazoleta). Al elegir uno:

- se activa solo esa zona y las demás pasan a “En espera”;
- se muestra un conteo grande con el cupo y el estado;
- el video y las alertas se enfocan en el área elegida;
- el botón **← Ver todas las zonas** restaura el monitoreo simultáneo.

Si el área elegida está en DEMO, el aviso lo indica y hay que configurar su cámara en *Configuración de la fuente* para medir en tiempo real. Si es el Domo, el modo alterno ajusta automáticamente el piso activo al área consultada.

> **Cámara compartida:** si varias áreas usan la misma fuente (por ejemplo el índice `0`), la app lo advierte. Una sola cámara física solo puede observar un lugar a la vez: diríjala al área que está consultando o asigne una cámara/RTSP distinta por zona para medirlas de forma independiente.

## Enlace público para celulares

Para compartir el aforo con cualquier persona que tenga el enlace, ejecuta:

```powershell
.\iniciar_publico.bat
```

Ese script levanta tres piezas:

1. el motor de visión (`server.py`, puerto 8000) si no está activo;
2. un **servidor público filtrado** (`public_server.py`, puerto 8001) con la vista móvil;
3. un túnel HTTPS de Cloudflare que entrega una URL pública y la copia al portapapeles.

La dirección **vigente** está siempre en `data/enlace_publico.txt` (y se copia al portapapeles al ejecutar el script). Cópiala de ahí; no uses enlaces de ejemplos ni versiones anteriores, porque dejan de funcionar al reiniciar el túnel.

```
type data\enlace_publico.txt
```

Esa página:

- se adapta al ancho del celular y actualiza los datos cada 2 segundos;
- permite elegir el área y **activar su medición por visión computarizada**, mostrando el conteo grande con su cupo. El conteo se comparte entre todos los visitantes: con la cámara del PC el área enfocada es la misma para todos; con la cámara de un celular, ese celular pasa a ser la fuente activa;
- muestra alertas recientes, créditos técnicos y aviso de cámara compartida;
- permite descargar el reporte CSV;
- **no expone** cambio de fuentes, conteo manual ni configuración: quien recibe el link solo puede consultar y medir con su propia cámara.

### Medir con la cámara del celular

Dentro de la página pública:

1. toque el área que quiere medir (Comicteca, Domo P2, Domo P3 o Plazoleta);
2. pulse **📷 Usar la cámara de mi celular para medir**;
3. acepte el permiso de cámara del navegador y apunte al área;
4. el celular envía ~2 fotogramas por segundo al servidor, donde YOLOv8n cuenta personas. **La pantalla muestra la imagen de vuelta con una caja sobre cada persona detectada**; el video crudo del teléfono queda oculto para que no haya confusión entre “ver la cámara” y “ver el conteo”. La vista se actualiza sola y el conteo queda compartido para quienes abran el enlace;
5. pulse **■ Detener envío** cuando termine. El último conteo y el evento `celular` quedan registrados en el CSV.

Si no aparecen cajas, revise que haya buena luz, que las personas estén visibles de frente y que exista `modelos/yolov8n.pt`. Debajo de la imagen se indica `Midiendo <área>: <conteo>/<cupo> ... · las cajas señalan las personas detectadas`.

Requisitos: abrir el enlace por **HTTPS** (navegadores bloquean la cámara en HTTP, salvo `localhost`), mantener la pantalla encendida y permitir el permiso. No hay que instalar ninguna app. Si varios celulares envían video, el último en hacerlo se convierte en la fuente activa.

> **Importante:** el túnel gratuito genera una dirección nueva cada vez que se reinicia y **solo funciona mientras tu PC siga encendido y con internet**. Para que cualquier persona use la app “en cualquier momento”, despliega en la nube (sección siguiente). Ya no se necesita cámara local: la medición la hace el celular del visitante.

## Funcionamiento 24/7 (sin depender del PC)

La medición con cámara del celular permite ejecutar todo en la nube: el servidor recibe JPEG, corre YOLOv8n y devuelve conteo + imagen anotada. Dejé preparados `Dockerfile`, `.dockerignore`, `render.yaml` y `Procfile`.

### Opción recomendada: Render, plan siempre activo

1. Crear cuenta en <https://render.com> y conectar el repositorio `https://github.com/O-10/aforovision-bdjgb`. Git ya quedó inicializado y el código subido; `herramientas/cloudflared.exe` y `data/` no se suben.
2. **New → Blueprint** y elegir `render.yaml`. Render usa `Dockerfile` y aplica:
   - plan de compute `0.5c-512mb` (0.5 CPU / 512 MB, **USD 7/mes**, siempre activo; el plan `free` se suspende por inactividad);
   - `AFORO_ORIGIN=http://127.0.0.1:8000` para el motor interno;
   - `AFORO_DATA_DIR=/data` con disco persistente de 1 GB.
3. El contenedor levanta dos procesos: `server.py` en `8000` (solo interno) y `public_server.py` en `$PORT` con HTTPS público.
4. Compartir la URL que asigne Render, por ejemplo `https://aforo-bdjgb.onrender.com`. Para usar `https://aforo.biblioteca.gov.co`, hay que ser titular del dominio, comprarlo en un registrador y agregarlo en Render con su DNS.
5. Verificar `/health` y descargar `/api/reporte.csv` desde el celular.

**Costo estimado:** workspace Hobby USD 0 + compute USD 7/mes + disco 1 GB USD 0,25/mes ≈ **USD 7,25/mes** (ancho de banda: 5 GB incluidos, después USD 0,15/GB). El subdominio `*.onrender.com` con HTTPS es gratis; los dominios propios se compran aparte (Render incluye 2 sin cargo en Hobby).

> El plan de compute y el dominio son **cosas distintas**: el plan paga el servidor encendido 24/7; el dominio es solo el nombre. Puedes usar el subdominio gratis y no comprar dominio. `config.json`, `eventos.jsonl` y `reportes/` quedan en `/data` y sobreviven a reinicios. En la nube **no se usa la cámara del PC**: cada visita mide con su propio teléfono.

### Probar la imagen antes de subir (opcional)

```powershell
docker build -t aforo-bdjgb .
docker run --rm -p 8001:8001 -e AFORO_ORIGIN=http://127.0.0.1:8000 -e AFORO_DATA_DIR=/data aforo-bdjgb
```

Abrir `http://localhost:8001` (en local sí se permite cámara por HTTP; en internet, solo HTTPS).

## Alertas

- **Normal:** < 80 % del aforo.
- **Preventiva:** ≥ 80 % y ≤ 100 %.
- **Excedido:** > 100 % → banner rojo, aviso sonoro (si se activa), evento en el registro y recomendación de suspender el ingreso. El aviso se reitera cada 20 s mientras persista el exceso y se registra la normalización al volver al rango.

Los eventos se guardan en `data/eventos.jsonl`. El botón **Reporte CSV** (o `GET /api/reporte.csv`) genera un archivo con fecha que contiene:

1. **`RESUMEN_POR_AREA`** → una fila por zona con su conteo, cupo, porcentaje, exceso y estado al momento del corte.
2. **`TOTAL_GENERAL`** → el total de personas y cuántas áreas estaban activas.
3. **`REGISTRO_EVENTOS`** → el historial completo de alertas, cambios y consultas para trazabilidad SG-SST.

Cada descarga también **queda registrada**: se agrega un evento `reporte` al historial y se guarda una copia del CSV en `data/reportes/reporte_aforo_AAAAMMDD_HHMMSS.csv`. El mismo comportamiento aplica al enlace público.

## Arquitectura

- `config.py`: zonas, aforos, fuentes documentales y configuración persistente.
- `vision.py`: detector YOLOv8n local (clase *person*), respaldo HOG/SVM de OpenCV, generador demo y anotación de fotogramas.
- `nucleo.py`: hilos de captura por zona, suavizado temporal (mediana), modo alterno del Domo, evaluación de alertas y reportes.
- `server.py`: API FastAPI, streaming MJPEG y archivos estáticos (panel de operación).
- `public_server.py`: API pública filtrada (consulta, medición con cámara del celular y CSV); bloquea video, fuentes y configuración.
- `static/ver.html`: vista móvil pública; `static/index.html`: tablero de operación.
- `iniciar_publico.bat` / `iniciar_publico.ps1`: arranque del enlace HTTPS compartible.
- `herramientas/cloudflared.exe`: cliente del túnel (no debe subirse a GitHub).
- `Dockerfile` / `render.yaml` / `Procfile`: despliegue 24/7 en la nube con `/data` persistente.
- `modelos/yolov8n.pt`: pesos del modelo incluidos para operación offline.

## Utilidades de verificación

- `probar_camaras.py`: lista los índices de cámara disponibles en el equipo.
- `verificar_frame.py`: toma un fotograma del stream real y muestra las detecciones del modelo.

## API principal

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/estado` | Snapshot completo de zonas, Domo, resumen y eventos. |
| GET | `/api/video/{zona}` | Stream MJPEG anotado. |
| POST | `/api/zonas/{zona}/fuente` | Configurar cámara/video/imagen/demo/manual. |
| POST | `/api/zonas/{zona}/manual` | Ajustar conteo con `{"delta": 1}`. |
| POST | `/api/zonas/{zona}/restaurar` | Volver al conteo automático. |
| POST | `/api/domo` | `{"modo":"alterno|ambos","piso_activo":"domo_p2","minutos":15}`. |
| GET | `/api/eventos` | Historial reciente. |
| POST | `/api/celular/frame` | Fotograma JPEG en base64 desde un celular (`{"zona":"comicteca","frame":"..."}`). Expuesto también en el enlace público. |
| GET | `/api/reporte.csv` | Conteo por área + total general + historial; guarda copia en `data/reportes/`. |
| GET | `/api/fuentes` | Trazabilidad documental. |

> La visión computarizada es una **herramienta de apoyo**: no sustituye la verificación del operario, las rutas de evacuación libres ni los condicionantes de los conceptos SG-SST.
