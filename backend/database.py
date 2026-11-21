from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if __package__:
    from .config import Settings
else:
    from config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_async_engine(
            settings.DATABASE_URL.get_secret_value(),
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"timeout": 5},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self) -> None:
        """Verify the extension and embedding column installed by Alembic."""
        async with self.engine.connect() as connection:
            vector_column = await connection.scalar(text("""
                SELECT pg_catalog.format_type(attribute.atttypid, attribute.atttypmod)
                FROM pg_catalog.pg_attribute AS attribute
                WHERE attribute.attrelid = pg_catalog.to_regclass('nodes')
                  AND attribute.attname = 'embedding' AND NOT attribute.attisdropped
                """))
        if vector_column != "vector(768)":
            raise RuntimeError("Expected nodes.embedding vector(768). Apply the Alembic baseline.")

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
