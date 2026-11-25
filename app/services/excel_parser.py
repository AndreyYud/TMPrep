import pandas as pd
from io import BytesIO
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime, date


def extract_main_account(code: str) -> str:
    """Извлекает основной счет (до точки)"""
    if '.' in code:
        return code.split('.')[0]
    return code


def parse_full_osv(file_bytes: bytes) -> Tuple[List[Dict], Optional[str], Optional[date]]:
    """
    Парсит файл полной ОСВ.
    Возвращает: (данные, ИНН организации или None, дата периода или None).
    В данных каждый элемент содержит: account_code (основной), full_account_code (полный), end_debit, end_credit.
    """
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None, dtype=str)

    header_row_idx = None
    for idx, row in df.iterrows():
        for cell in row:
            if pd.notna(cell) and isinstance(cell, str) and "счет" in cell.lower():
                header_row_idx = idx
                break
        if header_row_idx is not None:
            break

    if header_row_idx is None:
        raise ValueError("Не найден заголовок с 'Счет' в полной ОСВ")

    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for i, cell in enumerate(header_row):
        if pd.isna(cell):
            continue
        cell_str = str(cell).strip().lower()
        if "счет" in cell_str:
            col_indices['account'] = i
        elif "дт" in cell_str:
            col_indices['debit'] = i
        elif "кт" in cell_str:
            col_indices['credit'] = i
        elif "организация" in cell_str:
            col_indices['org'] = i
        elif "инн" in cell_str:
            col_indices['inn'] = i
        elif "дата" in cell_str:
            col_indices['date'] = i

    required = ['account', 'debit', 'credit']
    for col in required:
        if col not in col_indices:
            raise ValueError(f"Не найдена колонка '{col}' в заголовке полной ОСВ")

    account_idx = col_indices['account']
    debit_idx = col_indices['debit']
    credit_idx = col_indices['credit']
    inn_idx = col_indices.get('inn')
    date_idx = col_indices.get('date')

    grouped = defaultdict(lambda: {"debit": Decimal(0), "credit": Decimal(0), "full_codes": []})
    organization_inn = None
    period_date = None

    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        account_cell = row[account_idx] if account_idx < len(row) else None
        if pd.isna(account_cell):
            break
        account = str(account_cell).strip()
        if not account or "итого" in account.lower():
            continue

        if organization_inn is None and inn_idx is not None:
            inn_cell = row[inn_idx] if inn_idx < len(row) else None
            if pd.notna(inn_cell):
                organization_inn = str(inn_cell).strip()

        if period_date is None and date_idx is not None:
            date_cell = row[date_idx] if date_idx < len(row) else None
            if pd.notna(date_cell):
                try:
                    if isinstance(date_cell, datetime):
                        period_date = date_cell.date()
                    else:
                        period_date = pd.to_datetime(date_cell).date()
                except:
                    pass

        def to_decimal(val):
            if pd.isna(val):
                return Decimal(0)
            if isinstance(val, (int, float)):
                return Decimal(str(val))
            s = str(val).replace(" ", "").replace(",", ".")
            try:
                return Decimal(s)
            except:
                return Decimal(0)

        debit = to_decimal(row[debit_idx]) if debit_idx < len(row) else Decimal(0)
        credit = to_decimal(row[credit_idx]) if credit_idx < len(row) else Decimal(0)

        main_code = extract_main_account(account)
        grouped[main_code]["debit"] += debit
        grouped[main_code]["credit"] += credit
        grouped[main_code]["full_codes"].append(account)  # сохраняем полный код

    if not grouped:
        raise ValueError("Не удалось извлечь данные из полной ОСВ (пустой результат)")

    data = []
    for code, vals in grouped.items():
        full_code = vals["full_codes"][0] if vals["full_codes"] else code
        data.append({
            "account_code": code,  # основной счет для правил
            "full_account_code": full_code,  # полный счет для деталей
            "end_debit": vals["debit"],
            "end_credit": vals["credit"]
        })

    return data, organization_inn, period_date


