from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.personnel import ScrapeRun, ScrapeRunStatus
from app.schemas.filters import ScrapeRunRequest
import datetime

router = APIRouter()


@router.post("/scrape-runs")
async def create_scrape_run(
    req: ScrapeRunRequest,
    db: AsyncSession = Depends(get_db),
):
    run = ScrapeRun(
        municipality_code=req.municipality_code,
        area=req.area,
        year=req.year,
        months=req.months,
        contract_types=req.kinds,
        status=ScrapeRunStatus.PENDING,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Launch celery task
    try:
        from app.jobs.celery_app import run_scrape_task
        task = run_scrape_task.delay(run.id)
        run.celery_task_id = task.id
        run.status = ScrapeRunStatus.RUNNING
        run.started_at = datetime.datetime.utcnow()
        await db.commit()
    except Exception as e:
        run.status = ScrapeRunStatus.FAILED
        run.error_message = f"Failed to launch task: {str(e)}"
        await db.commit()

    return {
        "id": run.id,
        "status": run.status.value,
        "celery_task_id": run.celery_task_id,
    }


@router.get("/scrape-runs")
async def list_scrape_runs(
    municipality_code: str = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ScrapeRun).order_by(ScrapeRun.created_at.desc()).limit(50)
    if municipality_code:
        q = q.where(ScrapeRun.municipality_code == municipality_code)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "municipality_code": r.municipality_code,
            "area": r.area,
            "year": r.year,
            "months": r.months,
            "contract_types": r.contract_types,
            "status": r.status.value,
            "records_loaded": r.records_loaded,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/scrape-runs/{run_id}")
async def get_scrape_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))).scalar_one_or_none()
    if not run:
        return {"error": "Not found"}
    return {
        "id": run.id,
        "municipality_code": run.municipality_code,
        "status": run.status.value,
        "records_loaded": run.records_loaded,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
