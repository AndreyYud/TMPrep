from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models import BalanceRule, Account, BalanceSection, BalanceSubsection
from app.schemas.balance_rule import BalanceRuleCreate, BalanceRuleUpdate, BalanceRuleResponse

router = APIRouter(prefix="/balance-rules", tags=["balance rules"])

@router.get("/", response_model=list[BalanceRuleResponse])
async def list_rules(db: AsyncSession = Depends(get_db)):
    stmt = select(BalanceRule).options(
        selectinload(BalanceRule.accounts),
        selectinload(BalanceRule.section),
        selectinload(BalanceRule.subsection).selectinload(BalanceSubsection.section)
    ).order_by(BalanceRule.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=BalanceRuleResponse)
async def create_rule(data: BalanceRuleCreate, db: AsyncSession = Depends(get_db)):
    # Проверяем существование раздела и подраздела
    section = await db.get(BalanceSection, data.section_id)
    if not section:
        raise HTTPException(status_code=400, detail="Раздел не найден")
    subsection = await db.get(BalanceSubsection, data.subsection_id)
    if not subsection or subsection.section_id != data.section_id:
        raise HTTPException(status_code=400, detail="Подраздел не соответствует разделу")

    # Получаем или создаем счета
    accounts = []
    for code in data.account_codes:
        stmt = select(Account).where(Account.code == code)
        result = await db.execute(stmt)
        acc = result.scalars().first()
        if acc is None:
            acc = Account(code=code)
            db.add(acc)
            await db.flush()
        accounts.append(acc)

    # Проверяем уникальность счетов в пределах типа (актив/пассив)
    await _check_accounts_uniqueness(db, accounts, data.is_active, exclude_rule_id=None)

    new_rule = BalanceRule(
        section_id=data.section_id,
        subsection_id=data.subsection_id,
        item=data.item,
        is_active=data.is_active,
        accounts=accounts
    )
    db.add(new_rule)
    await db.commit()

    # Загружаем правило со всеми связями для ответа
    stmt = select(BalanceRule).options(
        selectinload(BalanceRule.accounts),
        selectinload(BalanceRule.section),
        selectinload(BalanceRule.subsection).selectinload(BalanceSubsection.section)
    ).where(BalanceRule.id == new_rule.id)
    result = await db.execute(stmt)
    return result.scalars().first()

@router.get("/{rule_id}", response_model=BalanceRuleResponse)
async def get_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(BalanceRule).options(
        selectinload(BalanceRule.accounts),
        selectinload(BalanceRule.section),
        selectinload(BalanceRule.subsection).selectinload(BalanceSubsection.section)
    ).where(BalanceRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return rule

@router.put("/{rule_id}", response_model=BalanceRuleResponse)
async def update_rule(rule_id: int, data: BalanceRuleUpdate, db: AsyncSession = Depends(get_db)):
    # Загружаем правило со всеми связями
    stmt = select(BalanceRule).options(
        selectinload(BalanceRule.accounts),
        selectinload(BalanceRule.section),
        selectinload(BalanceRule.subsection).selectinload(BalanceSubsection.section)
    ).where(BalanceRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    update_data = data.model_dump(exclude_unset=True)

    # Обработка изменения счетов
    if "account_codes" in update_data:
        new_accounts = []
        for code in update_data["account_codes"]:
            stmt_acc = select(Account).where(Account.code == code)
            res_acc = await db.execute(stmt_acc)
            acc = res_acc.scalars().first()
            if acc is None:
                acc = Account(code=code)
                db.add(acc)
                await db.flush()
            new_accounts.append(acc)

        is_active = update_data.get("is_active", rule.is_active)
        await _check_accounts_uniqueness(db, new_accounts, is_active, exclude_rule_id=rule_id)
        rule.accounts = new_accounts
        del update_data["account_codes"]

    # Если меняется is_active – проверяем уже имеющиеся счета
    if "is_active" in update_data and update_data["is_active"] != rule.is_active:
        await _check_accounts_uniqueness(db, rule.accounts, update_data["is_active"], exclude_rule_id=rule_id)

    # Обновляем поля
    for key, value in update_data.items():
        if key in ("section_id", "subsection_id", "item", "is_active"):
            setattr(rule, key, value)

    # Если изменился subsection_id, проверяем соответствие разделу
    if "subsection_id" in update_data:
        subsection = await db.get(BalanceSubsection, update_data["subsection_id"])
        if not subsection or subsection.section_id != rule.section_id:
            raise HTTPException(status_code=400, detail="Подраздел не соответствует разделу")

    await db.commit()

    # Повторно загружаем правило со всеми связями
    stmt = select(BalanceRule).options(
        selectinload(BalanceRule.accounts),
        selectinload(BalanceRule.section),
        selectinload(BalanceRule.subsection).selectinload(BalanceSubsection.section)
    ).where(BalanceRule.id == rule_id)
    result = await db.execute(stmt)
    return result.scalars().first()

@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(BalanceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    await db.delete(rule)
    await db.commit()
    return {"detail": "Правило удалено"}

async def _check_accounts_uniqueness(db: AsyncSession, accounts: list, is_active: bool, exclude_rule_id: int = None):
    """
    Проверяет, что каждый счёт не используется в другом правиле с таким же is_active.
    Исключает правило с id exclude_rule_id (при обновлении).
    """
    for account in accounts:
        stmt = (
            select(BalanceRule)
            .join(BalanceRule.accounts)
            .where(
                Account.id == account.id,
                BalanceRule.is_active == is_active
            )
        )
        if exclude_rule_id is not None:
            stmt = stmt.where(BalanceRule.id != exclude_rule_id)
        result = await db.execute(stmt)
        existing_rules = result.scalars().all()
        if existing_rules:
            rule_names = [f"#{r.id} ({r.section.name} / {r.item or 'без статьи'})" for r in existing_rules]
            raise HTTPException(
                status_code=400,
                detail=f"Счет {account.code} уже используется в правиле(ах): {', '.join(rule_names)} с тем же типом (Актив/Пассив)"
            )