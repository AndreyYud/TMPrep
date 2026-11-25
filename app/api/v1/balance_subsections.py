from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models import BalanceSubsection, BalanceSection, BalanceRule
from app.schemas.balance_subsection import BalanceSubsectionCreate, BalanceSubsectionUpdate, BalanceSubsectionResponse

router = APIRouter(prefix="/balance-subsections", tags=["balance subsections"])


@router.get("/", response_model=list[BalanceSubsectionResponse])
async def list_subsections(
        section_id: Optional[int] = Query(None),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(BalanceSubsection).options(
        selectinload(BalanceSubsection.section)
    ).order_by(BalanceSubsection.order, BalanceSubsection.name)
    if section_id is not None:
        stmt = stmt.where(BalanceSubsection.section_id == section_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=BalanceSubsectionResponse)
async def create_subsection(data: BalanceSubsectionCreate, db: AsyncSession = Depends(get_db)):
    section = await db.get(BalanceSection, data.section_id)
    if not section:
        raise HTTPException(status_code=400, detail="Раздел не найден")

    new_sub = BalanceSubsection(**data.model_dump())
    db.add(new_sub)
    await db.commit()

    # Перезагружаем с подгрузкой section
    stmt = select(BalanceSubsection).options(
        selectinload(BalanceSubsection.section)
    ).where(BalanceSubsection.id == new_sub.id)
    result = await db.execute(stmt)
    return result.scalars().first()


@router.get("/{subsection_id}", response_model=BalanceSubsectionResponse)
async def get_subsection(subsection_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(BalanceSubsection).options(
        selectinload(BalanceSubsection.section)
    ).where(BalanceSubsection.id == subsection_id)
    result = await db.execute(stmt)
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Подраздел не найден")
    return sub


@router.put("/{subsection_id}", response_model=BalanceSubsectionResponse)
async def update_subsection(
        subsection_id: int,
        data: BalanceSubsectionUpdate,
        db: AsyncSession = Depends(get_db)
):
    stmt = select(BalanceSubsection).options(
        selectinload(BalanceSubsection.section)
    ).where(BalanceSubsection.id == subsection_id)
    result = await db.execute(stmt)
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Подраздел не найден")

    update_data = data.model_dump(exclude_unset=True)
    if "section_id" in update_data:
        section = await db.get(BalanceSection, update_data["section_id"])
        if not section:
            raise HTTPException(status_code=400, detail="Раздел не найден")

    for key, value in update_data.items():
        setattr(sub, key, value)

    await db.commit()

    # Перезагружаем с подгрузкой section
    stmt = select(BalanceSubsection).options(
        selectinload(BalanceSubsection.section)
    ).where(BalanceSubsection.id == subsection_id)
    result = await db.execute(stmt)
    return result.scalars().first()


@router.delete("/{subsection_id}")
async def delete_subsection(subsection_id: int, db: AsyncSession = Depends(get_db)):
    # Загружаем подраздел (с подгрузкой section – для единообразия)
    stmt = select(BalanceSubsection).options(
        selectinload(BalanceSubsection.section)
    ).where(BalanceSubsection.id == subsection_id)
    result = await db.execute(stmt)
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="Подраздел не найден")

    # Проверяем, используется ли подраздел в правилах
    stmt_rules = select(BalanceRule).where(BalanceRule.subsection_id == subsection_id)
    rules_result = await db.execute(stmt_rules)
    if rules_result.scalars().first():
        raise HTTPException(status_code=400, detail="Подраздел используется в правилах, удаление запрещено")

    await db.delete(sub)
    await db.commit()
    return {"detail": "Подраздел удалён"}