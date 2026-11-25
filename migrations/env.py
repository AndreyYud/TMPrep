import asyncio
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from alembic import context

# Импортируем вашу базу и модели
from app.core.config import settings
from app.core.database import Base
from app.models import *  # Убедитесь, что все модели загружены

# Это объект конфигурации Alembic
config = context.config

# Интерпретируем файл конфигурации для логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные ваших моделей
target_metadata = Base.metadata

# Используем синхронный URL (убираем "+aiosqlite")
def get_sync_url():
    url = settings.DATABASE_URL
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://")
    return url

def run_migrations_offline() -> None:
    """Запуск миграций в офлайн-режиме."""
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Запуск миграций в онлайн-режиме (синхронный)."""
    # Используем синхронный движок
    sync_url = get_sync_url()
    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Можно добавить compare_type=True для сравнения типов колонок
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()