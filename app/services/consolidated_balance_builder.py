from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from collections import defaultdict
from datetime import date
from typing import List, Dict, Any
from .balance_builder import build_consolidated_balance

async def build_consolidated_balance_for_orgs(
    session: AsyncSession,
    org_inns: List[str],
    period_date: date
) -> Dict[str, Any]:
    if not org_inns:
        raise ValueError("Не выбрано ни одной организации")

    org_balances = []
    org_names = []
    skipped_orgs = []
    for inn in org_inns:
        try:
            balance = await build_consolidated_balance(session, inn, period_date)
            org_balances.append(balance)
            org_name = balance.get("organization_name")
            if org_name is None:
                org_name = balance.get("organization", {}).get("name")
            if org_name is None:
                org_name = inn
            org_names.append(org_name)
        except ValueError:
            skipped_orgs.append(inn)

    if not org_balances:
        raise ValueError("Не найдено данных ни для одной из выбранных организаций")

    item_data = defaultdict(lambda: {"org_values": defaultdict(Decimal)})

    for idx, bal in enumerate(org_balances):
        org_inn = org_inns[idx]
        for type_item in bal.get("sections", []):
            is_active = type_item["is_active"]
            for section in type_item.get("sections", []):
                section_name = section["name"]
                for subsection in section.get("subsections", []):
                    subsection_name = subsection["name"] or ""
                    for item in subsection.get("items", []):
                        item_name = item["name"]
                        key = (is_active, section_name, subsection_name, item_name)
                        balance = item["balance"]
                        item_data[key]["org_values"][org_inn] += balance

    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for (is_active, section, subsection, item) in item_data.keys():
        grouped[is_active][section][subsection].append(item)

    rows = []
    total_by_org = {inn: Decimal(0) for inn in org_inns}
    grand_total = Decimal(0)

    for is_active in [True, False]:
        if is_active not in grouped:
            continue

        type_org_totals = {inn: Decimal(0) for inn in org_inns}
        for section, subsections in grouped[is_active].items():
            for subsection, items in subsections.items():
                for item in items:
                    key = (is_active, section, subsection, item)
                    for inn, val in item_data[key]["org_values"].items():
                        type_org_totals[inn] += val

        type_total = sum(type_org_totals.values())
        rows.append({
            "type": "type_total",
            "is_active": is_active,
            "section": None,
            "subsection": None,
            "item": None,
            "total": type_total,
            "org_values": type_org_totals,
        })
        for inn, val in type_org_totals.items():
            total_by_org[inn] += val
        grand_total += type_total

        sections = sorted(
            grouped[is_active].keys(),
            key=lambda x: (1 if x == "Внутренние взаиморасчеты" else 0, x)
        )

        for section in sections:
            section_org_totals = {inn: Decimal(0) for inn in org_inns}
            subsections = grouped[is_active][section]
            for subsection, items in subsections.items():
                for item in items:
                    key = (is_active, section, subsection, item)
                    for inn, val in item_data[key]["org_values"].items():
                        section_org_totals[inn] += val

            section_total = sum(section_org_totals.values())
            rows.append({
                "type": "section_total",
                "is_active": is_active,
                "section": section,
                "subsection": None,
                "item": None,
                "total": section_total,
                "org_values": section_org_totals,
            })

            for subsection in sorted(subsections.keys()):
                subsection_org_totals = {inn: Decimal(0) for inn in org_inns}
                items = subsections[subsection]
                sorted_items = sorted(items)
                for item in sorted_items:
                    key = (is_active, section, subsection, item)
                    org_vals = item_data[key]["org_values"]
                    total_item = sum(org_vals.values())
                    rows.append({
                        "type": "item",
                        "is_active": is_active,
                        "section": section,
                        "subsection": subsection,
                        "item": item,
                        "total": total_item,
                        "org_values": org_vals,
                    })
                    for inn, val in org_vals.items():
                        subsection_org_totals[inn] += val

                subsection_total = sum(subsection_org_totals.values())
                rows.append({
                    "type": "subsection_total",
                    "is_active": is_active,
                    "section": section,
                    "subsection": subsection,
                    "item": None,
                    "total": subsection_total,
                    "org_values": subsection_org_totals,
                })

    return {
        "organizations": org_inns,
        "organization_names": org_names,
        "skipped_organizations": skipped_orgs,
        "period_date": period_date.isoformat(),
        "rows": rows,
        "totals": {
            "by_org": total_by_org,
            "grand": grand_total
        }
    }