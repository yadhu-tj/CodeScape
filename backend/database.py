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
        """Verify the database has the required vector and repository columns."""
        async with self.engine.connect() as connection:
            result = await connection.execute(text("""
                SELECT attribute.attname, pg_catalog.format_type(attribute.atttypid, attribute.atttypmod)
                FROM pg_catalog.pg_attribute AS attribute
                WHERE NOT attribute.attisdropped AND (
                    (attribute.attrelid = pg_catalog.to_regclass('nodes') AND attribute.attname = 'embedding')
                    OR (attribute.attrelid = pg_catalog.to_regclass('repos')
                        AND attribute.attname IN ('source_sha256', 'embedding_status'))
                )
                """))
            columns = dict(result.tuples().all())
        if columns.get("embedding") != "vector(768)" or not {"source_sha256", "embedding_status"} <= columns.keys():
            raise RuntimeError("Required CodeScape schema is missing. Run alembic upgrade head.")

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
