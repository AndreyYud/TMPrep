from pydantic import BaseModel
from decimal import Decimal
from typing import List, Optional, Dict

# ============================================================================
# Модели для управленческого баланса (одна организация) – с расшифровкой
# ============================================================================

class AccountDetail(BaseModel):
    account_code: str
    source: str  # 'full' или 'internal'
    debit: Decimal
    credit: Decimal
    balance: Decimal
    counterparty_inn: Optional[str] = None
    counterparty_name: Optional[str] = None

class BalanceItem(BaseModel):
    name: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    full_debit: Decimal = Decimal(0)
    full_credit: Decimal = Decimal(0)
    internal_debit: Decimal = Decimal(0)
    internal_credit: Decimal = Decimal(0)
    details: List[AccountDetail] = []

class BalanceSubsection(BaseModel):
    name: Optional[str]
    total_debit: Decimal
    total_credit: Decimal
    total_balance: Decimal
    items: List[BalanceItem]

class BalanceSection(BaseModel):
    name: str
    total_debit: Decimal
    total_credit: Decimal
    total_balance: Decimal
    subsections: List[BalanceSubsection]

class BalanceType(BaseModel):
    is_active: bool
    total_debit: Decimal
    total_credit: Decimal
    total_balance: Decimal
    sections: List[BalanceSection]

class ConsolidatedBalanceResponse(BaseModel):
    organization_inn: str
    organization_name: Optional[str]
    period_date: str
    sections: List[BalanceType]


# ============================================================================
# Модели для консолидированного баланса (несколько организаций) – без расшифровок
# ============================================================================

class ConsolidatedRow(BaseModel):
    type: str  # 'type_total', 'section_total', 'subsection_total', 'item'
    is_active: bool
    section: Optional[str] = None
    subsection: Optional[str] = None
    item: Optional[str] = None
    total: Decimal
    org_values: Dict[str, Decimal]  # {inn: значение}

class ConsolidatedBalanceTotals(BaseModel):
    by_org: Dict[str, Decimal]
    grand: Decimal

class ConsolidatedBalanceRequest(BaseModel):
    org_inns: List[str]
    period_date: str

class ConsolidatedBalanceMultiResponse(BaseModel):
    organizations: List[str]
    organization_names: List[str]
    skipped_organizations: Optional[List[str]] = []
    period_date: str
    rows: List[ConsolidatedRow]
    totals: ConsolidatedBalanceTotals


# ============================================================================
# Модели для сводного баланса внутренних взаиморасчетов – без расшифровок
# ============================================================================

class InternalBalanceRequest(BaseModel):
    org_inns: List[str]
    period_date: str

class InternalBalanceRow(BaseModel):
    type: str  # 'item', 'subsection_total', 'section_total', 'type_total'
    section: Optional[str]
    subsection: Optional[str]
    item: Optional[str]
    counterparty_inn: Optional[str] = None
    counterparty_name: Optional[str] = None
    is_active: bool
    total: Decimal
    org_values: Dict[str, Decimal]

class InternalBalanceTotals(BaseModel):
    by_org: Dict[str, Decimal]
    grand: Decimal

class InternalBalanceMultiResponse(BaseModel):
    organizations: List[str]
    organization_names: List[str]
    skipped_organizations: Optional[List[str]] = []
    period_date: str
    rows: List[InternalBalanceRow]
    totals: InternalBalanceTotals