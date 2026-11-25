from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class BalanceSubsection(Base):
    __tablename__ = "balance_subsection"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    section_id = Column(Integer, ForeignKey("balance_section.id"), nullable=False)
    order = Column(Integer, default=0)

    section = relationship("BalanceSection")