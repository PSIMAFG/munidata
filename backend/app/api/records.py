from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from app.database import get_db
from app.models.personnel import HonorariosRecord, ContrataRecord, PlantaRecord
from typing import Optional

router = APIRouter()


def _base_params(
    municipality_code: str = Query(...),
    area: str = Query("Salud"),
    year: int = Query(2025),
    months: Optional[str] = Query(None),
    convenios: Optional[str] = Query(None),
    search_text: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: Optional[str] = Query(None),
    sort_desc: bool = Query(False),
):
    return {
        "municipality_code": municipality_code,
        "area": area,
        "year": year,
        "months": [int(m) for m in months.split(",")] if months else None,
        "convenios": convenios.split(",") if convenios else None,
        "search_text": search_text,
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "sort_desc": sort_desc,
    }


def _apply_sort(q, model, sort_by, sort_desc):
    if sort_by and hasattr(model, sort_by):
        col = getattr(model, sort_by)
        q = q.order_by(col.desc() if sort_desc else col.asc())
    else:
        q = q.order_by(model.id.desc())
    return q


@router.get("/honorarios")
async def list_honorarios(
    params: dict = Depends(_base_params),
    db: AsyncSession = Depends(get_db),
):
    M = HonorariosRecord
    clauses = [
        M.municipality_code == params["municipality_code"],
        M.area == params["area"],
        M.year == params["year"],
    ]
    if params["months"]:
        clauses.append(M.month.in_(params["months"]))
    if params["convenios"]:
        clauses.append(M.convenio.in_(params["convenios"]))
    if params["search_text"]:
        p = f"%{params['search_text']}%"
        clauses.append(or_(M.nombre.ilike(p), M.descripcion_funcion.ilike(p), M.calificacion_profesional.ilike(p)))

    where = and_(*clauses)
    count_q = select(func.count(M.id)).where(where)
    total = (await db.execute(count_q)).scalar()

    q = select(M).where(where)
    q = _apply_sort(q, M, params["sort_by"], params["sort_desc"])
    q = q.offset((params["page"] - 1) * params["page_size"]).limit(params["page_size"])
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "page": params["page"],
        "page_size": params["page_size"],
        "data": [
            {
                "id": r.id, "month": r.month, "nombre": r.nombre, "rut": r.rut,
                "descripcion_funcion": r.descripcion_funcion,
                "calificacion_profesional": r.calificacion_profesional,
                "fecha_inicio": r.fecha_inicio, "fecha_termino": r.fecha_termino,
                "remuneracion_bruta": r.remuneracion_bruta,
                "remuneracion_liquida": r.remuneracion_liquida,
                "monto_total": r.monto_total,
                "observaciones": r.observaciones, "convenio": r.convenio,
            }
            for r in rows
        ],
    }


@router.get("/contrata")
async def list_contrata(
    params: dict = Depends(_base_params),
    db: AsyncSession = Depends(get_db),
):
    M = ContrataRecord
    clauses = [
        M.municipality_code == params["municipality_code"],
        M.area == params["area"],
        M.year == params["year"],
    ]
    if params["months"]:
        clauses.append(M.month.in_(params["months"]))
    if params["search_text"]:
        p = f"%{params['search_text']}%"
        clauses.append(or_(M.nombre.ilike(p), M.cargo.ilike(p), M.calificacion_profesional.ilike(p)))

    where = and_(*clauses)
    count_q = select(func.count(M.id)).where(where)
    total = (await db.execute(count_q)).scalar()

    q = select(M).where(where)
    q = _apply_sort(q, M, params["sort_by"], params["sort_desc"])
    q = q.offset((params["page"] - 1) * params["page_size"]).limit(params["page_size"])
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "page": params["page"],
        "page_size": params["page_size"],
        "data": [
            {
                "id": r.id, "month": r.month, "nombre": r.nombre, "rut": r.rut,
                "grado_eus": r.grado_eus, "cargo": r.cargo,
                "calificacion_profesional": r.calificacion_profesional,
                "region": r.region, "asignaciones": r.asignaciones,
                "remuneracion_bruta": r.remuneracion_bruta,
                "remuneracion_liquida": r.remuneracion_liquida,
                "fecha_inicio": r.fecha_inicio, "fecha_termino": r.fecha_termino,
                "observaciones": r.observaciones, "horas": r.horas,
            }
            for r in rows
        ],
    }


@router.get("/planta")
async def list_planta(
    params: dict = Depends(_base_params),
    db: AsyncSession = Depends(get_db),
):
    M = PlantaRecord
    clauses = [
        M.municipality_code == params["municipality_code"],
        M.area == params["area"],
        M.year == params["year"],
    ]
    if params["months"]:
        clauses.append(M.month.in_(params["months"]))
    if params["search_text"]:
        p = f"%{params['search_text']}%"
        clauses.append(or_(M.nombre.ilike(p), M.cargo.ilike(p), M.calificacion_profesional.ilike(p)))

    where = and_(*clauses)
    count_q = select(func.count(M.id)).where(where)
    total = (await db.execute(count_q)).scalar()

    q = select(M).where(where)
    q = _apply_sort(q, M, params["sort_by"], params["sort_desc"])
    q = q.offset((params["page"] - 1) * params["page_size"]).limit(params["page_size"])
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "page": params["page"],
        "page_size": params["page_size"],
        "data": [
            {
                "id": r.id, "month": r.month, "nombre": r.nombre, "rut": r.rut,
                "grado_eus": r.grado_eus, "cargo": r.cargo,
                "calificacion_profesional": r.calificacion_profesional,
                "region": r.region, "asignaciones": r.asignaciones,
                "remuneracion_bruta": r.remuneracion_bruta,
                "remuneracion_liquida": r.remuneracion_liquida,
                "fecha_inicio": r.fecha_inicio, "fecha_termino": r.fecha_termino,
                "observaciones": r.observaciones, "horas": r.horas,
            }
            for r in rows
        ],
    }
