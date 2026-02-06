# Prompt para Claude Code: Reescribir Scraper de Portal Transparencia Municipal

## Contexto del Proyecto

Tenemos un proyecto FastAPI + React en `/home/user/munidata/` que es un dashboard BI para datos municipales de transparencia Chile. Actualmente el scraper usa **Playwright** (navegador headless) para extraer datos del Portal Transparencia, pero es pesado, lento y frágil.

Necesitamos **reescribir el scraper** para usar **HTTP directo (httpx) + BeautifulSoup** en vez de Playwright, similar a como funciona este scraper exitoso de la Universidad de Chile:

```python
# Referencia: Scraper que SÍ funciona para transparencia Chile
# Usa urllib + BeautifulSoup para extraer tablas HTML directamente
# Sin Playwright ni Selenium - puro HTTP + parsing HTML
from bs4 import BeautifulSoup
import urllib.request

def scrapeTransparencia(url):
    fuente = BeautifulSoup(urllib.request.urlopen(url).read(), "html.parser")
    enlaces = fuente.find_all("div", {"class": "content__description"})
    # ... extrae links a páginas mensuales

def scrapeTablas(links):
    for link in links:
        fuente = BeautifulSoup(urllib.request.urlopen(link).read(), "html.parser")
        tabla = fuente.find_all("tr")
        # ... parsea las filas de la tabla
```

## Arquitectura Existente

### Backend (FastAPI)
- `backend/app/scraper/portal_scraper.py` - Scraper actual con Playwright (778+ líneas) - **REESCRIBIR**
- `backend/app/jobs/scrape_pipeline.py` - Pipeline Celery que llama al scraper
- `backend/app/jobs/celery_app.py` - Config Celery
- `backend/app/models/personnel.py` - Modelos SQLAlchemy: `HonorariosRecord`, `ContrataRecord`, `PlantaRecord`, `ScrapeRun`
- `backend/app/services/convenio_rules.py` - Reglas para derivar convenio desde observaciones
- `backend/app/config.py` - Settings (DATABASE_URL, REDIS_URL, etc.)

### Datos Objetivo
Scrapeamos del Portal Transparencia Chile:
- **URL base**: `https://www.portaltransparencia.cl/PortalPdT/pdtta?codOrganismo=MU{code}`
- Donde `{code}` es el código municipal (ej: "280" para San Antonio)
- **Secciones**: Personal y remuneraciones (sección 04):
  - 4.1.1: Personal de Planta
  - 4.1.2: Personal a Contrata
  - 4.1.3: Personas contratadas a honorarios
  - 4.1.4: Escala de remuneraciones

### Campos por tipo de registro

**Honorarios**: nombre, rut, descripcion_funcion, calificacion_profesional, fecha_inicio, fecha_termino, remuneracion_bruta, remuneracion_liquida, monto_total, observaciones, unidad_monetaria

**Contrata/Planta**: nombre, rut, grado_eus, cargo, calificacion_profesional, region, asignaciones, remuneracion_bruta, remuneracion_liquida, fecha_inicio, fecha_termino, observaciones, horas

### Dependencias disponibles (requirements.txt)
```
httpx==0.28.1
pandas==2.2.3
beautifulsoup4  # AGREGAR
lxml             # AGREGAR para parser rápido
```

## Tarea: Reescribir el Scraper

### Paso 1: Crear nuevo scraper HTTP en `backend/app/scraper/http_scraper.py`

Crear un nuevo archivo `http_scraper.py` que reemplace la funcionalidad de `portal_scraper.py` usando httpx + BeautifulSoup. **NO modificar portal_scraper.py** - dejarlo como fallback.

El nuevo scraper debe:

1. **Usar httpx (no urllib)** para HTTP requests con:
   - Session/Client con cookies persistentes
   - User-Agent de Chrome real
   - Timeouts generosos (30s)
   - Reintentos automáticos (3 intentos con backoff exponencial)
   - Follow redirects

2. **Estrategia de navegación multi-nivel**:

   **Nivel 0 - URLs directas del portal**: Intentar acceder directamente a las URLs de datos:
   ```
   https://www.portaltransparencia.cl/PortalPdT/pdtta/-/ta/MU{code}/{year}/A/{area}/{seccion}
   ```
   Donde seccion es: "4.1.1" (planta), "4.1.2" (contrata), "4.1.3" (honorarios)

   **Nivel 1 - Descarga CSV directa**: Buscar en el HTML links a archivos .csv, .xlsx, .xls y descargarlos

   **Nivel 2 - Parsing de tablas HTML**: Usar BeautifulSoup para extraer tablas `<table>` con datos:
   - Identificar la tabla correcta (la que tenga columnas como "Nombre", "RUT", "Remuneración", etc.)
   - Extraer headers de `<thead>` o primera fila `<tr>`
   - Extraer datos de `<tbody>` filas
   - Manejar paginación: buscar links "Siguiente", ">>", o parámetros `?page=N`

   **Nivel 3 - API interna del portal**: El portal Liferay/JSF puede tener endpoints AJAX internos. Intentar:
   - Inspeccionar el HTML en busca de `<form>` con action URLs
   - Buscar URLs en scripts `<script>` que contengan endpoints de datos
   - Buscar atributos `data-*` que contengan URLs de recursos

