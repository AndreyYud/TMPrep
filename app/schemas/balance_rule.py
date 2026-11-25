from pydantic import BaseModel
from typing import Optional, List

class BalanceRuleBase(BaseModel):
    section_id: int
    subsection_id: int
    item: Optional[str] = None
    is_active: bool = True
    account_codes: List[str]

class BalanceRuleCreate(BalanceRuleBase):
    pass

class BalanceRuleUpdate(BaseModel):
    section_id: Optional[int] = None
    subsection_id: Optional[int] = None
    item: Optional[str] = None
    is_active: Optional[bool] = None
    account_codes: Optional[List[str]] = None

class BalanceRuleResponse(BalanceRuleBase):
    id: int
    section: "BalanceSectionResponse"
    subsection: "BalanceSubsectionResponse"

    class Config:
        from_attributes = True

from app.schemas.balance_section import BalanceSectionResponse
from app.schemas.balance_subsection import BalanceSubsectionResponse
BalanceRuleResponse.model_rebuild()