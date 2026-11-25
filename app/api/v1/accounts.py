from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models import Account, Balance, InternalBalance
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.get("/", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    stmt = select(Account).order_by(Account.code)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=AccountResponse)
async def create_account(
    acc_data: AccountCreate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Account).where(Account.code == acc_data.code)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Счёт с таким кодом уже существует")
    new_acc = Account(**acc_data.model_dump())
    db.add(new_acc)
    await db.commit()
    await db.refresh(new_acc)
    return new_acc

@router.get("/{acc_id}", response_model=AccountResponse)
async def get_account(acc_id: int, db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, acc_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    return acc

@router.put("/{acc_id}", response_model=AccountResponse)
async def update_account(
    acc_id: int,
    acc_data: AccountUpdate,
    db: AsyncSession = Depends(get_db)
):
    acc = await db.get(Account, acc_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    update_data = acc_data.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] != acc.code:
        stmt = select(Account).where(Account.code == update_data["code"])
        result = await db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Счёт с таким кодом уже существует")
    for key, value in update_data.items():
        setattr(acc, key, value)
    await db.commit()
    await db.refresh(acc)
    return acc

@router.delete("/{acc_id}")
async def delete_account(acc_id: int, db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, acc_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    bal_stmt = select(func.count()).select_from(Balance).where(Balance.account_id == acc_id)
    bal_count = (await db.execute(bal_stmt)).scalar()
    if bal_count > 0:
        raise HTTPException(status_code=400, detail="Счёт используется в балансах, удаление запрещено")
    int_stmt = select(func.count()).select_from(InternalBalance).where(InternalBalance.account_id == acc_id)
    int_count = (await db.execute(int_stmt)).scalar()
    if int_count > 0:
        raise HTTPException(status_code=400, detail="Счёт используется во внутренних балансах, удаление запрещено")
    await db.delete(acc)
    await db.commit()
    return {"detail": "Счёт удалён"}