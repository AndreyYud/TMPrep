from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from decimal import Decimal
from collections import defaultdict
from datetime import date
from app.models import Organization, Balance, InternalBalance, BalanceRule, Account, BalanceSubsection

def extract_main_account(code: str) -> str:
    if '.' in code:
        return code.split('.')[0]
    return code

async def build_consolidated_balance(
    session: AsyncSession,
    org_inn: str,
    period_date: date
) -> dict:
    # 1. Организация
    stmt = select(Organization).where(Organization.inn == org_inn)
    org = (await session.execute(stmt)).scalars().first()
    if not org:
        raise ValueError("Организация не найдена")

    # 2. Чтение балансов с полным кодом счета
    bal_stmt = (
        select(Balance, Account.code, Balance.full_account_code)
        .join(Account, Balance.account_id == Account.id)
        .where(Balance.organization_id == org.id, Balance.period_date == period_date)
    )
    balances_res = await session.execute(bal_stmt)
    balances_by_account = {}
    for b, code, full_code in balances_res:
        balances_by_account[code] = {
            "debit": b.end_debit,
            "credit": b.end_credit,
            "full_account_code": full_code or code
        }

    # 3. Получение детальных записей внутренних остатков с контрагентами
    internal_stmt = (
        select(
            InternalBalance,
            Account.code,
            InternalBalance.full_account_code,
            Organization.inn.label('counterparty_inn'),
            Organization.name.label('counterparty_name')
        )
        .join(Account, InternalBalance.account_id == Account.id)
        .join(Organization, InternalBalance.counterparty_organization_id == Organization.id)
        .where(InternalBalance.organization_id == org.id, InternalBalance.period_date == period_date)
    )
    internal_res = await session.execute(internal_stmt)
    internal_details_by_account = defaultdict(list)
    internal_by_account = defaultdict(lambda: {"debit": Decimal(0), "credit": Decimal(0)})
    for ib, code, full_code, counterparty_inn, counterparty_name in internal_res:
        internal_details_by_account[code].append({
            "debit": ib.end_debit,
            "credit": ib.end_credit,
            "full_account_code": full_code or code,
            "counterparty_inn": counterparty_inn,
            "counterparty_name": counterparty_name
        })
        internal_by_account[code]["debit"] += ib.end_debit
        internal_by_account[code]["credit"] += ib.end_credit

    # 4. Правила
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

    # 5. Агрегация
    agg_data = defaultdict(lambda: {
        "debit": Decimal(0),
        "credit": Decimal(0),
        "full_debit": Decimal(0),
        "full_credit": Decimal(0),
        "internal_debit": Decimal(0),
        "internal_credit": Decimal(0),
        "details": []
    })

    def add_to_agg(
        section_name, subsection_name, item_name, is_active,
        debit, credit,
        full_debit=Decimal(0), full_credit=Decimal(0),
        internal_debit=Decimal(0), internal_credit=Decimal(0)
    ):
        key = (section_name, subsection_name or "", item_name or "", is_active)
        entry = agg_data[key]
        entry["debit"] += debit
        entry["credit"] += credit
        entry["full_debit"] += full_debit
        entry["full_credit"] += full_credit
        entry["internal_debit"] += internal_debit
        entry["internal_credit"] += internal_credit

    def add_detail_to_agg(
        section_name, subsection_name, item_name, is_active,
        account_code, source, debit, credit, counterparty_inn=None, counterparty_name=None
    ):
        key = (section_name, subsection_name or "", item_name or "", is_active)
        balance = debit - credit if is_active else credit - debit
        agg_data[key]["details"].append({
            "account_code": account_code,
            "source": source,
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "counterparty_inn": counterparty_inn,
            "counterparty_name": counterparty_name
        })

    def process_account(
        account_code,
        debit,
        credit,
        is_internal=False,
        full_debit=Decimal(0),
        full_credit=Decimal(0),
        internal_debit=Decimal(0),
        internal_credit=Decimal(0),
        internal_details_list=None
    ):
        main_code = extract_main_account(account_code)
        active_rule = account_to_active.get(main_code)
        passive_rule = account_to_passive.get(main_code)

        if active_rule and passive_rule:
            if is_internal:
                add_to_agg(
                    "Внутренние взаиморасчеты",
                    active_rule.subsection.name,
                    active_rule.item,
                    True,
                    debit,
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                    debit,
                    Decimal(0)
                )
                add_to_agg(
                    "Внутренние взаиморасчеты",
                    passive_rule.subsection.name,
                    passive_rule.item,
                    False,
                    Decimal(0),
                    credit,
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                    credit
                )
                if internal_details_list:
                    for det in internal_details_list:
                        add_detail_to_agg(
                            "Внутренние взаиморасчеты",
                            active_rule.subsection.name,
                            active_rule.item,
                            True,
                            account_code,
                            "internal",
                            det["debit"],
                            Decimal(0),
                            det["counterparty_inn"],
                            det["counterparty_name"]
                        )
                        add_detail_to_agg(
                            "Внутренние взаиморасчеты",
                            passive_rule.subsection.name,
                            passive_rule.item,
                            False,
                            account_code,
                            "internal",
                            Decimal(0),
                            det["credit"],
                            det["counterparty_inn"],
                            det["counterparty_name"]
                        )
            else:
                add_to_agg(
                    active_rule.section.name,
                    active_rule.subsection.name,
                    active_rule.item,
                    True,
                    debit,
                    Decimal(0),
                    full_debit,
                    Decimal(0),
                    internal_debit,
                    Decimal(0)
                )
                add_to_agg(
                    passive_rule.section.name,
                    passive_rule.subsection.name,
                    passive_rule.item,
                    False,
                    Decimal(0),
                    credit,
                    Decimal(0),
                    full_credit,
                    Decimal(0),
                    internal_credit
                )
                if full_debit != 0 or full_credit != 0:
                    add_detail_to_agg(
                        active_rule.section.name,
                        active_rule.subsection.name,
                        active_rule.item,
                        True,
                        account_code,
                        "full",
                        full_debit,
                        Decimal(0)
                    )
                    if full_credit != 0:
                        add_detail_to_agg(
                            passive_rule.section.name,
                            passive_rule.subsection.name,
                            passive_rule.item,
                            False,
                            account_code,
                            "full",
                            Decimal(0),
                            full_credit
                        )
                if internal_details_list:
                    for det in internal_details_list:
                        if det["debit"] != 0:
                            add_detail_to_agg(
                                active_rule.section.name,
                                active_rule.subsection.name,
                                active_rule.item,
                                True,
                                account_code,
                                "internal",
                                det["debit"],
                                Decimal(0),
                                det["counterparty_inn"],
                                det["counterparty_name"]
                            )
                        if det["credit"] != 0:
                            add_detail_to_agg(
                                passive_rule.section.name,
                                passive_rule.subsection.name,
                                passive_rule.item,
                                False,
                                account_code,
                                "internal",
                                Decimal(0),
                                det["credit"],
                                det["counterparty_inn"],
                                det["counterparty_name"]
                            )
        elif active_rule:
            net = debit - credit
            section_name = "Внутренние взаиморасчеты" if is_internal else active_rule.section.name
            subsection_name = active_rule.subsection.name
            item_name = active_rule.item

            if net >= 0:
                add_to_agg(
                    section_name,
                    subsection_name,
                    item_name,
                    True,
                    net,
                    Decimal(0),
                    full_debit,
                    full_credit,
                    internal_debit,
                    internal_credit
                )
            else:
                add_to_agg(
                    section_name,
                    subsection_name,
                    item_name,
                    True,
                    Decimal(0),
                    -net,
                    full_debit,
                    full_credit,
                    internal_debit,
                    internal_credit
                )

            if full_debit != 0 or full_credit != 0:
                add_detail_to_agg(
                    section_name,
                    subsection_name,
                    item_name,
                    True,
                    account_code,
                    "full",
                    full_debit,
                    full_credit
                )

            if internal_details_list:
                for det in internal_details_list:
                    if det["debit"] != 0 or det["credit"] != 0:
                        add_detail_to_agg(
                            section_name,
                            subsection_name,
                            item_name,
                            True,
                            account_code,
                            "internal",
                            det["debit"],
                            det["credit"],
                            det["counterparty_inn"],
                            det["counterparty_name"]
                        )
        elif passive_rule:
            net = credit - debit
            section_name = "Внутренние взаиморасчеты" if is_internal else passive_rule.section.name
            subsection_name = passive_rule.subsection.name
            item_name = passive_rule.item

            if net >= 0:
                add_to_agg(
                    section_name,
                    subsection_name,
                    item_name,
                    False,
                    Decimal(0),
                    net,
                    full_debit,
                    full_credit,
                    internal_debit,
                    internal_credit
                )
            else:
                add_to_agg(
                    section_name,
                    subsection_name,
                    item_name,
                    False,
                    -net,
                    Decimal(0),
                    full_debit,
                    full_credit,
                    internal_debit,
                    internal_credit
                )

            if full_debit != 0 or full_credit != 0:
                add_detail_to_agg(
                    section_name,
                    subsection_name,
                    item_name,
                    False,
                    account_code,
                    "full",
                    full_debit,
                    full_credit
                )

            if internal_details_list:
                for det in internal_details_list:
                    if det["debit"] != 0 or det["credit"] != 0:
                        add_detail_to_agg(
                            section_name,
                            subsection_name,
                            item_name,
                            False,
                            account_code,
                            "internal",
                            det["debit"],
                            det["credit"],
                            det["counterparty_inn"],
                            det["counterparty_name"]
                        )
        else:
            net = debit - credit
            section = "Внутренние взаиморасчеты" if is_internal else "Прочие"
            if net >= 0:
                add_to_agg(
                    section,
                    None,
                    None,
                    True,
                    net,
                    Decimal(0),
                    full_debit,
                    full_credit,
                    internal_debit,
                    internal_credit
                )
            else:
                add_to_agg(
                    section,
                    None,
                    None,
                    True,
                    Decimal(0),
                    -net,
                    full_debit,
                    full_credit,
                    internal_debit,
                    internal_credit
                )

            if full_debit != 0 or full_credit != 0:
                add_detail_to_agg(
                    section,
                    None,
                    None,
                    True,
                    account_code,
                    "full",
                    full_debit,
                    full_credit
                )

            if internal_details_list:
                for det in internal_details_list:
                    if det["debit"] != 0 or det["credit"] != 0:
                        add_detail_to_agg(
                            section,
                            None,
                            None,
                            True,
                            account_code,
                            "internal",
                            det["debit"],
                            det["credit"],
                            det["counterparty_inn"],
                            det["counterparty_name"]
                        )

    # 6. Обработка внешних остатков
    for account_code, balances in balances_by_account.items():
        debit = balances["debit"]
        credit = balances["credit"]
        full_acc_code = balances["full_account_code"]
        internal = internal_by_account.get(account_code, {"debit": Decimal(0), "credit": Decimal(0)})
        int_debit = internal["debit"]
        int_credit = internal["credit"]

        ext_debit = max(debit - int_debit, Decimal(0))
        ext_credit = max(credit - int_credit, Decimal(0))

        if ext_debit == 0 and ext_credit == 0:
            continue

        internal_details_list = internal_details_by_account.get(account_code, [])
        process_account(
            full_acc_code,
            ext_debit,
            ext_credit,
            is_internal=False,
            full_debit=debit,
            full_credit=credit,
            internal_debit=int_debit,
            internal_credit=int_credit,
            internal_details_list=internal_details_list
        )

    # 7. Обработка внутренних остатков
    for account_code, details in internal_details_by_account.items():
        for detail in details:
            int_debit = detail["debit"]
            int_credit = detail["credit"]
            full_acc_code = detail["full_account_code"]
            if int_debit == 0 and int_credit == 0:
                continue
            process_account(
                full_acc_code,
                int_debit,
                int_credit,
                is_internal=True,
                full_debit=Decimal(0),
                full_credit=Decimal(0),
                internal_debit=int_debit,
                internal_credit=int_credit,
                internal_details_list=[detail]
            )

    # 8. Построение иерархии
    def build_hierarchy():
        types = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [])))

        for (section, subsection, item, is_active), vals in agg_data.items():
            if vals["debit"] == 0 and vals["credit"] == 0:
                continue
            balance = vals["debit"] - vals["credit"] if is_active else vals["credit"] - vals["debit"]
            types[is_active][section][subsection].append({
                "name": item if item else "Без статьи",
                "debit": vals["debit"],
                "credit": vals["credit"],
                "balance": balance,
                "full_debit": vals["full_debit"],
                "full_credit": vals["full_credit"],
                "internal_debit": vals["internal_debit"],
                "internal_credit": vals["internal_credit"],
                "details": vals["details"]
            })

        hierarchy = []
        for is_active in [True, False]:
            type_data = types[is_active]
            if not type_data:
                continue

            type_obj = {
                "is_active": is_active,
                "total_debit": Decimal(0),
                "total_credit": Decimal(0),
                "total_balance": Decimal(0),
                "sections": []
            }

            # Разделы: сначала все, кроме "Внутренние взаиморасчеты" (по алфавиту), потом "Внутренние взаиморасчеты"
            sections = sorted([s for s in type_data.keys() if s != "Внутренние взаиморасчеты"])
            if "Внутренние взаиморасчеты" in type_data:
                sections.append("Внутренние взаиморасчеты")

            for section in sections:
                subsections = type_data[section]
                section_obj = {
                    "name": section,
                    "total_debit": Decimal(0),
                    "total_credit": Decimal(0),
                    "total_balance": Decimal(0),
                    "subsections": []
                }

                for subsection in sorted(subsections.keys()):
                    items = subsections[subsection]
                    subsection_obj = {
                        "name": subsection if subsection else None,
                        "total_debit": Decimal(0),
                        "total_credit": Decimal(0),
                        "total_balance": Decimal(0),
                        "items": []
                    }
                    sorted_items = sorted(items, key=lambda x: x["name"])
                    for item in sorted_items:
                        subsection_obj["items"].append(item)
                        subsection_obj["total_debit"] += item["debit"]
                        subsection_obj["total_credit"] += item["credit"]
                        subsection_obj["total_balance"] += item["balance"]

                    section_obj["subsections"].append(subsection_obj)
                    section_obj["total_debit"] += subsection_obj["total_debit"]
                    section_obj["total_credit"] += subsection_obj["total_credit"]
                    section_obj["total_balance"] += subsection_obj["total_balance"]

                type_obj["sections"].append(section_obj)
                type_obj["total_debit"] += section_obj["total_debit"]
                type_obj["total_credit"] += section_obj["total_credit"]
                type_obj["total_balance"] += section_obj["total_balance"]

            hierarchy.append(type_obj)

        return hierarchy

    hierarchy = build_hierarchy()

    return {
        "organization_inn": org.inn,
        "organization_name": org.name,
        "period_date": period_date.isoformat(),
        "sections": hierarchy
    }