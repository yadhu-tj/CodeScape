import asyncio

from alembic import context

from config import Settings
from database import Database
from models import Base


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    database = Database(Settings())
    try:
        async with database.engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await database.dispose()


if context.is_offline_mode():
    context.configure(dialect_name="postgresql", target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
