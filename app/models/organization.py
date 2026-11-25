from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Organization(Base):
    __tablename__ = "organization"

    id = Column(Integer, primary_key=True, index=True)
    inn = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    type_id = Column(Integer, ForeignKey("organization_type.id"), nullable=True)

    type = relationship("OrganizationType")