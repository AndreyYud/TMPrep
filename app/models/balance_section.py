from sqlalchemy import Column, Integer, String
from app.core.database import Base

class BalanceSection(Base):
    __tablename__ = "balance_section"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    order = Column(Integer, default=0)