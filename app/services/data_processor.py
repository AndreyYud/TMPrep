from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from decimal import Decimal
from typing import List, Dict
from app.models import Organization, Account, Balance, InternalBalance, UploadSession

async def process_upload(
    session: AsyncSession,
    period_date: date,
    organization_inn: str,
    full_balances: List[Dict],
    internal_balances: List[Dict]
) -> dict:
    # 1. Основная организация
    stmt = select(Organization).where(Organization.inn == organization_inn)
    result = await session.execute(stmt)
    org = result.scalars().first()
    if org is None:
        org = Organization(inn=organization_inn, name=None)
        session.add(org)
        await session.flush()

    # 2. Удаление старых записей
    await session.execute(
        Balance.__table__.delete().where(
            Balance.organization_id == org.id,
            Balance.period_date == period_date
        )
    )
    await session.execute(
        InternalBalance.__table__.delete().where(
            InternalBalance.organization_id == org.id,
            InternalBalance.period_date == period_date
        )
    )
    await session.execute(
        UploadSession.__table__.delete().where(
            UploadSession.organization_id == org.id,
            UploadSession.period_date == period_date
        )
    )

    # 3. Кеш счетов
    account_cache = {}
    async def get_account(code: str):
        if code not in account_cache:
            stmt = select(Account).where(Account.code == code)
            result = await session.execute(stmt)
            acc = result.scalars().first()
            if acc is None:
                acc = Account(code=code)
                session.add(acc)
                await session.flush()
                account_cache[code] = acc
            else:
                account_cache[code] = acc
        return account_cache[code]

    # 4. Кеш контрагентов
    counterparty_cache = {}
    async def get_counterparty(inn: str):
        if inn not in counterparty_cache:
            stmt = select(Organization).where(Organization.inn == inn)
            result = await session.execute(stmt)
            c = result.scalars().first()
            if c is None:
                c = Organization(inn=inn, name=None)
                session.add(c)
                await session.flush()
                counterparty_cache[inn] = c
            else:
                counterparty_cache[inn] = c
        return counterparty_cache[inn]

    # 5. Вставка Balance
    for item in full_balances:
        acc = await get_account(item["account_code"])
        balance = Balance(
            organization_id=org.id,
            account_id=acc.id,
            full_account_code=item.get("full_account_code", item["account_code"]),
            period_date=period_date,
            end_debit=item["end_debit"],
            end_credit=item["end_credit"]
        )
        session.add(balance)

    # 6. Вставка InternalBalance
    for item in internal_balances:
        acc = await get_account(item["account_code"])
        counterparty = await get_counterparty(item["counterparty_inn"])
        internal = InternalBalance(
            organization_id=org.id,
            counterparty_organization_id=counterparty.id,
            account_id=acc.id,
            period_date=period_date,
            full_account_code=item.get("full_account_code", item["account_code"]),  # добавляем
            end_debit=item["end_debit"],
            end_credit=item["end_credit"]
        )
        session.add(internal)

    # 7. Создание записи сессии загрузки
    upload_session = UploadSession(
        organization_id=org.id,
        period_date=period_date
    )
    session.add(upload_session)

    await session.commit()

    return {
        "period_date": period_date,
        "balances_count": len(full_balances),
        "internal_count": len(internal_balances),
        "organization_inn": org.inn
    }