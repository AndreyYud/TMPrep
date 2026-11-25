from pydantic import BaseModel, Field
from typing import Optional

class AccountBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = None

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = None

class AccountResponse(AccountBase):
    id: int

    class Config:
        from_attributes = True