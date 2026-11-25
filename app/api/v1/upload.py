from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.services.excel_parser import parse_full_osv, parse_internal_osv
from app.services.data_processor import process_upload
from app.schemas.upload import UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post("/", response_model=UploadResponse)
async def upload_osv(
    full_osv: UploadFile = File(...),
    internal_osv: UploadFile = File(...),
    organization_inn: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    allowed = (".xlsx", ".xls")
    if not full_osv.filename.lower().endswith(allowed) or not internal_osv.filename.lower().endswith(allowed):
        raise HTTPException(status_code=400, detail="Файлы должны быть в формате Excel (.xlsx, .xls)")

    full_bytes = await full_osv.read()
    internal_bytes = await internal_osv.read()

    try:
        full_data, full_org_inn, full_period_date = parse_full_osv(full_bytes)
        internal_data, internal_org_inn, internal_period_date = parse_internal_osv(internal_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга: {str(e)}")

    # Определяем организацию
    if full_org_inn is None and internal_org_inn is None:
        if organization_inn:
            org_inn = organization_inn
        else:
            raise HTTPException(status_code=400, detail="В файлах не указан ИНН организации, выберите организацию")
    elif full_org_inn is not None and internal_org_inn is not None:
        if full_org_inn != internal_org_inn:
            raise HTTPException(
                status_code=400,
                detail=f"ИНН организации в файлах не совпадают: полная ОСВ - {full_org_inn}, внутренняя - {internal_org_inn}"
            )
        org_inn = full_org_inn
        if organization_inn and organization_inn != org_inn:
            raise HTTPException(
                status_code=400,
                detail=f"Выбранная организация ({organization_inn}) не совпадает с ИНН в файлах ({org_inn})"
            )
    else:
        org_inn = full_org_inn or internal_org_inn
        if organization_inn and organization_inn != org_inn:
            raise HTTPException(
                status_code=400,
                detail=f"Выбранная организация ({organization_inn}) не совпадает с ИНН в файлах ({org_inn})"
            )

    # Определяем дату периода
    if full_period_date is None and internal_period_date is None:
        raise HTTPException(status_code=400, detail="Не удалось определить дату периода из файлов")
    elif full_period_date is not None and internal_period_date is not None:
        if full_period_date != internal_period_date:
            raise HTTPException(
                status_code=400,
                detail=f"Даты периода в файлах не совпадают: полная ОСВ - {full_period_date}, внутренняя - {internal_period_date}"
            )
        period_date = full_period_date
    else:
        period_date = full_period_date or internal_period_date

    if not full_data:
        raise HTTPException(status_code=400, detail="Не удалось извлечь данные из полной ОСВ")
    # internal_data может быть пустым – это допустимо

    try:
        result = await process_upload(db, period_date, org_inn, full_data, internal_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}")

    return UploadResponse(
        period_date=result["period_date"],
        balances_count=result["balances_count"],
        internal_count=result["internal_count"],
        organization_inn=result["organization_inn"]
    )