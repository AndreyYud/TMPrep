from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.core.database import get_db
from app.services.consolidated_balance_builder import build_consolidated_balance_for_orgs
from app.schemas.balance import ConsolidatedBalanceRequest, ConsolidatedBalanceMultiResponse
from app.services.excel_exporter import export_consolidated_balance_to_excel
from fastapi.responses import StreamingResponse
from urllib.parse import quote

router = APIRouter(prefix="/consolidated-balance", tags=["consolidated balance"])

@router.post("/", response_model=ConsolidatedBalanceMultiResponse)
async def get_consolidated_balance(
    request: ConsolidatedBalanceRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        pdate = datetime.strptime(request.period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if not request.org_inns:
        raise HTTPException(status_code=400, detail="Не выбрано ни одной организации")

    try:
        result = await build_consolidated_balance_for_orgs(db, request.org_inns, pdate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result

@router.post("/export")
async def export_consolidated_balance(
    request: ConsolidatedBalanceRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        pdate = datetime.strptime(request.period_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if not request.org_inns:
        raise HTTPException(status_code=400, detail="Не выбрано ни одной организации")

    try:
        result = await build_consolidated_balance_for_orgs(db, request.org_inns, pdate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        excel_file = export_consolidated_balance_to_excel(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации Excel: {str(e)}")

    filename = f"Консолидированный_баланс_{pdate.isoformat()}.xlsx"
    # Кодируем имя файла для заголовка Content-Disposition согласно RFC 5987
    encoded_filename = quote(filename, safe='')
    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition}
    )