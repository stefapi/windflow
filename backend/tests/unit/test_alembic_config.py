"""Tests de l'infrastructure Alembic (STORY-120.1).

Vérifie :
- le ``alembic.ini`` racine est parsable et pointe vers ``backend/alembic/`` ;
- ``env.py`` ne loggue jamais l'URL DB (qui peut contenir le mot de
  passe PostgreSQL) ;
- la migration baseline crée exactement les tables de ``Base.metadata`` ;
- le scénario AC 1 : base existante (create_all) → ``stamp baseline`` →
  ``upgrade head`` no-op → ``alembic check`` sans diff.
"""

import os
import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.database import Base
from app import models  # noqa: F401  # enregistre tous les modèles

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
SCRIPT_LOCATION = REPO_ROOT / "backend" / "alembic"

# Tables attendues : exactement celles des ~10 modèles ORM.
EXPECTED_TABLES = {
    "users",
    "organizations",
    "targets",
    "stacks",
    "stack_versions",
    "deployments",
    "plugins",
    "plugin_hook_logs",
    "scheduled_tasks",
    "target_capabilities",
}


def _run_alembic(*args: str, db_url: str) -> subprocess.CompletedProcess[str]:
    """Exécute la CLI alembic dans un sous-process isolé (env DATABASE_URL)."""
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestAlembicIni:
    """test_alembic_ini_resolves_script_location."""

    def test_alembic_ini_resolves_script_location(self) -> None:
        """L'alembic.ini racine est parsable et script_location existe."""
        assert ALEMBIC_INI.is_file(), "alembic.ini manquant à la racine du repo"

        parser = ConfigParser()
        read = parser.read(ALEMBIC_INI)
        assert read, "alembic.ini illisible"

        script_location = parser.get("alembic", "script_location")
        assert script_location, "script_location vide"

        resolved = (REPO_ROOT / script_location).resolve()
        assert resolved == SCRIPT_LOCATION.resolve()
        assert resolved.is_dir(), f"backend/alembic/ introuvable : {resolved}"
        assert (resolved / "env.py").is_file(), "env.py manquant"
        assert (SCRIPT_LOCATION / "versions").is_dir(), "versions/ manquant"

    def test_alembic_ini_contains_no_secret(self) -> None:
        """Sécurité : sqlalchemy.url reste vide dans alembic.ini."""
        parser = ConfigParser()
        parser.read(ALEMBIC_INI)
        url = parser.get("alembic", "sqlalchemy.url", fallback="")
        assert url.strip() == "", "sqlalchemy.url doit rester vide (aucun secret)"


