from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.core.database import get_db
from app.services.balance_builder import build_consolidated_balance
from app.schemas.balance import ConsolidatedBalanceResponse

router = APIRouter(prefix="/balance", tags=["balance"])

@router.get("/{org_inn}/{period_date}", response_model=ConsolidatedBalanceResponse)
async def get_consolidated_balance(
    org_inn: str,
    period_date: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        pdate = datetime.strptime(period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    try:
        result = await build_consolidated_balance(db, org_inn, pdate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result