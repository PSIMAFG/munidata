"""Synchronous scrape pipeline executed by Celery worker."""
import datetime
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.personnel import ScrapeRun, ScrapeRunStatus, HonorariosRecord, ContrataRecord, PlantaRecord
from app.scraper.portal_scraper import PortalScraper
from app.services.convenio_rules import derive_convenio

logger = logging.getLogger(__name__)


def execute_scrape_pipeline(scrape_run_id: int) -> dict:
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC)

    with Session(engine) as db:
        run = db.get(ScrapeRun, scrape_run_id)
        if not run:
            return {"error": "ScrapeRun not found"}

        run.status = ScrapeRunStatus.RUNNING
        run.started_at = datetime.datetime.utcnow()
        db.commit()

        total_loaded = 0
        org_code = f"MU{int(run.municipality_code):03d}"

        try:
            scraper = PortalScraper(org_code=org_code)
            kinds = run.contract_types or ["honorarios"]

            for kind in kinds:
                kind_lower = kind.lower()
                if kind_lower == "honorarios":
                    total_loaded += _scrape_honorarios(
                        db, scraper, run, org_code
                    )
                elif kind_lower == "contrata":
                    total_loaded += _scrape_contrata(
                        db, scraper, run, org_code
                    )
                elif kind_lower == "planta":
                    total_loaded += _scrape_planta(
                        db, scraper, run, org_code
                    )
                elif kind_lower == "escalas":
                    _scrape_escalas(db, scraper, run, org_code)

            run.status = ScrapeRunStatus.COMPLETED
            run.records_loaded = total_loaded
            run.completed_at = datetime.datetime.utcnow()
            db.commit()

            scraper.close()
            return {"status": "completed", "records_loaded": total_loaded}

        except Exception as e:
            logger.exception(f"Scrape pipeline failed: {e}")
            run.status = ScrapeRunStatus.FAILED
            run.error_message = str(e)[:2000]
            run.completed_at = datetime.datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": str(e)}


def _scrape_honorarios(db: Session, scraper: PortalScraper, run: ScrapeRun, org_code: str) -> int:
    count = 0
    for month in run.months:
        try:
            records = scraper.scrape_honorarios(
                area=run.area, year=run.year, month=month
            )
            for rec in records:
                hon = HonorariosRecord(
                    municipality_code=run.municipality_code,
                    area=run.area,
                    year=run.year,
                    month=month,
                    scrape_run_id=run.id,
                    nombre=rec.get("nombre"),
                    rut=rec.get("rut"),
                    descripcion_funcion=rec.get("descripcion_funcion"),
                    calificacion_profesional=rec.get("calificacion_profesional"),
                    fecha_inicio=rec.get("fecha_inicio"),
                    fecha_termino=rec.get("fecha_termino"),
                    remuneracion_bruta=_parse_float(rec.get("remuneracion_bruta")),
                    remuneracion_liquida=_parse_float(rec.get("remuneracion_liquida")),
                    monto_total=_parse_float(rec.get("monto_total")),
                    observaciones=rec.get("observaciones"),
                    convenio=derive_convenio(rec.get("observaciones", "")),
                )
                db.add(hon)
                count += 1
            db.commit()
            logger.info(f"Honorarios month {month}: {len(records)} records")
        except Exception as e:
            logger.error(f"Error scraping honorarios month {month}: {e}")
            db.rollback()
    return count


def _scrape_contrata(db: Session, scraper: PortalScraper, run: ScrapeRun, org_code: str) -> int:
    count = 0
    for month in run.months:
        try:
            records = scraper.scrape_contrata(
                area=run.area, year=run.year, month=month
            )
            for rec in records:
                cont = ContrataRecord(
                    municipality_code=run.municipality_code,
                    area=run.area,
                    year=run.year,
                    month=month,
                    scrape_run_id=run.id,
                    nombre=rec.get("nombre"),
                    rut=rec.get("rut"),
                    grado_eus=rec.get("grado_eus"),
                    cargo=rec.get("cargo"),
                    calificacion_profesional=rec.get("calificacion_profesional"),
                    region=rec.get("region"),
                    asignaciones=_parse_float(rec.get("asignaciones")),
                    remuneracion_bruta=_parse_float(rec.get("remuneracion_bruta")),
                    remuneracion_liquida=_parse_float(rec.get("remuneracion_liquida")),
                    fecha_inicio=rec.get("fecha_inicio"),
                    fecha_termino=rec.get("fecha_termino"),
                    observaciones=rec.get("observaciones"),
                    horas=rec.get("horas"),
                )
                db.add(cont)
                count += 1
            db.commit()
            logger.info(f"Contrata month {month}: {len(records)} records")
        except Exception as e:
            logger.error(f"Error scraping contrata month {month}: {e}")
            db.rollback()
    return count


def _scrape_planta(db: Session, scraper: PortalScraper, run: ScrapeRun, org_code: str) -> int:
    count = 0
    for month in run.months:
        try:
            records = scraper.scrape_planta(
                area=run.area, year=run.year, month=month
            )
            for rec in records:
                pla = PlantaRecord(
                    municipality_code=run.municipality_code,
                    area=run.area,
                    year=run.year,
                    month=month,
                    scrape_run_id=run.id,
                    nombre=rec.get("nombre"),
                    rut=rec.get("rut"),
                    grado_eus=rec.get("grado_eus"),
                    cargo=rec.get("cargo"),
                    calificacion_profesional=rec.get("calificacion_profesional"),
                    region=rec.get("region"),
                    asignaciones=_parse_float(rec.get("asignaciones")),
                    remuneracion_bruta=_parse_float(rec.get("remuneracion_bruta")),
                    remuneracion_liquida=_parse_float(rec.get("remuneracion_liquida")),
                    fecha_inicio=rec.get("fecha_inicio"),
                    fecha_termino=rec.get("fecha_termino"),
                    observaciones=rec.get("observaciones"),
                    horas=rec.get("horas"),
                )
                db.add(pla)
                count += 1
            db.commit()
            logger.info(f"Planta month {month}: {len(records)} records")
        except Exception as e:
            logger.error(f"Error scraping planta month {month}: {e}")
            db.rollback()
    return count


def _scrape_escalas(db: Session, scraper: PortalScraper, run: ScrapeRun, org_code: str):
    try:
        scraper.scrape_escalas(year=run.year)
        logger.info("Escalas downloaded")
    except Exception as e:
        logger.error(f"Error scraping escalas: {e}")


def _parse_float(val) -> float | None:
    """Parse Chilean currency format to float.

    Handles: '$ 41.712', '$41.712', '1.234.567', '41712', '1234,56', empty strings.
    Chilean format uses '.' as thousand separator and ',' as decimal separator.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = str(val).strip()
        if not cleaned or cleaned.lower() in ("", "-", "no informa", "no aplica"):
            return None
        # Remove currency symbol and spaces
        cleaned = cleaned.replace("$", "").replace("\xa0", "").strip()
        # Chilean format: '.' is thousands, ',' is decimal
        # If there's a comma, it's a decimal separator
        if "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # Only dots = thousand separators (e.g. "1.234.567")
            cleaned = cleaned.replace(".", "")
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None
