from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date
from app.models import Organization, Balance, InternalBalance, UploadSession, Account

async def get_periods_list(session: AsyncSession):
    stmt = (
        select(
            UploadSession.organization_id,
            UploadSession.period_date,
            func.max(UploadSession.created_at).label('created_at')
        )
        .group_by(UploadSession.organization_id, UploadSession.period_date)
        .order_by(UploadSession.period_date.desc())
    )
    result = await session.execute(stmt)
    rows = result.all()
    output = []
    for org_id, period_date, created_at in rows:
        org = await session.get(Organization, org_id)
        if not org:
            continue
        bal_count = await session.scalar(
            select(func.count()).select_from(Balance).where(
                Balance.organization_id == org_id,
                Balance.period_date == period_date
            )
        )
        int_count = await session.scalar(
            select(func.count()).select_from(InternalBalance).where(
                InternalBalance.organization_id == org_id,
                InternalBalance.period_date == period_date
            )
        )
        output.append({
            "organization_inn": org.inn,
            "organization_name": org.name,
            "period_date": period_date,
            "created_at": created_at,
            "balances_count": bal_count or 0,
            "internal_count": int_count or 0
        })
    return output

async def get_report_detail(session: AsyncSession, org_inn: str, period_date: date):
    stmt = select(Organization).where(Organization.inn == org_inn)
    org = (await session.execute(stmt)).scalars().first()
    if not org:
        return None

    # Полные остатки (Balance) – используем full_account_code, если есть
    balances_stmt = (
        select(
            Balance,
            Account.code,
            Balance.full_account_code
        )
        .join(Account, Balance.account_id == Account.id)
        .where(Balance.organization_id == org.id, Balance.period_date == period_date)
    )
    balances_res = await session.execute(balances_stmt)
    balances = []
    for b, code, full_code in balances_res:
        account_display = full_code or code
        balances.append({
            "account_code": account_display,
            "end_debit": b.end_debit,
            "end_credit": b.end_credit
        })

    # Внутренние остатки (InternalBalance) – используем full_account_code, если есть
    internal_stmt = (
        select(
            InternalBalance,
            Account.code,
            InternalBalance.full_account_code,
            Organization.inn,
            Organization.name
        )
        .join(Account, InternalBalance.account_id == Account.id)
        .join(Organization, InternalBalance.counterparty_organization_id == Organization.id)
        .where(InternalBalance.organization_id == org.id, InternalBalance.period_date == period_date)
    )
    internal_res = await session.execute(internal_stmt)
    internals = []
    for ib, code, full_code, c_inn, c_name in internal_res:
        account_display = full_code or code
        internals.append({
            "account_code": account_display,
            "counterparty_inn": c_inn,
            "counterparty_name": c_name,
            "end_debit": ib.end_debit,
            "end_credit": ib.end_credit
        })

    return {
        "organization": {"inn": org.inn, "name": org.name},
        "period_date": period_date,
        "balances": balances,
        "internal": internals
    }