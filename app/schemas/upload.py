from pydantic import BaseModel
from datetime import date
from typing import Optional

class UploadResponse(BaseModel):
    period_date: date
    balances_count: int
    internal_count: int
    organization_inn: str

class UploadRequest(BaseModel):
    organization_inn: Optional[str] = None