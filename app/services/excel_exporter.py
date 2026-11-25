from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from decimal import Decimal
from typing import Dict, Any, List


def export_consolidated_balance_to_excel(data: Dict[str, Any]) -> BytesIO:
    """
    Генерирует Excel-файл с консолидированным балансом.
    Принимает данные от build_consolidated_balance_for_orgs.
    Возвращает BytesIO с файлом.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Консолидированный баланс"

    # Стили
    bold_font = Font(bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center")  # без wrap для чисел
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    # Заливки
    fill_type = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")      # синий
    fill_section = PatternFill(start_color="E9ECEF", end_color="E9ECEF", fill_type="solid")   # светло-серый
    fill_subsection = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid") # очень светлый серый
    fill_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    organizations = data["organizations"]
    org_names = data["organization_names"]
    skipped = data.get("skipped_organizations", [])
    period_date = data["period_date"]
    rows_data = data["rows"]

    # Заголовок отчёта
    ws.merge_cells(f'A1:{get_column_letter(2 + len(organizations))}1')
    ws['A1'] = "Консолидированный управленческий баланс"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = center_align

    # Информация об организациях и дате
    row = 2
    orgs_str = ", ".join(org_names)
    ws[f'A{row}'] = f"Организации: {orgs_str}"
    ws[f'A{row}'].font = bold_font
    if skipped:
        ws[f'A{row+1}'] = f"Пропущены (нет данных): {', '.join(skipped)}"
        row += 1
    row += 1
    ws[f'A{row}'] = f"Дата периода: {period_date}"
    ws[f'A{row}'].font = bold_font
    row += 2

    # Заголовки колонок
    headers = ["Показатель", "Итого"] + org_names
    header_row = row
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = bold_font
        cell.alignment = center_align
        cell.border = thin_border
        cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    row += 1

    # Запись данных
    for item in rows_data:
        if item["type"] == "type_total":
            type_label = "Активы ↓" if item["is_active"] else "Пассивы ↓"
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
            cell = ws.cell(row=row, column=1, value=type_label)
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.alignment = center_align
            cell.fill = fill_type
            cell.border = thin_border
            row += 1
            continue

        # Определяем стиль строки
        if item["type"] == "section_total":
            label = item["section"]
            indent = 0
            bg_fill = fill_section
            font = Font(bold=True)
        elif item["type"] == "subsection_total":
            label = item["subsection"]
            indent = 1
            bg_fill = fill_subsection
            font = Font(bold=True)
        else:
            label = item["item"]
            indent = 2 if item.get("subsection") else 1
            bg_fill = fill_white
            font = Font()

        # Первая колонка – показатель с отступом
        cell = ws.cell(row=row, column=1, value=("    " * indent) + label)
        cell.font = font
        cell.alignment = left_align
        cell.border = thin_border
        cell.fill = bg_fill

        # Итого
        val = float(item["total"]) if isinstance(item["total"], Decimal) else item["total"]
        cell = ws.cell(row=row, column=2, value=val)
        cell.font = font
        cell.alignment = right_align
        cell.number_format = '#,##0.00'
        cell.border = thin_border
        cell.fill = bg_fill

        # По организациям
        for col_idx, org_inn in enumerate(organizations, start=3):
            val = item.get("org_values", {}).get(org_inn, 0)
            val = float(val) if isinstance(val, Decimal) else val
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.font = font
            cell.alignment = right_align
            cell.number_format = '#,##0.00'
            cell.border = thin_border
            cell.fill = bg_fill

        row += 1

    # Проверка баланса (отдельный блок)
    total_assets = sum(float(item["total"]) for item in rows_data if item["type"] == "type_total" and item["is_active"])
    total_liabilities = sum(float(item["total"]) for item in rows_data if item["type"] == "type_total" and not item["is_active"])
    is_balanced = abs(total_assets - total_liabilities) < 0.01
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
    cell = ws.cell(row=row, column=1, value=f"Проверка баланса: Активы = Пассивы {'✅' if is_balanced else '❌'} (Активы: {total_assets:,.2f}, Пассивы: {total_liabilities:,.2f})")
    cell.font = Font(bold=True, color="FFFFFF" if not is_balanced else "000000")
    cell.alignment = center_align
    cell.fill = PatternFill(start_color="D4EDDA" if is_balanced else "F8D7DA", end_color="D4EDDA" if is_balanced else "F8D7DA", fill_type="solid")
    cell.border = thin_border

    # Фиксированная ширина колонок
    # Первая колонка (показатели) – широкая
    ws.column_dimensions['A'].width = 40
    # Остальные колонки – 16.0
    for col_idx in range(2, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 16.0

    # Сохраняем в BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_internal_balance_to_excel(data: Dict[str, Any]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Внутренние взаиморасчеты"

    bold_font = Font(bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

    fill_type = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
    fill_section = PatternFill(start_color="E9ECEF", end_color="E9ECEF", fill_type="solid")
    fill_subsection = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
    fill_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    organizations = data["organizations"]
    org_names = data["organization_names"]
    skipped = data.get("skipped_organizations", [])
    period_date = data["period_date"]
    rows_data = data["rows"]

    ws.merge_cells(f'A1:{get_column_letter(3 + len(organizations))}1')
    ws['A1'] = "Сводный баланс внутренних взаиморасчетов"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = center_align

    row = 2
    orgs_str = ", ".join(org_names)
    ws[f'A{row}'] = f"Организации: {orgs_str}"
    ws[f'A{row}'].font = bold_font
    if skipped:
        ws[f'A{row+1}'] = f"Пропущены (нет данных): {', '.join(skipped)}"
        row += 1
    row += 1
    ws[f'A{row}'] = f"Дата периода: {period_date}"
    ws[f'A{row}'].font = bold_font
    row += 2

    headers = ["Показатель", "Контрагент", "Итого"] + org_names
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = bold_font
        cell.alignment = center_align
        cell.border = thin_border
        cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    row += 1

    for item in rows_data:
        if item["type"] == "type_total":
            type_label = "Активы ↓" if item["is_active"] else "Пассивы ↓"
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
            cell = ws.cell(row=row, column=1, value=type_label)
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.alignment = center_align
            cell.fill = fill_type
            cell.border = thin_border
            row += 1
            label = "Итого по типу"
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            cell = ws.cell(row=row, column=1, value=label)
            cell.font = bold_font
            cell.alignment = left_align
            cell.border = thin_border
            cell.fill = fill_type
            val = float(item["total"]) if isinstance(item["total"], Decimal) else item["total"]
            cell = ws.cell(row=row, column=3, value=val)
            cell.font = bold_font
            cell.alignment = right_align
            cell.number_format = '#,##0.00'
            cell.border = thin_border
            cell.fill = fill_type
            for col_idx, org_inn in enumerate(organizations, start=4):
                val = item.get("org_values", {}).get(org_inn, 0)
                val = float(val) if isinstance(val, Decimal) else val
                cell = ws.cell(row=row, column=col_idx, value=val)
                cell.font = bold_font
                cell.alignment = right_align
                cell.number_format = '#,##0.00'
                cell.border = thin_border
                cell.fill = fill_type
            row += 1
            continue

        if item["type"] == "section_total":
            label = f"Итого по разделу: {item['section']}"
            indent = 0
            bg_fill = fill_section
            font = Font(bold=True)
        elif item["type"] == "subsection_total":
            label = f"Итого по подразделу: {item['subsection']}"
            indent = 1
            bg_fill = fill_subsection
            font = Font(bold=True)
        else:
            label = item["item"]
            indent = 2 if item.get("subsection") else 1
            bg_fill = fill_white
            font = Font()

        counterparty = item.get("counterparty_name") or item.get("counterparty_inn") or ""

        cell = ws.cell(row=row, column=1, value=("    " * indent) + label)
        cell.font = font
        cell.alignment = left_align
        cell.border = thin_border
        cell.fill = bg_fill

        cell = ws.cell(row=row, column=2, value=counterparty)
        cell.font = font
        cell.alignment = left_align
        cell.border = thin_border
        cell.fill = bg_fill

        val = float(item["total"]) if isinstance(item["total"], Decimal) else item["total"]
        cell = ws.cell(row=row, column=3, value=val)
        cell.font = font
        cell.alignment = right_align
        cell.number_format = '#,##0.00'
        cell.border = thin_border
        cell.fill = bg_fill

        for col_idx, org_inn in enumerate(organizations, start=4):
            val = item.get("org_values", {}).get(org_inn, 0)
            val = float(val) if isinstance(val, Decimal) else val
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.font = font
            cell.alignment = right_align
            cell.number_format = '#,##0.00'
            cell.border = thin_border
            cell.fill = bg_fill

        row += 1

    total_assets = sum(float(item["total"]) for item in rows_data if item["type"] == "type_total" and item["is_active"])
    total_liabilities = sum(float(item["total"]) for item in rows_data if item["type"] == "type_total" and not item["is_active"])
    is_balanced = abs(total_assets - total_liabilities) < 0.01
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
    cell = ws.cell(row=row, column=1, value=f"Проверка: Активы = Пассивы {'✅' if is_balanced else '❌'} (Активы: {total_assets:,.2f}, Пассивы: {total_liabilities:,.2f})")
    cell.font = Font(bold=True, color="FFFFFF" if not is_balanced else "000000")
    cell.alignment = center_align
    cell.fill = PatternFill(start_color="D4EDDA" if is_balanced else "F8D7DA", end_color="D4EDDA" if is_balanced else "F8D7DA", fill_type="solid")
    cell.border = thin_border

    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 30
    for col_idx in range(3, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 16

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output