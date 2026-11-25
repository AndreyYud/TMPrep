from sqlalchemy import Column, Integer, ForeignKey, Numeric, Date, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class Balance(Base):
    __tablename__ = "balance"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    period_date = Column(Date, nullable=False)

    end_debit = Column(Numeric(20, 2), default=0)
    end_credit = Column(Numeric(20, 2), default=0)

    full_account_code = Column(String, nullable=True)  # полный код счета (с субсчетом)

    __table_args__ = (
        UniqueConstraint('organization_id', 'period_date', 'account_id', name='uix_balance'),
    )

    organization = relationship("Organization")
    account = relationship("Account")