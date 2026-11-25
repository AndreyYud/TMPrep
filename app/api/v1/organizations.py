from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models import Organization, Balance, InternalBalance
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])

@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(db: AsyncSession = Depends(get_db)):
    """
    Получить список всех организаций с подгрузкой типа.
    """
    stmt = select(Organization).options(selectinload(Organization.type)).order_by(Organization.inn)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=OrganizationResponse)
async def create_organization(org_data: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать новую организацию.
    """
    # Проверяем уникальность ИНН
    stmt = select(Organization).where(Organization.inn == org_data.inn)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Организация с таким ИНН уже существует")

    new_org = Organization(**org_data.model_dump())
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    # Подгружаем тип для ответа (если есть)
    if new_org.type_id:
        await db.refresh(new_org, attribute_names=['type'])
    return new_org

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить организацию по ID.
    """
    stmt = select(Organization).options(selectinload(Organization.type)).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    return org

@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(org_id: int, org_data: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    """
    Обновить данные организации.
    """
    stmt = select(Organization).options(selectinload(Organization.type)).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    update_data = org_data.model_dump(exclude_unset=True)

    # Если меняется ИНН, проверяем уникальность
    if "inn" in update_data and update_data["inn"] != org.inn:
        stmt_check = select(Organization).where(Organization.inn == update_data["inn"])
        check_result = await db.execute(stmt_check)
        if check_result.scalars().first():
            raise HTTPException(status_code=400, detail="Организация с таким ИНН уже существует")

    for key, value in update_data.items():
        setattr(org, key, value)

    await db.commit()
    await db.refresh(org)
    if org.type_id:
        await db.refresh(org, attribute_names=['type'])
    return org

@router.delete("/{org_id}")
async def delete_organization(org_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удалить организацию, если она не используется в балансах.
    """
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    # Проверяем использование в балансах
    bal_stmt = select(func.count()).select_from(Balance).where(Balance.organization_id == org_id)
    bal_count = (await db.execute(bal_stmt)).scalar()
    if bal_count > 0:
        raise HTTPException(status_code=400, detail="Организация используется в балансах, удаление запрещено")

    int_stmt = select(func.count()).select_from(InternalBalance).where(
        (InternalBalance.organization_id == org_id) | (InternalBalance.counterparty_organization_id == org_id)
    )
    int_count = (await db.execute(int_stmt)).scalar()
    if int_count > 0:
        raise HTTPException(status_code=400, detail="Организация используется во внутренних балансах, удаление запрещено")

    await db.delete(org)
    await db.commit()
    return {"detail": "Организация удалена"}