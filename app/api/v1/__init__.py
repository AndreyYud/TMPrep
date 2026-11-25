from fastapi import APIRouter
from . import upload, balances, report, organizations, accounts, org_types
from . import balance_rules, balance_sections, balance_subsections
from . import balance, consolidated_balance, internal_balance

router = APIRouter(prefix="/v1")
router.include_router(upload.router)
router.include_router(balances.router)
router.include_router(report.router)
router.include_router(organizations.router)
router.include_router(accounts.router)
router.include_router(org_types.router)
router.include_router(balance_rules.router)
router.include_router(balance_sections.router)
router.include_router(balance_subsections.router)
router.include_router(balance.router)
router.include_router(consolidated_balance.router)
router.include_router(internal_balance.router)