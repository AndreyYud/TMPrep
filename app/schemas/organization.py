from pydantic import BaseModel, Field
from typing import Optional

class OrganizationBase(BaseModel):
    inn: str = Field(..., min_length=10, max_length=12)
    name: Optional[str] = None
    type_id: Optional[int] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    inn: Optional[str] = Field(None, min_length=10, max_length=12)
    name: Optional[str] = None
    type_id: Optional[int] = None

class OrganizationResponse(OrganizationBase):
    id: int
    type: Optional["OrgTypeResponse"] = None

    class Config:
        from_attributes = True

# Чтобы избежать циклических импортов, импортируем позже
from app.schemas.org_type import OrgTypeResponse
OrganizationResponse.model_rebuild()