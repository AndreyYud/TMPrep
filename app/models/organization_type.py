from sqlalchemy import Column, Integer, String
from app.core.database import Base

class OrganizationType(Base):
    __tablename__ = "organization_type"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)