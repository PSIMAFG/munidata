from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.database import get_db
from app.models.personnel import AuditException
from app.schemas.filters import AuditConfig
from typing import Optional

router = APIRouter()


@router.post("/run")
async def run_audit_endpoint(
    config: AuditConfig,
    db: AsyncSession = Depends(get_db),
):
    """Trigger audit computation (runs synchronously for now)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession
    from app.config import get_settings
    from app.services.audit_service import run_audit

    settings = get_settings()
    sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    with SyncSession(sync_engine) as sync_db:
        count = run_audit(sync_db, config.municipality_code, config.year, config.threshold_pct)
    return {"exceptions_found": count}


@router.get("/summary")
async def audit_summary(
    municipality_code: str = Query(...),
    year: int = Query(2025),
    threshold_pct: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    clauses = [
        AuditException.municipality_code == municipality_code,
        AuditException.year == year,
        AuditException.is_special == True,
    ]
    if threshold_pct is not None:
        clauses.append(func.abs(AuditException.diferencia_pct) >= threshold_pct)

    where = and_(*clauses)

    # Total exceptions
    total = (await db.execute(select(func.count(AuditException.id)).where(where))).scalar()

    # By month
    by_month_q = (
        select(
            AuditException.month,
            func.count(AuditException.id).label("count"),
            func.sum(func.abs(AuditException.diferencia)).label("total_diff"),
        )
        .where(where)
        .group_by(AuditException.month)
        .order_by(AuditException.month)
    )
    by_month = [
        {"month": r.month, "count": r.count, "total_diff": float(r.total_diff or 0)}
        for r in (await db.execute(by_month_q)).all()
    ]

    # By convenio
    by_convenio_q = (
        select(
            AuditException.convenio,
            func.count(AuditException.id).label("count"),
            func.sum(func.abs(AuditException.diferencia)).label("total_diff"),
        )
        .where(where)
        .group_by(AuditException.convenio)
        .order_by(func.sum(func.abs(AuditException.diferencia)).desc())
        .limit(15)
    )
    by_convenio = [
        {"convenio": r.convenio or "Sin convenio", "count": r.count, "total_diff": float(r.total_diff or 0)}
        for r in (await db.execute(by_convenio_q)).all()
    ]

    # By cargo
    by_cargo_q = (
        select(
            AuditException.cargo,
            func.count(AuditException.id).label("count"),
            func.sum(func.abs(AuditException.diferencia)).label("total_diff"),
        )
        .where(where)
        .group_by(AuditException.cargo)
        .order_by(func.sum(func.abs(AuditException.diferencia)).desc())
        .limit(15)
    )
    by_cargo = [
        {"cargo": r.cargo or "Sin cargo", "count": r.count, "total_diff": float(r.total_diff or 0)}
        for r in (await db.execute(by_cargo_q)).all()
    ]

    return {
        "total_exceptions": total,
        "by_month": by_month,
        "by_convenio": by_convenio,
        "by_cargo": by_cargo,
    }


@router.get("/exceptions")
async def audit_exceptions(
    municipality_code: str = Query(...),
    year: int = Query(2025),
    month: Optional[int] = Query(None),
    convenio: Optional[str] = Query(None),
    threshold_pct: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    clauses = [
        AuditException.municipality_code == municipality_code,
        AuditException.year == year,
        AuditException.is_special == True,
    ]
    if month:
        clauses.append(AuditException.month == month)
    if convenio:
        clauses.append(AuditException.convenio == convenio)
    if threshold_pct is not None:
        clauses.append(func.abs(AuditException.diferencia_pct) >= threshold_pct)

    where = and_(*clauses)

    total = (await db.execute(select(func.count(AuditException.id)).where(where))).scalar()

    q = (
        select(AuditException)
        .where(where)
        .order_by(func.abs(AuditException.diferencia_pct).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [
            {
                "id": r.id, "month": r.month, "contract_type": r.contract_type,
                "record_id": r.record_id, "nombre": r.nombre, "cargo": r.cargo,
                "convenio": r.convenio, "valor_real": r.valor_real,
                "valor_esperado": r.valor_esperado, "diferencia": r.diferencia,
                "diferencia_pct": r.diferencia_pct, "threshold_pct": r.threshold_pct,
                "match_method": r.match_method, "match_confidence": r.match_confidence,
                "fields_used": r.fields_used, "explanation": r.explanation,
            }
            for r in rows
        ],
    }