def parse_internal_osv(file_bytes: bytes) -> Tuple[List[Dict], Optional[str], Optional[date]]:
    """
    Парсит файл внутренней ОСВ.
    Возвращает: (данные, ИНН организации или None, дата периода или None).
    В данных каждый элемент содержит: account_code (основной), full_account_code (полный), counterparty_inn, end_debit, end_credit.
    """
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None, dtype=str)

    header_row_idx = None
    for idx, row in df.iterrows():
        row_has_account = False
        row_has_counterparty = False
        for cell in row:
            if pd.notna(cell) and isinstance(cell, str):
                cell_lower = cell.lower()
                if "счет" in cell_lower:
                    row_has_account = True
                if "субконто" in cell_lower or "контрагент" in cell_lower:
                    row_has_counterparty = True
        if row_has_account and row_has_counterparty:
            header_row_idx = idx
            break

    if header_row_idx is None:
        raise ValueError("Не найден заголовок с 'Счет' и 'Контрагент' во внутренней ОСВ")

    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for i, cell in enumerate(header_row):
        if pd.isna(cell):
            continue
        cell_str = str(cell).strip().lower()
        if "инн" in cell_str and not ("субконто" in cell_str or "контрагент" in cell_str):
            col_indices['org_inn'] = i
        elif "счет" in cell_str:
            col_indices['account'] = i
        elif "субконто 1.инн" in cell_str or "контрагент" in cell_str:
            col_indices['counterparty'] = i
        elif ("сумма ост. дт" in cell_str or "дебет" in cell_str or
              cell_str.strip() == "дт" or cell_str.strip() == "dt"):
            col_indices['debit'] = i
        elif ("сумма ост. кт" in cell_str or "кредит" in cell_str or
              cell_str.strip() == "кт" or cell_str.strip() == "kt"):
            col_indices['credit'] = i
        elif "дата" in cell_str or "период" in cell_str:
            col_indices['date'] = i

    required = ['account', 'counterparty', 'debit', 'credit']
    for col in required:
        if col not in col_indices:
            raise ValueError(f"Не найдена колонка '{col}' в заголовке внутренней ОСВ")

    start_row = header_row_idx + 1
    if start_row < len(df):
        sample = df.iloc[start_row]
        has_subheader = False
        for cell in sample:
            if pd.notna(cell) and isinstance(cell, str) and ("дебет" in cell.lower() or "кредит" in cell.lower()):
                has_subheader = True
                break
        if has_subheader:
            start_row += 1

    organization_inn = None
    period_date = None
    grouped = defaultdict(lambda: {"debit": Decimal(0), "credit": Decimal(0), "full_codes": []})

    org_inn_idx = col_indices.get('org_inn')
    date_idx = col_indices.get('date')
    account_idx = col_indices['account']
    counterparty_idx = col_indices['counterparty']
    debit_idx = col_indices['debit']
    credit_idx = col_indices['credit']

    for idx in range(start_row, len(df)):
        row = df.iloc[idx]
        account_cell = row[account_idx] if account_idx < len(row) else None
        if pd.isna(account_cell):
            break
        account = str(account_cell).strip()
        if not account:
            continue

        if organization_inn is None and org_inn_idx is not None:
            inn_cell = row[org_inn_idx] if org_inn_idx < len(row) else None
            if pd.notna(inn_cell):
                organization_inn = str(inn_cell).strip()

        if period_date is None and date_idx is not None:
            date_cell = row[date_idx] if date_idx < len(row) else None
            if pd.notna(date_cell):
                try:
                    if isinstance(date_cell, datetime):
                        period_date = date_cell.date()
                    else:
                        period_date = pd.to_datetime(date_cell).date()
                except:
                    pass

        counterparty = row[counterparty_idx] if counterparty_idx < len(row) else None
        if pd.isna(counterparty):
            continue
        counterparty = str(counterparty).strip()
        if counterparty == "":
            continue

        def to_decimal(val):
            if pd.isna(val):
                return Decimal(0)
            if isinstance(val, (int, float)):
                return Decimal(str(val))
            s = str(val).replace(" ", "").replace(",", ".")
            try:
                return Decimal(s)
            except:
                return Decimal(0)

        end_debit = to_decimal(row[debit_idx]) if debit_idx < len(row) else Decimal(0)
        end_credit = to_decimal(row[credit_idx]) if credit_idx < len(row) else Decimal(0)

        main_code = extract_main_account(account)
        key = (main_code, counterparty)
        grouped[key]["debit"] += end_debit
        grouped[key]["credit"] += end_credit
        grouped[key]["full_codes"].append(account)  # сохраняем полный код

    if not grouped:
        # Возвращаем пустые данные без ошибки (внутренняя ОСВ может быть пустой)
        return [], organization_inn, period_date

    data = []
    for (code, counterparty), vals in grouped.items():
        full_code = vals["full_codes"][0] if vals["full_codes"] else code
        data.append({
            "account_code": code,  # основной счет для правил
            "full_account_code": full_code,  # полный счет для деталей
            "counterparty_inn": counterparty,
            "end_debit": vals["debit"],
            "end_credit": vals["credit"]
        })

    return data, organization_inn, period_date