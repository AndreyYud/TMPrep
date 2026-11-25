from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)

    # Обратная связь с правилами баланса
    balance_rules = relationship("BalanceRule", secondary="balance_rule_account", back_populates="accounts")