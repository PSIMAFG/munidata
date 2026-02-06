from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.filters import DashboardFilters
from app.services.dashboard_service import get_kpis, get_timeseries, get_breakdown
from typing import Optional

router = APIRouter()


def _parse_filters(
    municipality_code: str = Query(...),
    area: str = Query("Salud"),
    year: int = Query(2025),
    months: Optional[str] = Query(None, description="Comma-separated months"),
    contract_types: Optional[str] = Query(None, description="Comma-separated types"),
    convenios: Optional[str] = Query(None, description="Comma-separated convenios"),
    search_text: Optional[str] = Query(None),
    audit_flag_special: Optional[bool] = Query(None),
) -> DashboardFilters:
    return DashboardFilters(
        municipality_code=municipality_code,
        area=area,
        year=year,
        months=[int(m) for m in months.split(",")] if months else list(range(1, 13)),
        contract_types=contract_types.split(",") if contract_types else ["HONORARIOS", "CONTRATA", "PLANTA"],
        convenios=convenios.split(",") if convenios else [],
        search_text=search_text,
        audit_flag_special=audit_flag_special,
    )


@router.get("/kpis")
async def dashboard_kpis(
    filters: DashboardFilters = Depends(_parse_filters),
    db: AsyncSession = Depends(get_db),
):
    return await get_kpis(db, filters)


@router.get("/timeseries")
async def dashboard_timeseries(
    filters: DashboardFilters = Depends(_parse_filters),
    group_by: str = Query("month", enum=["month", "convenio", "vinculo"]),
    db: AsyncSession = Depends(get_db),
):
    return await get_timeseries(db, filters, group_by)


@router.get("/breakdown")
async def dashboard_breakdown(
    filters: DashboardFilters = Depends(_parse_filters),
    group_by: str = Query("convenio", enum=["convenio", "vinculo", "profesional"]),
    top_n: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await get_breakdown(db, filters, group_by, top_n)
