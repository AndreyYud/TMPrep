from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

class BalanceItem(BaseModel):
    account_code: str
    end_debit: Decimal
    end_credit: Decimal

class InternalItem(BaseModel):
    account_code: str
    counterparty_inn: str
    counterparty_name: Optional[str]
    end_debit: Decimal
    end_credit: Decimal

class PeriodListItem(BaseModel):
    organization_inn: str
    organization_name: Optional[str]
    period_date: date
    created_at: datetime
    balances_count: int
    internal_count: int

class ReportDetail(BaseModel):
    organization: dict
    period_date: date
    balances: list[BalanceItem]
    internal: list[InternalItem]