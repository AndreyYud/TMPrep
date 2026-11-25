#!/usr/bin/env python3
"""
Скрипт для загрузки данных из JSON-файла в базу данных SQLite.
Запуск: python load_data.py --file <путь к JSON> [--db <путь к БД>] [--clear]
Если --clear указан, таблицы очищаются перед загрузкой (удаляются все записи).
"""

import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).parent))
from app.core.database import Base
import app.models

def get_engine(db_path):
    if db_path.startswith("sqlite://"):
        db_url = db_path
    else:
        db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False)

def load_data(engine, data, clear=False):
    metadata = MetaData()
    metadata.reflect(bind=engine)
    sorted_tables = metadata.sorted_tables

    if clear:
        print("Очистка таблиц перед загрузкой...")
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = OFF"))
            for table in reversed(sorted_tables):
                table_name = table.name
                if table_name in data:
                    conn.execute(text(f"DELETE FROM {table_name}"))
                    print(f"  Очищена таблица {table_name}")
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.commit()

    with engine.connect() as conn:
        for table in sorted_tables:
            table_name = table.name
            if table_name not in data:
                continue
            records = data[table_name]
            if not records:
                continue
            print(f"Загрузка {len(records)} записей в таблицу {table_name}...")
            try:
                conn.execute(table.insert(), records)
                conn.commit()
            except IntegrityError as e:
                print(f"Ошибка целостности при вставке в таблицу {table_name}: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"Ошибка при вставке в таблицу {table_name}: {e}")
                sys.exit(1)
    print("Загрузка завершена.")

def main():
    parser = argparse.ArgumentParser(description="Загрузка данных из JSON в БД")
    parser.add_argument("--file", required=True, help="Путь к JSON-файлу с данными")
    parser.add_argument("--db", default=str(Path(__file__).parent / "osv.db"), help="Путь к файлу базы данных")
    parser.add_argument("--clear", action="store_true", help="Очищать таблицы перед загрузкой")
    args = parser.parse_args()

    # Проверяем существование файла (дополнительно можно проверить расширение)
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Ошибка: файл {args.file} не найден.")
        sys.exit(1)
    if file_path.suffix.lower() != '.json':
        print("Предупреждение: файл не имеет расширения .json, но загрузка будет продолжена.")

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        print("Файл не содержит данных.")
        sys.exit(0)

    engine = get_engine(args.db)
    # Создаём таблицы, если они ещё не существуют
    Base.metadata.create_all(engine)

    load_data(engine, data, clear=args.clear)

if __name__ == "__main__":
    main()