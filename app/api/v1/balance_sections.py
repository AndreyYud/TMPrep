from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models import BalanceSection, BalanceSubsection
from app.schemas.balance_section import BalanceSectionCreate, BalanceSectionUpdate, BalanceSectionResponse

router = APIRouter(prefix="/balance-sections", tags=["balance sections"])

@router.get("/", response_model=list[BalanceSectionResponse])
async def list_sections(db: AsyncSession = Depends(get_db)):
    stmt = select(BalanceSection).order_by(BalanceSection.order, BalanceSection.name)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=BalanceSectionResponse)
async def create_section(data: BalanceSectionCreate, db: AsyncSession = Depends(get_db)):
    new = BalanceSection(**data.model_dump())
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return new

@router.get("/{section_id}", response_model=BalanceSectionResponse)
async def get_section(section_id: int, db: AsyncSession = Depends(get_db)):
    section = await db.get(BalanceSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    return section

@router.put("/{section_id}", response_model=BalanceSectionResponse)
async def update_section(section_id: int, data: BalanceSectionUpdate, db: AsyncSession = Depends(get_db)):
    section = await db.get(BalanceSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(section, key, value)
    await db.commit()
    await db.refresh(section)
    return section

@router.delete("/{section_id}")
async def delete_section(section_id: int, db: AsyncSession = Depends(get_db)):
    section = await db.get(BalanceSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    stmt = select(BalanceSubsection).where(BalanceSubsection.section_id == section_id)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Раздел содержит подразделы, удаление запрещено")
    await db.delete(section)
    await db.commit()
    return {"detail": "Раздел удалён"}