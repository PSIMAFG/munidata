# MuniData - Dashboard BI Municipal

Plataforma de análisis de gastos en personal de Salud Municipal basada en datos de Transparencia Activa (Chile). Dashboard interactivo estilo Power BI con scraping automatizado del Portal de Transparencia.

## Arquitectura

```
munidata/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/              # Migraciones DB
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Settings (env vars)
│   │   ├── database.py       # SQLAlchemy async engine
│   │   ├── models/           # SQLAlchemy models (honorarios, contrata, planta, escalas, audit)
│   │   ├── schemas/          # Pydantic schemas (filters, pagination)
│   │   ├── api/              # Routers: health, dashboard, records, scrape, audit, export, filters
│   │   ├── services/         # Business logic: dashboard aggregations, audit, convenio rules
│   │   ├── scraper/          # Playwright scraper for Portal Transparencia
│   │   └── jobs/             # Celery tasks for background scraping
│   └── data/                 # Raw downloaded files (mounted volume)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx           # Router + layout
        ├── main.tsx          # Entry point
        ├── types/            # TypeScript interfaces
        ├── stores/           # Zustand global filter store (URL sync)
        ├── services/         # API client (axios)
        ├── hooks/            # React hooks for data fetching
        ├── components/
        │   ├── layout/       # AppLayout (sidebar + filter panel)
        │   ├── filters/      # FilterPanel (global filters)
        │   ├── charts/       # ECharts: TimeseriesChart, BreakdownChart
        │   ├── tables/       # RecordsTable (server-side pagination)
        │   ├── dashboard/    # KPICards
        │   └── audit/        # Audit components
        └── pages/
            ├── SetupPage     # Config municipio + lanzar scraper
            ├── DashboardPage # Dashboard principal BI
            ├── ConveniosPage # Vista detalle convenios
            ├── ContractTypePage # Honorarios vs Contrata vs Planta
            ├── AuditPage     # Auditoría de remuneraciones
            └── RecordsPage   # Tablas detalle con export
```

## Stack Tecnológico

- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL, Celery + Redis, Playwright
- **Frontend**: React 18, TypeScript, Vite, Ant Design, ECharts, Zustand, TanStack Table
- **Infra**: Docker Compose

## Levantar con Docker Compose

```bash
# Clonar repo
git clone <repo-url> && cd munidata

# Levantar todos los servicios
docker-compose up --build

# Acceder:
#   Frontend: http://localhost:5173
#   Backend API: http://localhost:8000
#   API Docs: http://localhost:8000/docs
```

## Levantar Local (Windows / macOS / Linux)

### Requisitos
- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- Redis

### Backend

```bash
cd backend

# Crear virtualenv
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

# Variables de entorno (o crear .env)
set DATABASE_URL=postgresql+asyncpg://munidata:munidata@localhost:5432/munidata
set DATABASE_URL_SYNC=postgresql://munidata:munidata@localhost:5432/munidata
set REDIS_URL=redis://localhost:6379/0
set CELERY_BROKER_URL=redis://localhost:6379/1

# Crear DB
createdb munidata  # o desde pgAdmin

# Iniciar API
uvicorn app.main:app --reload --port 8000

# En otra terminal: iniciar Celery worker
celery -A app.jobs.celery_app worker -l info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Abre http://localhost:5173
```

## Uso

1. **Setup**: Ir a `/setup`, ingresar código de municipio (ej: `280` para San Antonio)
2. **Extraer**: Seleccionar año, meses y tipos de datos, presionar "Iniciar Extracción"
3. **Dashboard**: Ir a `/dashboard` para ver KPIs, gráficos y tablas interactivas
4. **Filtros**: Usar panel lateral para filtrar por mes, convenio, tipo de vínculo
5. **Cross-filter**: Click en cualquier gráfico para filtrar todo el dashboard
6. **Export**: Botones CSV y Excel disponibles en cada vista

## API Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /health` | Health check + estado DB |
| `POST /api/scrape-runs` | Lanzar extracción |
| `GET /api/scrape-runs` | Listar extracciones |
| `GET /api/dashboard/kpis` | KPIs agregados |
| `GET /api/dashboard/timeseries` | Serie temporal (por mes/convenio/vínculo) |
| `GET /api/dashboard/breakdown` | Breakdown (top convenios/vínculos/profesionales) |
| `GET /api/records/honorarios` | Registros honorarios (paginados) |
| `GET /api/records/contrata` | Registros contrata (paginados) |
| `GET /api/records/planta` | Registros planta (paginados) |
| `GET /api/filters/options` | Opciones dinámicas de filtros |
| `GET /api/audit/summary` | Resumen auditoría |
| `GET /api/audit/exceptions` | Excepciones de auditoría |
| `POST /api/audit/run` | Ejecutar auditoría |
| `GET /api/export/csv` | Export CSV filtrado |
| `GET /api/export/excel` | Export Excel consolidado |

Todos los endpoints de dashboard aceptan filtros via query params:
`municipality_code`, `area`, `year`, `months`, `contract_types`, `convenios`, `search_text`

## Municipios de Ejemplo

| Código | Municipio |
|---|---|
| 280 | San Antonio |
| 345 | Valparaíso |
| 301 | Santiago |

El código genera `org=MU{code:03d}` para el Portal de Transparencia.

## License

All rights reserved.
This repository is public for viewing and evaluation purposes.
Any use, modification, distribution, or commercial use requires
explicit written permission from the author.
