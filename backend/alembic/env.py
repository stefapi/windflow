"""
Environment Alembic async pour WindFlow (STORY-120.1).

Engine construit depuis ``settings.database_url`` (SQLite/aiosqlite ou
PostgreSQL/asyncpg) — jamais en dur, jamais loggée (l'URL peut contenir
le mot de passe PostgreSQL). L'URL de ``alembic.ini`` est volontairement
vide : seule la configuration applicative fait foi.
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Résolution du package ``backend.app`` quel que soit le répertoire de
# travail : la racine du repo (parent de ``backend/``) est ajoutée au
# sys.path — cohérent avec ``python -m uvicorn backend.main:app``.
BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = BACKEND_DIR.parent
for _path in (str(BACKEND_DIR), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app import models  # noqa: E402,F401  # importe tous les modèles (autogenerate)

# La config Alembic (alembic.ini) — fournie par la CLI ou l'API Python.
config = context.config

# Logging depuis alembic.ini (format console), si le fichier le demande.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Métadonnées cibles de l'autogenerate — TOUS les modèles via models.
target_metadata = Base.metadata

# L'URL DB vient exclusivement des settings applicatifs (variable
# d'environnement DATABASE_URL ou défaut SQLite) — surcharge toute URL
# statique éventuellement présente dans alembic.ini (sécurité : aucun
# secret ne doit vivre dans le fichier ini).
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Mode offline : génère le SQL sans connexion DB réelle.

    L'URL n'est PAS passée à ``engine_from_config`` : le mode offline
    n'émet que du DDL textuel (``--sql``), l'URL sert uniquement au
    dialecte pour le rendu. Aucun log de l'URL (peut contenir un secret).
    """
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=settings.database_url.startswith("sqlite"),
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Exécute les migrations sur une connexion sync sous-jacente."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite ne supporte pas ALTER la plupart des colonnes : le mode
        # batch (recreate table) rend les migrations portables.
        render_as_batch=settings.database_url.startswith("sqlite"),
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Crée un engine async et exécute les migrations dessus."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Mode online : exécute les migrations via l'engine async."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
