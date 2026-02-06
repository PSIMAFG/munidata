"""Synchronous scrape pipeline executed by Celery worker.

Strategy: Try HTTPScraper first (fast, lightweight), fall back to
PortalScraper (Playwright) if HTTP scraping returns no data.
"""
import datetime
import logging
import traceback
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.personnel import ScrapeRun, ScrapeRunStatus, HonorariosRecord, ContrataRecord, PlantaRecord
from app.services.convenio_rules import derive_convenio

logger = logging.getLogger(__name__)


def _create_scraper(org_code: str, use_http: bool):
    """Create the appropriate scraper instance.

    Args:
        org_code: Organization code, e.g. "MU280".
        use_http: If True, return HTTPScraper; otherwise PortalScraper.
    """
    if use_http:
        from app.scraper.http_scraper import HTTPScraper
        return HTTPScraper(org_code=org_code)
    else:
        from app.scraper.portal_scraper import PortalScraper
        return PortalScraper(org_code=org_code)


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
        scraper = None
        errors = []
        scraper_type = "http"

        try:
            # ---- Phase 1: Try HTTP scraper (fast, no browser) ----
            logger.info(f"[{org_code}] Starting HTTP scraper (Phase 1)")
            try:
                scraper = _create_scraper(org_code, use_http=True)
                kinds = run.contract_types or ["honorarios"]

                for kind in kinds:
                    kind_lower = kind.lower()
                    try:
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
                    except Exception as e:
                        error_msg = f"HTTP scraper error ({kind_lower}): {e}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                        continue

                if total_loaded > 0:
                    logger.info(
                        f"[{org_code}] HTTP scraper succeeded: {total_loaded} records loaded"
                    )
                    scraper_type = "http"
                else:
                    logger.warning(
                        f"[{org_code}] HTTP scraper returned 0 records, "
                        "falling back to Playwright"
                    )
            except Exception as e:
                logger.warning(
                    f"[{org_code}] HTTP scraper initialization failed: {e}. "
                    "Falling back to Playwright."
                )
            finally:
                if scraper:
                    try:
                        scraper.close()
                    except Exception:
                        pass
                    scraper = None

            # ---- Phase 2: Playwright fallback (if HTTP got nothing) ----
            if total_loaded == 0:
                logger.info(f"[{org_code}] Starting Playwright scraper (Phase 2 fallback)")
                scraper_type = "playwright"
                errors_phase1 = list(errors)
                errors = []

                try:
                    scraper = _create_scraper(org_code, use_http=False)
                    kinds = run.contract_types or ["honorarios"]

                    for kind in kinds:
                        kind_lower = kind.lower()
                        try:
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
                        except Exception as e:
                            error_msg = f"Playwright scraper error ({kind_lower}): {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue
                except Exception as e:
                    error_msg = f"Playwright scraper failed: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

                # Combine errors from both phases if both failed
                if total_loaded == 0 and errors_phase1:
                    errors = errors_phase1 + errors

            if total_loaded > 0 or not errors:
                run.status = ScrapeRunStatus.COMPLETED
            else:
                run.status = ScrapeRunStatus.FAILED
            run.records_loaded = total_loaded
            run.completed_at = datetime.datetime.utcnow()
            if errors:
                run.error_message = "; ".join(errors)[:2000]
            db.commit()

            logger.info(
                f"[{org_code}] Pipeline finished: status={run.status.value}, "
                f"records={total_loaded}, scraper={scraper_type}"
            )

            return {
                "status": run.status.value.lower(),
                "records_loaded": total_loaded,
                "errors": errors,
                "scraper_used": scraper_type,
            }

        except Exception as e:
            logger.exception(f"Scrape pipeline failed: {e}")
            run.status = ScrapeRunStatus.FAILED
            run.error_message = f"{str(e)[:1500]}\n{traceback.format_exc()[-500:]}"
            run.completed_at = datetime.datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": str(e)}
        finally:
            if scraper:
                try:
                    scraper.close()
                except Exception:
                    pass


def _scrape_honorarios(db: Session, scraper, run: ScrapeRun, org_code: str) -> int:
    count = 0
    for month in run.months:
        try:
            logger.info(f"Scraping honorarios month {month} for {run.municipality_code}")
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
            logger.info(f"Honorarios month {month}: {len(records)} records loaded")
        except Exception as e:
            logger.error(f"Error scraping honorarios month {month}: {e}", exc_info=True)
            db.rollback()
    return count


def _scrape_contrata(db: Session, scraper, run: ScrapeRun, org_code: str) -> int:
    count = 0
    for month in run.months:
        try:
            logger.info(f"Scraping contrata month {month} for {run.municipality_code}")
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
            logger.info(f"Contrata month {month}: {len(records)} records loaded")
        except Exception as e:
            logger.error(f"Error scraping contrata month {month}: {e}", exc_info=True)
            db.rollback()
    return count


def _scrape_planta(db: Session, scraper, run: ScrapeRun, org_code: str) -> int:
    count = 0
    for month in run.months:
        try:
            logger.info(f"Scraping planta month {month} for {run.municipality_code}")
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
            logger.info(f"Planta month {month}: {len(records)} records loaded")
        except Exception as e:
            logger.error(f"Error scraping planta month {month}: {e}", exc_info=True)
            db.rollback()
    return count


def _scrape_escalas(db: Session, scraper, run: ScrapeRun, org_code: str):
    try:
        scraper.scrape_escalas(year=run.year)
        logger.info("Escalas downloaded")
    except Exception as e:
        logger.error(f"Error scraping escalas: {e}", exc_info=True)


def _parse_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = str(val).replace(".", "").replace(",", ".").replace("$", "").strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None
