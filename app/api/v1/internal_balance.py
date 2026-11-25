from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.core.database import get_db
from app.services.internal_balance_builder import build_internal_balance_for_orgs
from app.schemas.balance import InternalBalanceRequest, InternalBalanceMultiResponse
from fastapi.responses import StreamingResponse
from app.services.excel_exporter import export_internal_balance_to_excel
from urllib.parse import quote

router = APIRouter(prefix="/internal-balance", tags=["internal balance"])

@router.post("/", response_model=InternalBalanceMultiResponse)
async def get_internal_balance(
    request: InternalBalanceRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        pdate = datetime.strptime(request.period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    if not request.org_inns:
        raise HTTPException(status_code=400, detail="Не выбрано ни одной организации")
    try:
        result = await build_internal_balance_for_orgs(db, request.org_inns, pdate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result

@router.post("/export")
async def export_internal_balance(
    request: InternalBalanceRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        pdate = datetime.strptime(request.period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    if not request.org_inns:
        raise HTTPException(status_code=400, detail="Не выбрано ни одной организации")
    try:
        result = await build_internal_balance_for_orgs(db, request.org_inns, pdate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        excel_file = export_internal_balance_to_excel(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации Excel: {str(e)}")
    filename = f"Внутренние_взаиморасчеты_{pdate.isoformat()}.xlsx"
    encoded_filename = quote(filename, safe='')
    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition}
    )