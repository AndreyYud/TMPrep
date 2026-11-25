from pydantic import BaseModel
from typing import Optional

class OrgTypeBase(BaseModel):
    name: str

class OrgTypeCreate(OrgTypeBase):
    pass

class OrgTypeUpdate(BaseModel):
    name: Optional[str] = None

class OrgTypeResponse(OrgTypeBase):
    id: int

    class Config:
        from_attributes = True