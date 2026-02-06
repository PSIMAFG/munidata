from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from app.database import get_db
from app.models.personnel import HonorariosRecord, ContrataRecord, PlantaRecord

router = APIRouter()


@router.get("/options")
async def filter_options(
    municipality_code: str = Query(...),
    area: str = Query("Salud"),
    year: int = Query(2025),
    db: AsyncSession = Depends(get_db),
):
    """Return dynamic filter options based on available data."""
    # Available months (from honorarios)
    hon_months_q = (
        select(distinct(HonorariosRecord.month))
        .where(
            HonorariosRecord.municipality_code == municipality_code,
            HonorariosRecord.area == area,
            HonorariosRecord.year == year,
        )
        .order_by(HonorariosRecord.month)
    )
    cont_months_q = (
        select(distinct(ContrataRecord.month))
        .where(
            ContrataRecord.municipality_code == municipality_code,
            ContrataRecord.area == area,
            ContrataRecord.year == year,
        )
        .order_by(ContrataRecord.month)
    )
    pla_months_q = (
        select(distinct(PlantaRecord.month))
        .where(
            PlantaRecord.municipality_code == municipality_code,
            PlantaRecord.area == area,
            PlantaRecord.year == year,
        )
        .order_by(PlantaRecord.month)
    )

    hon_months = {r[0] for r in (await db.execute(hon_months_q)).all() if r[0]}
    cont_months = {r[0] for r in (await db.execute(cont_months_q)).all() if r[0]}
    pla_months = {r[0] for r in (await db.execute(pla_months_q)).all() if r[0]}
    all_months = sorted(hon_months | cont_months | pla_months)

    # Available convenios
    conv_q = (
        select(distinct(HonorariosRecord.convenio))
        .where(
            HonorariosRecord.municipality_code == municipality_code,
            HonorariosRecord.area == area,
            HonorariosRecord.year == year,
            HonorariosRecord.convenio.isnot(None),
        )
        .order_by(HonorariosRecord.convenio)
    )
    convenios = [r[0] for r in (await db.execute(conv_q)).all() if r[0]]

    # Contract types with data
    contract_types = []
    for ct, cnt in [
        ("HONORARIOS", (await db.execute(
            select(func.count(HonorariosRecord.id)).where(
                HonorariosRecord.municipality_code == municipality_code,
                HonorariosRecord.year == year,
            )
        )).scalar()),
        ("CONTRATA", (await db.execute(
            select(func.count(ContrataRecord.id)).where(
                ContrataRecord.municipality_code == municipality_code,
                ContrataRecord.year == year,
            )
        )).scalar()),
        ("PLANTA", (await db.execute(
            select(func.count(PlantaRecord.id)).where(
                PlantaRecord.municipality_code == municipality_code,
                PlantaRecord.year == year,
            )
        )).scalar()),
    ]:
        if cnt and cnt > 0:
            contract_types.append(ct)

    # Available years
    years_q = select(distinct(HonorariosRecord.year)).where(
        HonorariosRecord.municipality_code == municipality_code
    ).order_by(HonorariosRecord.year.desc())
    years = [r[0] for r in (await db.execute(years_q)).all()]
    if not years:
        years = [2025]

    return {
        "months": all_months,
        "convenios": convenios,
        "contract_types": contract_types if contract_types else ["HONORARIOS", "CONTRATA", "PLANTA"],
        "years": years,
    }
