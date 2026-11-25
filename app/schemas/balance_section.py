from pydantic import BaseModel
from typing import Optional

class BalanceSectionBase(BaseModel):
    name: str
    order: int = 0

class BalanceSectionCreate(BalanceSectionBase):
    pass

class BalanceSectionUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None

class BalanceSectionResponse(BalanceSectionBase):
    id: int

    class Config:
        from_attributes = True