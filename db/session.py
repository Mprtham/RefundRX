from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from db.models import Base

# asyncpg rejects libpq-only query params that Neon connection strings carry.
_LIBPQ_ONLY = {"sslmode", "channel_binding"}


def normalize_url(url: str) -> tuple[str, dict]:
    """Turn a Neon/libpq URL into an asyncpg URL plus connect_args."""
    connect_args: dict = {}
    if url.startswith(("postgres://", "postgresql://")):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        if query.get("sslmode") in {"require", "verify-ca", "verify-full"}:
            connect_args["ssl"] = True
        query = {k: v for k, v in query.items() if k not in _LIBPQ_ONLY}
        url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url, connect_args


def make_engine(url: str) -> AsyncEngine:
    url, connect_args = normalize_url(url)
    engine = create_async_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        _sqlite_begin_immediate(engine)
    return engine


def _sqlite_begin_immediate(engine: AsyncEngine) -> None:
    """SQLite ignores SELECT ... FOR UPDATE, and a deferred transaction that
    reads the chain head and then writes fails with "database is locked" when it
    tries to upgrade its lock. Taking the write lock at BEGIN serializes audit
    appends the way FOR UPDATE does on Postgres (SQLAlchemy's documented recipe)."""

    @event.listens_for(engine.sync_engine, "connect")
    def _connect(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
