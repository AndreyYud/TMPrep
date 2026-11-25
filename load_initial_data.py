#!/usr/bin/env python3
"""
Скрипт для загрузки начальных справочников организаций, счетов и типов организаций из Excel-файлов.
Запуск: python load_initial_data.py
Файлы должны находиться в той же папке, что и скрипт, или укажите пути в переменных.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import pandas as pd
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.models import Organization, Account, OrganizationType

ORG_FILE = Path(__file__).parent / "Организации-.xlsx"
ACCOUNT_FILE = Path(__file__).parent / "План счетов-.xlsx"

async def load_organization_types(session, type_names):
    """Загружает типы организаций в справочник, если их ещё нет."""
    added = 0
    for name in type_names:
        if not name or pd.isna(name):
            continue
        name = str(name).strip()
        if not name:
            continue
        stmt = select(OrganizationType).where(OrganizationType.name == name)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            new_type = OrganizationType(name=name)
            session.add(new_type)
            added += 1
    if added:
        await session.commit()
    return added

async def load_organizations(session):
    """Загружает организации из Excel-файла, включая типы."""
    if not ORG_FILE.exists():
        print(f"Файл {ORG_FILE} не найден, пропускаем загрузку организаций.")
        return 0, 0, 0

    df = pd.read_excel(ORG_FILE, sheet_name=0, header=None, dtype=str)
    # Ищем строку с заголовком, содержащим "ИНН" (регистронезависимо)
    header_row_idx = None
    for idx, row in df.iterrows():
        for cell in row:
            if pd.notna(cell) and isinstance(cell, str) and "инн" in cell.lower():
                header_row_idx = idx
                break
        if header_row_idx is not None:
            break

    if header_row_idx is None:
        print("Не найден заголовок с 'ИНН' в файле организаций, пропускаем.")
        return 0, 0, 0

    # Определяем индексы колонок по заголовку
    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for i, cell in enumerate(header_row):
        if pd.isna(cell):
            continue
        cell_str = str(cell).strip().lower()
        if "инн" in cell_str:
            col_indices['inn'] = i
        elif "наименование" in cell_str:
            col_indices['name'] = i
        elif "тип" in cell_str:
            col_indices['type'] = i

    if 'inn' not in col_indices:
        print("Не найдена колонка 'ИНН' в заголовке, пропускаем.")
        return 0, 0, 0

    # Собираем данные организаций и уникальные типы
    orgs = []
    type_names = set()
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        # Если в колонке ИНН пусто – прекращаем чтение (считаем, что данные закончились)
        inn_cell = row[col_indices['inn']] if col_indices.get('inn') is not None else None
        if pd.isna(inn_cell):
            break
        inn = str(inn_cell).strip()
        if not inn:
            continue

        name = None
        if 'name' in col_indices:
            name_val = row[col_indices['name']]
            if pd.notna(name_val):
                name = str(name_val).strip()

        type_name = None
        if 'type' in col_indices:
            type_val = row[col_indices['type']]
            if pd.notna(type_val):
                type_name = str(type_val).strip()
                if type_name:
                    type_names.add(type_name)

        orgs.append({"inn": inn, "name": name, "type_name": type_name})

    if not orgs:
        print("Не найдено ни одной организации после заголовка.")
        return 0, 0, 0

    # Загружаем уникальные типы в справочник
    type_added = await load_organization_types(session, type_names)

    # Теперь загружаем организации, связывая с типами
    added = 0
    updated = 0
    for org_data in orgs:
        stmt = select(Organization).where(Organization.inn == org_data["inn"])
        result = await session.execute(stmt)
        existing = result.scalars().first()

        # Находим ID типа
        type_id = None
        if org_data["type_name"]:
            stmt_type = select(OrganizationType).where(OrganizationType.name == org_data["type_name"])
            type_result = await session.execute(stmt_type)
            type_obj = type_result.scalars().first()
            if type_obj:
                type_id = type_obj.id

        if existing:
            # Обновляем имя и тип, если они изменились
            changed = False
            if existing.name != org_data["name"]:
                existing.name = org_data["name"]
                changed = True
            if existing.type_id != type_id:
                existing.type_id = type_id
                changed = True
            if changed:
                session.add(existing)
                updated += 1
            else:
                # Считаем как пропущенные (уже есть)
                pass
        else:
            org = Organization(inn=org_data["inn"], name=org_data["name"], type_id=type_id)
            session.add(org)
            added += 1

    await session.commit()
    return added, updated, type_added

async def load_accounts(session):
    """Загружает счета из Excel-файла."""
    if not ACCOUNT_FILE.exists():
        print(f"Файл {ACCOUNT_FILE} не найден, пропускаем загрузку счетов.")
        return 0, 0

    df = pd.read_excel(ACCOUNT_FILE, sheet_name=0, header=0, dtype=str)
    if "Код счета" not in df.columns or "Наименование счета" not in df.columns:
        print("В файле счетов не найдены нужные колонки, пропускаем.")
        return 0, 0

    added = 0
    updated = 0
    for _, row in df.iterrows():
        code = row["Код счета"]
        name = row["Наименование счета"]
        if pd.isna(code):
            continue
        code = str(code).strip()
        if not code:
            continue
        name = str(name).strip() if pd.notna(name) else None

        stmt = select(Account).where(Account.code == code)
        result = await session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            if existing.name != name:
                existing.name = name
                session.add(existing)
                updated += 1
            continue

        acc = Account(code=code, name=name)
        session.add(acc)
        added += 1

    await session.commit()
    return added, updated

async def main():
    # Создаём таблицы, если их нет
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print("Загрузка организаций...")
        org_added, org_updated, type_added = await load_organizations(session)
        print(f"Организации: добавлено {org_added}, обновлено {org_updated}")
        print(f"Добавлено новых типов: {type_added}")

        print("Загрузка счетов...")
        acc_added, acc_updated = await load_accounts(session)
        print(f"Счета: добавлено {acc_added}, обновлено {acc_updated}")

if __name__ == "__main__":
    asyncio.run(main())