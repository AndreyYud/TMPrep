from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.core.database import get_db
from app.services.report_builder import get_report_detail
from app.schemas.report import ReportDetail

router = APIRouter(prefix="/report", tags=["report"])

@router.get("/{org_inn}/{period_date}", response_model=ReportDetail)
async def report_detail(org_inn: str, period_date: str, db: AsyncSession = Depends(get_db)):
    try:
        pdate = datetime.strptime(period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    data = await get_report_detail(db, org_inn, pdate)
    if not data:
        raise HTTPException(status_code=404, detail="Данные не найдены")
    return data