3. **Exploración inteligente del portal**:
   ```python
   class HTTPScraper:
       def __init__(self, org_code: str):
           self.org_code = org_code
           self.client = httpx.Client(...)
           self.base_url = f"https://www.portaltransparencia.cl/PortalPdT/pdtta"

       def _discover_data_urls(self, area: str, year: int) -> dict:
           """Navega la página principal y descubre URLs de datos para cada sección."""
           # GET página principal del organismo
           # Parsear con BeautifulSoup
           # Encontrar links a secciones de personal
           # Retornar dict con URLs por tipo

       def _try_csv_download(self, url: str) -> list[dict] | None:
           """Busca y descarga CSV desde una página."""

       def _parse_html_table(self, url: str) -> list[dict]:
           """Extrae datos de tablas HTML en la página."""

       def _handle_pagination(self, soup, base_url) -> list[str]:
           """Encuentra y retorna URLs de páginas siguientes."""
   ```

4. **Normalización de datos** (reutilizar lógica existente):
   - Mapear columnas del portal a nombres estándar de la BD
   - Manejar formatos chilenos: puntos para miles, comas para decimales
   - Encodings: probar utf-8, latin-1, cp1252, iso-8859-1
   - CSV delimitadores: punto y coma (;), coma (,), tab

5. **Mantener la misma interfaz pública** que `portal_scraper.py`:
   ```python
   class HTTPScraper:
       def scrape_honorarios(self, area: str, year: int, month: int) -> list[dict]
       def scrape_contrata(self, area: str, year: int, month: int) -> list[dict]
       def scrape_planta(self, area: str, year: int, month: int) -> list[dict]
       def scrape_escalas(self, year: int)
       def close(self)
   ```

### Paso 2: Actualizar el pipeline para usar el nuevo scraper

Modificar `backend/app/jobs/scrape_pipeline.py` para:

1. Intentar primero con `HTTPScraper` (rápido, ligero)
2. Si falla o no obtiene datos, hacer fallback a `PortalScraper` (Playwright)
3. Loguear claramente qué estrategia se usó

```python
from app.scraper.http_scraper import HTTPScraper
from app.scraper.portal_scraper import PortalScraper

def execute_scrape_pipeline(scrape_run_id: int) -> dict:
    # ... setup ...

    # Intentar primero con HTTP directo (rápido)
    try:
        scraper = HTTPScraper(org_code=org_code)
        # ... scrape ...
        if total_loaded > 0:
            return result
    except Exception as e:
        logger.warning(f"HTTP scraper failed, falling back to Playwright: {e}")

    # Fallback a Playwright si HTTP no funcionó
    try:
        scraper = PortalScraper(org_code=org_code)
        # ... scrape ...
    except Exception as e:
        # ... handle error ...
```

### Paso 3: Agregar dependencias

Agregar a `backend/requirements.txt`:
```
beautifulsoup4==4.12.3
lxml==5.3.0
```

### Paso 4: Agregar script de diagnóstico

Crear `backend/scripts/test_scraper.py` para testing manual:

```python
"""Script para probar el scraper HTTP contra un municipio específico.

Uso:
    python -m scripts.test_scraper --code 280 --year 2025 --month 1
"""
import argparse
import json
import logging
from app.scraper.http_scraper import HTTPScraper

logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True, help="Código municipal (ej: 280)")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--type", choices=["honorarios", "contrata", "planta", "all"], default="all")
    args = parser.parse_args()

    scraper = HTTPScraper(org_code=f"MU{int(args.code):03d}")

    if args.type in ("honorarios", "all"):
        print(f"\n=== HONORARIOS {args.year}/{args.month:02d} ===")
        records = scraper.scrape_honorarios(area="Salud", year=args.year, month=args.month)
        print(f"Records: {len(records)}")
        if records:
            print(json.dumps(records[0], indent=2, ensure_ascii=False))

    # ... similar para contrata y planta ...

    scraper.close()

if __name__ == "__main__":
    main()
```

## Notas Importantes

1. **El portal puede usar JavaScript/AJAX** para cargar datos dinámicamente. En ese caso, buscar en el HTML:
   - Atributos `data-url`, `data-source`, `data-ajax-url`
   - Tags `<script>` que contengan URLs de API o endpoints JSON
   - Formularios `<form>` con action URLs que podrían servir endpoints de datos
   - Elementos `<iframe>` que carguen subpáginas con datos

2. **Manejar el caso donde HTTP no funcione**: Si el portal requiere JavaScript para renderizar, el HTTPScraper debe fallar graciosamente y loguear el HTML obtenido para diagnóstico, permitiendo que el fallback a Playwright tome el control.

3. **Guardar HTML de diagnóstico** en `DATA_DIR/raw/{org_code}/` para poder inspeccionar qué devuelve el portal y ajustar selectores.

4. **Formato chileno de números**: Los montos vienen como "1.234.567" (puntos para miles) o "$1.234.567". La función `_parse_float` existente en scrape_pipeline.py ya maneja esto.

5. **Encoding**: El portal chileno típicamente usa Latin-1 o UTF-8. Probar ambos.

6. **Rate limiting**: Agregar delays entre requests (1-2 segundos) para no sobrecargar el portal.

7. **NO borrar portal_scraper.py** - dejarlo como fallback. El nuevo http_scraper.py es el approach principal.
