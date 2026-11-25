from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from decimal import Decimal
from collections import defaultdict
from datetime import date
from typing import List, Dict, Any
from app.models import Organization, InternalBalance, BalanceRule, Account, BalanceSubsection

async def build_internal_balance_for_orgs(
    session: AsyncSession,
    org_inns: List[str],
    period_date: date
) -> Dict[str, Any]:
    if not org_inns:
        raise ValueError("Не выбрано ни одной организации")

    orgs = []
    org_names = []
    skipped = []
    for inn in org_inns:
        stmt = select(Organization).where(Organization.inn == inn)
        result = await session.execute(stmt)
        org = result.scalars().first()
        if not org:
            skipped.append(inn)
            continue
        orgs.append(org)
        org_names.append(org.name or inn)

    if not orgs:
        raise ValueError("Не найдено ни одной организации из выбранных")

    org_ids = [org.id for org in orgs]

    rules_stmt = select(BalanceRule).options(
        selectinload(BalanceRule.accounts),
        selectinload(BalanceRule.section),
        selectinload(BalanceRule.subsection).selectinload(BalanceSubsection.section)
    )
    rules_res = await session.execute(rules_stmt)
    rules = rules_res.scalars().all()
    account_to_active = {}
    account_to_passive = {}
    for rule in rules:
        for acc in rule.accounts:
            if rule.is_active:
                account_to_active[acc.code] = rule
            else:
                account_to_passive[acc.code] = rule

    agg = defaultdict(lambda: {
        "total": Decimal(0),
        "org_values": defaultdict(Decimal),
        "counterparty_name": "",
    })

    for org in orgs:
        stmt = (
            select(
                Account.code,
                InternalBalance.counterparty_organization_id,
                func.sum(InternalBalance.end_debit).label('total_debit'),
                func.sum(InternalBalance.end_credit).label('total_credit')
            )
            .join(Account, InternalBalance.account_id == Account.id)
            .where(
                InternalBalance.organization_id == org.id,
                InternalBalance.period_date == period_date,
                InternalBalance.counterparty_organization_id.in_(org_ids)
            )
            .group_by(
                Account.code,
                InternalBalance.counterparty_organization_id
            )
        )
        result = await session.execute(stmt)
        for account_code, counterparty_id, debit, credit in result:
            counterparty = await session.get(Organization, counterparty_id)
            if not counterparty:
                continue

            active_rule = account_to_active.get(account_code)
            passive_rule = account_to_passive.get(account_code)

            if active_rule and passive_rule:
                if debit:
                    section = active_rule.section.name
                    subsection = active_rule.subsection.name or ""
                    item = active_rule.item or ""
                    is_active = True
                    key = (is_active, section, subsection, item, counterparty.inn)
                    agg[key]["total"] += debit
                    agg[key]["org_values"][org.inn] += debit
                    agg[key]["counterparty_name"] = counterparty.name or counterparty.inn
                if credit:
                    section = passive_rule.section.name
                    subsection = passive_rule.subsection.name or ""
                    item = passive_rule.item or ""
                    is_active = False
                    key = (is_active, section, subsection, item, counterparty.inn)
                    agg[key]["total"] += credit
                    agg[key]["org_values"][org.inn] += credit
                    agg[key]["counterparty_name"] = counterparty.name or counterparty.inn
            elif active_rule:
                net = debit - credit
                if net:
                    section = active_rule.section.name
                    subsection = active_rule.subsection.name or ""
                    item = active_rule.item or ""
                    is_active = True
                    key = (is_active, section, subsection, item, counterparty.inn)
                    agg[key]["total"] += net
                    agg[key]["org_values"][org.inn] += net
                    agg[key]["counterparty_name"] = counterparty.name or counterparty.inn
            elif passive_rule:
                net = credit - debit
                if net:
                    section = passive_rule.section.name
                    subsection = passive_rule.subsection.name or ""
                    item = passive_rule.item or ""
                    is_active = False
                    key = (is_active, section, subsection, item, counterparty.inn)
                    agg[key]["total"] += net
                    agg[key]["org_values"][org.inn] += net
                    agg[key]["counterparty_name"] = counterparty.name or counterparty.inn
            else:
                net = debit - credit
                if net:
                    section = "Прочие"
                    subsection = ""
                    item = ""
                    is_active = True
                    key = (is_active, section, subsection, item, counterparty.inn)
                    agg[key]["total"] += net
                    agg[key]["org_values"][org.inn] += net
                    agg[key]["counterparty_name"] = counterparty.name or counterparty.inn

    rows = []
    for is_active in [True, False]:
        sections = set()
        subsections_by_section = defaultdict(set)
        items_by_subsection = defaultdict(list)

        for (act, section, subsection, item, counterparty_inn), vals in agg.items():
            if act != is_active:
                continue
            sections.add(section)
            subsections_by_section[section].add(subsection)
            items_by_subsection[(section, subsection)].append((item, counterparty_inn, vals))

        if not sections:
            continue

        type_total = Decimal(0)
        type_org_totals = defaultdict(Decimal)
        for (act, section, subsection, item, counterparty_inn), vals in agg.items():
            if act != is_active:
                continue
            type_total += vals["total"]
            for org_inn, val in vals["org_values"].items():
                type_org_totals[org_inn] += val

        rows.append({
            "type": "type_total",
            "section": None,
            "subsection": None,
            "item": None,
            "counterparty_inn": None,
            "counterparty_name": None,
            "is_active": is_active,
            "total": type_total,
            "org_values": dict(type_org_totals),
        })

        for section in sorted(sections):
            section_total = Decimal(0)
            section_org_totals = defaultdict(Decimal)
            for (act, sec, subsection, item, counterparty_inn), vals in agg.items():
                if act != is_active or sec != section:
                    continue
                section_total += vals["total"]
                for org_inn, val in vals["org_values"].items():
                    section_org_totals[org_inn] += val

            rows.append({
                "type": "section_total",
                "section": section,
                "subsection": None,
                "item": None,
                "counterparty_inn": None,
                "counterparty_name": None,
                "is_active": is_active,
                "total": section_total,
                "org_values": dict(section_org_totals),
            })

            subsections = sorted(subsections_by_section[section])
            for subsection in subsections:
                subsection_total = Decimal(0)
                subsection_org_totals = defaultdict(Decimal)
                items_in_subsection = []
                for (item, counterparty_inn, vals) in items_by_subsection.get((section, subsection), []):
                    subsection_total += vals["total"]
                    for org_inn, val in vals["org_values"].items():
                        subsection_org_totals[org_inn] += val
                    items_in_subsection.append({
                        "item": item,
                        "counterparty_inn": counterparty_inn,
                        "counterparty_name": vals["counterparty_name"],
                        "total": vals["total"],
                        "org_values": dict(vals["org_values"]),
                    })

                if subsection:
                    rows.append({
                        "type": "subsection_total",
                        "section": section,
                        "subsection": subsection,
                        "item": None,
                        "counterparty_inn": None,
                        "counterparty_name": None,
                        "is_active": is_active,
                        "total": subsection_total,
                        "org_values": dict(subsection_org_totals),
                    })

                for item_data in items_in_subsection:
                    rows.append({
                        "type": "item",
                        "section": section,
                        "subsection": subsection if subsection else None,
                        "item": item_data["item"],
                        "counterparty_inn": item_data["counterparty_inn"],
                        "counterparty_name": item_data["counterparty_name"],
                        "is_active": is_active,
                        "total": item_data["total"],
                        "org_values": item_data["org_values"],
                    })

    total_by_org = defaultdict(Decimal)
    grand_total = Decimal(0)
    for row in rows:
        if row["type"] == "type_total":
            for org_inn, val in row["org_values"].items():
                total_by_org[org_inn] += val
                grand_total += val

    return {
        "organizations": [org.inn for org in orgs],
        "organization_names": org_names,
        "skipped_organizations": skipped,
        "period_date": period_date.isoformat(),
        "rows": rows,
        "totals": {
            "by_org": dict(total_by_org),
            "grand": grand_total
        }
    }