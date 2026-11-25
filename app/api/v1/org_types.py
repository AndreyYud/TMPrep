from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models import OrganizationType
from app.schemas.org_type import OrgTypeCreate, OrgTypeUpdate, OrgTypeResponse

router = APIRouter(prefix="/org-types", tags=["organization types"])

@router.get("/", response_model=list[OrgTypeResponse])
async def list_types(db: AsyncSession = Depends(get_db)):
    stmt = select(OrganizationType).order_by(OrganizationType.name)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=OrgTypeResponse)
async def create_type(data: OrgTypeCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(OrganizationType).where(OrganizationType.name == data.name)
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Тип с таким названием уже существует")
    new_type = OrganizationType(name=data.name)
    db.add(new_type)
    await db.commit()
    await db.refresh(new_type)
    return new_type

@router.get("/{type_id}", response_model=OrgTypeResponse)
async def get_type(type_id: int, db: AsyncSession = Depends(get_db)):
    t = await db.get(OrganizationType, type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Тип не найден")
    return t

@router.put("/{type_id}", response_model=OrgTypeResponse)
async def update_type(type_id: int, data: OrgTypeUpdate, db: AsyncSession = Depends(get_db)):
    t = await db.get(OrganizationType, type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Тип не найден")
    if data.name is not None:
        stmt = select(OrganizationType).where(OrganizationType.name == data.name)
        existing = (await db.execute(stmt)).scalars().first()
        if existing and existing.id != type_id:
            raise HTTPException(status_code=400, detail="Тип с таким названием уже существует")
        t.name = data.name
    await db.commit()
    await db.refresh(t)
    return t

@router.delete("/{type_id}")
async def delete_type(type_id: int, db: AsyncSession = Depends(get_db)):
    t = await db.get(OrganizationType, type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Тип не найден")
    # Проверяем, используется ли тип в организациях
    from app.models import Organization
    stmt = select(Organization).where(Organization.type_id == type_id)
    orgs = (await db.execute(stmt)).scalars().all()
    if orgs:
        raise HTTPException(status_code=400, detail="Тип используется в организациях, удаление запрещено")
    await db.delete(t)
    await db.commit()
    return {"detail": "Тип удалён"}