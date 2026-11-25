from pydantic import BaseModel
from typing import Optional

class BalanceSubsectionBase(BaseModel):
    name: str
    section_id: int
    order: int = 0

class BalanceSubsectionCreate(BalanceSubsectionBase):
    pass

class BalanceSubsectionUpdate(BaseModel):
    name: Optional[str] = None
    section_id: Optional[int] = None
    order: Optional[int] = None

class BalanceSubsectionResponse(BalanceSubsectionBase):
    id: int
    section: Optional["BalanceSectionResponse"] = None

    class Config:
        from_attributes = True

from app.schemas.balance_section import BalanceSectionResponse
BalanceSubsectionResponse.model_rebuild()