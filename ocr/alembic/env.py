import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from dotenv import load_dotenv
import asyncio
load_dotenv()

# Import your Base and models
from core.database import Base
from models.pdf import Document  # noqa: F401

# this is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging. This line sets up loggers basically.
fileConfig(config.config_file_name)

# Get the database URL from the environment variable
db_url = os.getenv("OCR_SERVER_DATABASE_URL")

if db_url is None:
    raise ValueError("OCR_SERVER_DATABASE_URL environment variable is not set")

# Convert to async URL and set in Alembic config
if db_url.startswith("postgresql://"):
    async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
elif db_url.startswith("postgres://"):
    async_db_url = db_url.replace("postgres://", "postgresql+asyncpg://")
else:
    async_db_url = db_url

config.set_main_option("sqlalchemy.url", async_db_url)

# Provide the target metadata for Alembic migrations. This points to the metadata of your models.
target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    def do_run_migrations(connection):
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
