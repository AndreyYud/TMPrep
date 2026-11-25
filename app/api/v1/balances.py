from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.core.database import get_db
from app.services.report_builder import get_periods_list
from app.schemas.report import PeriodListItem
from app.models import Organization, UploadSession, Balance, InternalBalance

router = APIRouter(prefix="/periods", tags=["periods"])

@router.get("/", response_model=list[PeriodListItem])
async def list_periods(db: AsyncSession = Depends(get_db)):
    periods = await get_periods_list(db)
    return [PeriodListItem(**p) for p in periods]

@router.delete("/{org_inn}/{period_date}")
async def delete_period(org_inn: str, period_date: str, db: AsyncSession = Depends(get_db)):
    try:
        pdate = datetime.strptime(period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    stmt = select(Organization).where(Organization.inn == org_inn)
    org = (await db.execute(stmt)).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    stmt = select(UploadSession).where(
        UploadSession.organization_id == org.id,
        UploadSession.period_date == pdate
    )
    session_record = (await db.execute(stmt)).scalars().first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Период не найден")

    await db.execute(
        Balance.__table__.delete().where(
            Balance.organization_id == org.id,
            Balance.period_date == pdate
        )
    )
    await db.execute(
        InternalBalance.__table__.delete().where(
            InternalBalance.organization_id == org.id,
            InternalBalance.period_date == pdate
        )
    )
    await db.delete(session_record)
    await db.commit()

    return {"detail": "Период удален"}