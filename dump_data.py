#!/usr/bin/env python3
"""
Скрипт для выгрузки данных из базы данных SQLite в JSON-файл.
Запуск: python dump_data.py [--db <путь к БД>] [--tables <таблица1> <таблица2> ...] [--output <имя_файла>]
Если таблицы не указаны, выгружаются все непустые таблицы.
Имя файла по умолчанию: dump_<имя_БД>_<дата-время>.json
Если в --output не указано расширение .json, оно добавляется автоматически.
Если выходной файл уже существует, будет запрошено подтверждение перезаписи.
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, inspect, text

def get_engine(db_path):
    if db_path.startswith("sqlite://"):
        db_url = db_path
    else:
        db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False)

def get_table_names(engine, tables_arg):
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    if tables_arg:
        missing = [t for t in tables_arg if t not in all_tables]
        if missing:
            raise ValueError(f"Таблицы не найдены: {', '.join(missing)}")
        return tables_arg
    else:
        non_empty = []
        with engine.connect() as conn:
            for table in all_tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                if count > 0:
                    non_empty.append(table)
        return non_empty

def dump_table(engine, table_name):
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        stmt = table.select()
        rows = conn.execute(stmt)
        result = []
        for row in rows:
            row_dict = {}
            for key, value in row._mapping.items():
                if hasattr(value, 'isoformat'):
                    row_dict[key] = value.isoformat()
                elif isinstance(value, decimal.Decimal):
                    row_dict[key] = str(value)
                else:
                    row_dict[key] = value
            result.append(row_dict)
        return result

def ensure_json_extension(file_path):
    path = Path(file_path)
    if path.suffix.lower() != '.json':
        return str(path.with_suffix(path.suffix + '.json'))
    return str(path)

def ask_overwrite(file_path):
    """Спрашивает пользователя, перезаписывать ли существующий файл."""
    if not os.path.exists(file_path):
        return True
    while True:
        response = input(f"Файл '{file_path}' уже существует. Перезаписать? (y/N): ").strip().lower()
        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no', ''):
            return False
        else:
            print("Пожалуйста, введите 'y' или 'n'.")

def main():
    parser = argparse.ArgumentParser(description="Выгрузка данных из БД в JSON")
    parser.add_argument("--db", default=str(Path(__file__).parent / "osv.db"), help="Путь к файлу базы данных")
    parser.add_argument("--tables", nargs="*", default=[], help="Список таблиц для выгрузки")
    parser.add_argument("--output", help="Имя выходного JSON-файла (расширение .json добавится автоматически)")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Ошибка: файл базы данных {args.db} не найден.")
        sys.exit(1)

    engine = get_engine(args.db)
    try:
        tables = get_table_names(engine, args.tables)
    except ValueError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if not tables:
        print("Нет таблиц для выгрузки.")
        sys.exit(0)

    print(f"Выгружаемые таблицы: {', '.join(tables)}")
    data = {}
    for table in tables:
        print(f"Чтение таблицы {table}...")
        data[table] = dump_table(engine, table)

    if args.output:
        out_file = ensure_json_extension(args.output)
    else:
        db_name = Path(args.db).stem
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_file = f"dump_{db_name}_{timestamp}.json"

    # Проверяем существование файла и спрашиваем о перезаписи
    if not ask_overwrite(out_file):
        print("Операция отменена пользователем.")
        sys.exit(0)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Данные успешно выгружены в файл: {out_file}")

if __name__ == "__main__":
    import decimal
    main()