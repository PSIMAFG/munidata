from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database import get_db
from app.models.personnel import (
    Project, HonorariosRecord, ContrataRecord, PlantaRecord,
    RemunerationScale, AuditException, ScrapeRun,
)
from app.schemas.filters import ProjectCreate, ProjectUpdate
import datetime

router = APIRouter()


def _project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "municipality_code": p.municipality_code,
        "area": p.area,
        "year": p.year,
        "months": p.months,
        "contract_types": p.contract_types,
        "convenios": p.convenios,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("")
async def create_project(req: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(
        name=req.name,
        description=req.description,
        municipality_code=req.municipality_code,
        area=req.area,
        year=req.year,
        months=req.months,
        contract_types=req.contract_types,
        convenios=req.convenios,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_to_dict(project)


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    q = select(Project).order_by(Project.updated_at.desc())
    rows = (await db.execute(q)).scalars().all()
    return [_project_to_dict(p) for p in rows]


@router.get("/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return _project_to_dict(project)


@router.put("/{project_id}")
async def update_project(
    project_id: int, req: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    project.updated_at = datetime.datetime.utcnow()

    await db.commit()
    await db.refresh(project)
    return _project_to_dict(project)


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    await db.delete(project)
    await db.commit()
    return {"detail": "Proyecto eliminado"}


@router.delete("/{project_id}/data")
async def delete_project_data(project_id: int, db: AsyncSession = Depends(get_db)):
    """Delete all data records associated with a project's municipality/area/year."""
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    muni = project.municipality_code
    area = project.area
    year = project.year

    deleted = {}

    # Delete honorarios records
    result = await db.execute(
        delete(HonorariosRecord).where(
            HonorariosRecord.municipality_code == muni,
            HonorariosRecord.area == area,
            HonorariosRecord.year == year,
        )
    )
    deleted["honorarios"] = result.rowcount

    # Delete contrata records
    result = await db.execute(
        delete(ContrataRecord).where(
            ContrataRecord.municipality_code == muni,
            ContrataRecord.area == area,
            ContrataRecord.year == year,
        )
    )
    deleted["contrata"] = result.rowcount

    # Delete planta records
    result = await db.execute(
        delete(PlantaRecord).where(
            PlantaRecord.municipality_code == muni,
            PlantaRecord.area == area,
            PlantaRecord.year == year,
        )
    )
    deleted["planta"] = result.rowcount

    # Delete remuneration scales
    result = await db.execute(
        delete(RemunerationScale).where(
            RemunerationScale.municipality_code == muni,
            RemunerationScale.year == year,
        )
    )
    deleted["escalas"] = result.rowcount

    # Delete audit exceptions
    result = await db.execute(
        delete(AuditException).where(
            AuditException.municipality_code == muni,
            AuditException.year == year,
        )
    )
    deleted["audit_exceptions"] = result.rowcount

    # Delete scrape runs
    result = await db.execute(
        delete(ScrapeRun).where(
            ScrapeRun.municipality_code == muni,
            ScrapeRun.area == area,
            ScrapeRun.year == year,
        )
    )
    deleted["scrape_runs"] = result.rowcount

    await db.commit()

    total = sum(deleted.values())
    return {
        "detail": f"Se eliminaron {total} registros del proyecto '{project.name}'",
        "deleted": deleted,
    }
