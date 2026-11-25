from sqlalchemy import Column, Integer, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class UploadSession(Base):
    __tablename__ = "upload_session"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    period_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization")