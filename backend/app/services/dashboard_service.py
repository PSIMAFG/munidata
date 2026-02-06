"""Server-side aggregation service for dashboard endpoints."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, or_, cast, Float
from app.models.personnel import HonorariosRecord, ContrataRecord, PlantaRecord
from app.schemas.filters import DashboardFilters
from typing import Any


def _build_honorarios_where(f: DashboardFilters):
    clauses = [
        HonorariosRecord.municipality_code == f.municipality_code,
        HonorariosRecord.area == f.area,
        HonorariosRecord.year == f.year,
    ]
    if f.months:
        clauses.append(HonorariosRecord.month.in_(f.months))
    if f.convenios:
        clauses.append(HonorariosRecord.convenio.in_(f.convenios))
    if f.search_text:
        pattern = f"%{f.search_text}%"
        clauses.append(
            or_(
                HonorariosRecord.nombre.ilike(pattern),
                HonorariosRecord.descripcion_funcion.ilike(pattern),
                HonorariosRecord.calificacion_profesional.ilike(pattern),
            )
        )
    return and_(*clauses)


def _build_contrata_where(f: DashboardFilters):
    clauses = [
        ContrataRecord.municipality_code == f.municipality_code,
        ContrataRecord.area == f.area,
        ContrataRecord.year == f.year,
    ]
    if f.months:
        clauses.append(ContrataRecord.month.in_(f.months))
    if f.search_text:
        pattern = f"%{f.search_text}%"
        clauses.append(
            or_(
                ContrataRecord.nombre.ilike(pattern),
                ContrataRecord.cargo.ilike(pattern),
                ContrataRecord.calificacion_profesional.ilike(pattern),
            )
        )
    return and_(*clauses)


def _build_planta_where(f: DashboardFilters):
    clauses = [
        PlantaRecord.municipality_code == f.municipality_code,
        PlantaRecord.area == f.area,
        PlantaRecord.year == f.year,
    ]
    if f.months:
        clauses.append(PlantaRecord.month.in_(f.months))
    if f.search_text:
        pattern = f"%{f.search_text}%"
        clauses.append(
            or_(
                PlantaRecord.nombre.ilike(pattern),
                PlantaRecord.cargo.ilike(pattern),
                PlantaRecord.calificacion_profesional.ilike(pattern),
            )
        )
    return and_(*clauses)


async def get_kpis(db: AsyncSession, f: DashboardFilters) -> dict[str, Any]:
    result: dict[str, Any] = {
        "total_gasto": 0,
        "gasto_honorarios": 0,
        "gasto_contrata": 0,
        "gasto_planta": 0,
        "count_honorarios": 0,
        "count_contrata": 0,
        "count_planta": 0,
        "unique_profesionales": 0,
        "unique_convenios": 0,
    }

    if "HONORARIOS" in f.contract_types:
        q = select(
            func.coalesce(func.sum(HonorariosRecord.remuneracion_bruta), 0),
            func.count(HonorariosRecord.id),
            func.count(func.distinct(HonorariosRecord.nombre)),
            func.count(func.distinct(HonorariosRecord.convenio)),
        ).where(_build_honorarios_where(f))
        row = (await db.execute(q)).one()
        result["gasto_honorarios"] = float(row[0])
        result["count_honorarios"] = row[1]
        result["unique_profesionales"] = row[2]
        result["unique_convenios"] = row[3]

    if "CONTRATA" in f.contract_types:
        q = select(
            func.coalesce(func.sum(ContrataRecord.remuneracion_bruta), 0),
            func.count(ContrataRecord.id),
        ).where(_build_contrata_where(f))
        row = (await db.execute(q)).one()
        result["gasto_contrata"] = float(row[0])
        result["count_contrata"] = row[1]

    if "PLANTA" in f.contract_types:
        q = select(
            func.coalesce(func.sum(PlantaRecord.remuneracion_bruta), 0),
            func.count(PlantaRecord.id),
        ).where(_build_planta_where(f))
        row = (await db.execute(q)).one()
        result["gasto_planta"] = float(row[0])
        result["count_planta"] = row[1]

    result["total_gasto"] = (
        result["gasto_honorarios"] + result["gasto_contrata"] + result["gasto_planta"]
    )
    return result


async def get_timeseries(
    db: AsyncSession, f: DashboardFilters, group_by: str = "month"
) -> list[dict]:
    """Return monthly timeseries, optionally grouped by convenio or contract_type."""
    rows = []

    if "HONORARIOS" in f.contract_types:
        group_col = (
            HonorariosRecord.convenio if group_by == "convenio"
            else func.literal("HONORARIOS")
        )
        q = (
            select(
                HonorariosRecord.month,
                group_col.label("group_key"),
                func.coalesce(func.sum(HonorariosRecord.remuneracion_bruta), 0).label("total"),
                func.count(HonorariosRecord.id).label("count"),
            )
            .where(_build_honorarios_where(f))
            .group_by(HonorariosRecord.month, group_col)
            .order_by(HonorariosRecord.month)
        )
        for r in (await db.execute(q)).all():
            rows.append({
                "month": r.month,
                "group_key": r.group_key or "Sin convenio",
                "total": float(r.total),
                "count": r.count,
                "contract_type": "HONORARIOS",
            })

    if "CONTRATA" in f.contract_types:
        q = (
            select(
                ContrataRecord.month,
                func.literal("CONTRATA").label("group_key"),
                func.coalesce(func.sum(ContrataRecord.remuneracion_bruta), 0).label("total"),
                func.count(ContrataRecord.id).label("count"),
            )
            .where(_build_contrata_where(f))
            .group_by(ContrataRecord.month)
            .order_by(ContrataRecord.month)
        )
        for r in (await db.execute(q)).all():
            rows.append({
                "month": r.month,
                "group_key": "CONTRATA",
                "total": float(r.total),
                "count": r.count,
                "contract_type": "CONTRATA",
            })

    if "PLANTA" in f.contract_types:
        q = (
            select(
                PlantaRecord.month,
                func.literal("PLANTA").label("group_key"),
                func.coalesce(func.sum(PlantaRecord.remuneracion_bruta), 0).label("total"),
                func.count(PlantaRecord.id).label("count"),
            )
            .where(_build_planta_where(f))
            .group_by(PlantaRecord.month)
            .order_by(PlantaRecord.month)
        )
        for r in (await db.execute(q)).all():
            rows.append({
                "month": r.month,
                "group_key": "PLANTA",
                "total": float(r.total),
                "count": r.count,
                "contract_type": "PLANTA",
            })

    return rows


async def get_breakdown(
    db: AsyncSession, f: DashboardFilters, group_by: str = "convenio", top_n: int = 10
) -> list[dict]:
    """Return breakdown aggregation grouped by convenio, contract_type, or profesional."""
    rows = []

    if group_by == "convenio" and "HONORARIOS" in f.contract_types:
        q = (
            select(
                HonorariosRecord.convenio.label("group_key"),
                func.coalesce(func.sum(HonorariosRecord.remuneracion_bruta), 0).label("total"),
                func.count(HonorariosRecord.id).label("count"),
                func.count(func.distinct(HonorariosRecord.nombre)).label("unique_people"),
            )
            .where(_build_honorarios_where(f))
            .group_by(HonorariosRecord.convenio)
            .order_by(func.sum(HonorariosRecord.remuneracion_bruta).desc())
            .limit(top_n)
        )
        for r in (await db.execute(q)).all():
            rows.append({
                "group_key": r.group_key or "Sin convenio",
                "total": float(r.total),
                "count": r.count,
                "unique_people": r.unique_people,
            })

    elif group_by == "vinculo":
        if "HONORARIOS" in f.contract_types:
            q = select(
                func.coalesce(func.sum(HonorariosRecord.remuneracion_bruta), 0),
                func.count(HonorariosRecord.id),
            ).where(_build_honorarios_where(f))
            r = (await db.execute(q)).one()
            rows.append({"group_key": "HONORARIOS", "total": float(r[0]), "count": r[1]})

        if "CONTRATA" in f.contract_types:
            q = select(
                func.coalesce(func.sum(ContrataRecord.remuneracion_bruta), 0),
                func.count(ContrataRecord.id),
            ).where(_build_contrata_where(f))
            r = (await db.execute(q)).one()
            rows.append({"group_key": "CONTRATA", "total": float(r[0]), "count": r[1]})

        if "PLANTA" in f.contract_types:
            q = select(
                func.coalesce(func.sum(PlantaRecord.remuneracion_bruta), 0),
                func.count(PlantaRecord.id),
            ).where(_build_planta_where(f))
            r = (await db.execute(q)).one()
            rows.append({"group_key": "PLANTA", "total": float(r[0]), "count": r[1]})

    elif group_by == "profesional" and "HONORARIOS" in f.contract_types:
        q = (
            select(
                HonorariosRecord.nombre.label("group_key"),
                func.coalesce(func.sum(HonorariosRecord.remuneracion_bruta), 0).label("total"),
                func.count(HonorariosRecord.id).label("count"),
            )
            .where(_build_honorarios_where(f))
            .group_by(HonorariosRecord.nombre)
            .order_by(func.sum(HonorariosRecord.remuneracion_bruta).desc())
            .limit(top_n)
        )
        for r in (await db.execute(q)).all():
            rows.append({
                "group_key": r.group_key or "Desconocido",
                "total": float(r.total),
                "count": r.count,
            })

    # Compute percentages
    grand_total = sum(r["total"] for r in rows)
    for r in rows:
        r["pct"] = round(r["total"] / grand_total * 100, 2) if grand_total > 0 else 0

    return rows