class TestEnvDoesNotLogDatabaseUrl:
    """test_env_does_not_log_database_url."""

    def test_env_does_not_log_database_url(self, tmp_path: Path) -> None:
        """L'URL DB (avec credentials en variante PostgreSQL) n'apparaît
        dans aucun log après exécution d'env.py.

        Le mode offline (``--sql``) exécute réellement ``env.py`` (branche
        ``run_migrations_offline``) avec le dialecte PostgreSQL **sans
        connexion réseau** : tout le pipeline est exercé et l'on vérifie
        que le mot de passe n'apparaît ni dans stdout (DDL généré) ni dans
        stderr (logs alembic).
        """
        db_path = tmp_path / "nolog.db"

        # Variante SQLite : URL avec query-param secret — exécution online
        # complète, le secret ne doit fuir dans aucune sortie.
        sqlite_url = f"sqlite+aiosqlite:///{db_path}?secret=S3cret-P4ssw0rd"
        result = _run_alembic("upgrade", "head", db_url=sqlite_url)
        assert result.returncode == 0, (
            f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "S3cret-P4ssw0rd" not in combined, (
            "L'URL DB (avec secret) fuit dans les sorties de la CLI alembic"
        )

        # Variante PostgreSQL : mode offline (--sql) exécute env.py avec le
        # dialecte asyncpg/PostgreSQL et un mot de passe dans l'URL, sans
        # nécessiter de serveur réel.
        pg_url = "postgresql+asyncpg://windflow:S3cret-P4ssw0rd@localhost:5432/windflow"
        result = _run_alembic("upgrade", "base:head", "--sql", db_url=pg_url)
        assert result.returncode == 0, (
            f"upgrade --sql (offline PostgreSQL) a échoué :\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "S3cret-P4ssw0rd" not in combined, (
            "Le mot de passe PostgreSQL est apparu dans les logs/DDL générés"
        )
        # Le DDL offline PostgreSQL contient bien les CREATE TABLE attendus :
        # preuve que env.py a traité la variante PostgreSQL de bout en bout.
        assert "CREATE TABLE organizations" in result.stdout


class TestBaselineCreatesAllModelTables:
    """test_baseline_creates_all_model_tables."""

    def test_baseline_creates_all_model_tables(self, tmp_path: Path) -> None:
        """alembic upgrade head sur base SQLite temporaire → l'inspection
        révèle exactement les tables de Base.metadata (ni plus, ni moins)."""
        db_path = tmp_path / "baseline.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        result = _run_alembic("upgrade", "head", db_url=db_url)
        assert result.returncode == 0, (
            f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            db_tables = set(inspector.get_table_names())
        finally:
            engine.dispose()

        # alembic_version est créée par Alembic lui-même : attendue en plus.
        assert db_tables == EXPECTED_TABLES | {"alembic_version"}, (
            f"Tables observées : {sorted(db_tables)}"
        )
        assert db_tables == set(Base.metadata.tables) | {"alembic_version"}, (
            "La baseline diverge de Base.metadata : "
            f"{db_tables ^ (set(Base.metadata.tables) | {'alembic_version'})}"
        )


class TestExistingDatabaseStampScenario:
    """Scénario AC 1 : base existante (create_all) → stamp → no-op → check."""

    def test_stamp_then_upgrade_is_noop_and_check_clean(self, tmp_path: Path) -> None:
        """Sur une base créée par create_all : stamp baseline → upgrade head
        no-op → alembic check sans diff (aucune recréation/altération)."""
        db_path = tmp_path / "existing.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # 1. Simule la base existante : create_all via un engine sync
        #    (équivalent SQLite du create_all async de database.py).
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        before = set(inspect(sync_engine).get_table_names())
        sync_engine.dispose()
        assert EXPECTED_TABLES <= before, "create_all n'a pas créé les tables modèles"

        # 2. stamp baseline — marque la base comme étant au niveau baseline
        result = _run_alembic("stamp", "baseline", db_url=db_url)
        assert result.returncode == 0, (
            f"stamp a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        # 3. upgrade head → no-op (déjà à head), aucune table altérée
        result = _run_alembic("upgrade", "head", db_url=db_url)
        assert result.returncode == 0, (
            f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "Running upgrade" not in result.stdout, (
            "upgrade head n'a pas été un no-op après stamp baseline"
        )

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            after = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        assert before | {"alembic_version"} == after, (
            "Le schéma a été modifié par upgrade head après stamp (non-no-op)"
        )

        # 4. alembic check → aucun diff (commande échoue (rc=255) si diff
        #    détecté, rc=0 si propre).
        result = _run_alembic("check", db_url=db_url)
        assert result.returncode == 0, (
            f"alembic check a détecté un diff :\n{result.stdout}\n{result.stderr}"
        )
        assert "No new upgrade operations detected" in result.stdout


class TestDowngrade:
    """Complément baseline : downgrade complet fonctionnel."""

    def test_downgrade_base_drops_all_tables(self, tmp_path: Path) -> None:
        """upgrade head puis downgrade base → toutes les tables modèles
        sont supprimées (downgrade complet implémenté)."""
        db_path = tmp_path / "downgrade.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        up = _run_alembic("upgrade", "head", db_url=db_url)
        assert up.returncode == 0, up.stderr

        down = _run_alembic("downgrade", "base", db_url=db_url)
        assert down.returncode == 0, down.stderr

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            remaining = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        assert remaining == {"alembic_version"}, (
            f"Tables résiduelles après downgrade base : {sorted(remaining)}"
        )


@pytest.mark.unit
class TestSanityMarker:
    """Marquage unit standard du projet (cohérence conventions)."""

    def test_expected_tables_match_metadata(self) -> None:
        """La liste attendue correspond exactement à Base.metadata."""
        assert EXPECTED_TABLES == set(Base.metadata.tables)
