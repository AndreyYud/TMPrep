from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.core.database import Base

balance_rule_account = Table(
    'balance_rule_account',
    Base.metadata,
    Column('balance_rule_id', Integer, ForeignKey('balance_rule.id'), primary_key=True),
    Column('account_id', Integer, ForeignKey('account.id'), primary_key=True)
)

class BalanceRule(Base):
    __tablename__ = "balance_rule"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("balance_section.id"), nullable=False)
    subsection_id = Column(Integer, ForeignKey("balance_subsection.id"), nullable=False)
    item = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    accounts = relationship("Account", secondary=balance_rule_account, back_populates="balance_rules")
    section = relationship("BalanceSection")
    subsection = relationship("BalanceSubsection")

    @property
    def account_codes(self):
        """Возвращает список кодов счетов, связанных с правилом."""
        return [acc.code for acc in self.accounts]