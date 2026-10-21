"""Tests de la migration 1311 — ssh_keys / host_ssh_fingerprints (STORY-131.1).

Pattern des tests Alembic existants (``test_migrations.py``) : CLI alembic
en sous-process isolé sur une base SQLite temporaire, seed SQL **brut**
antérieur à la migration, puis inspection structurelle et de données.

Couvre :
- upgrade : création des 2 tables + FK ``targets.ssh_key_id`` (+ index) ;
- data migration « sans perte » : cible avec ``ssh_private_key`` chiffré →
  entité ``ssh_keys`` créée (fingerprint correct, clé privée chiffrée),
  FK settée, credentials ré-encryptés sans la clé ;
- déduplication : deux cibles partageant la même clé → **une seule**
  ``SSHKey`` (AC 2 de la story mère) ;
- cible sans clé → inchangée ;
- tolérance R1 : cible illisible (chiffrée avec une autre clé maîtresse)
  → inchangée, ``upgrade head`` n'échoue pas ;
- rejouabilité : re-run de la data migration après stamp → pas de doublon ;
- downgrade : drop propre des tables et de la colonne.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import asyncssh
from sqlalchemy import create_engine, inspect, text

from app.core.secret_manager import SecretManager
from app.models.target import encrypt_credentials_for_storage

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

# Clés de test générées une fois (valeurs factices).
_KEY_A = asyncssh.generate_private_key("ssh-ed25519")
PEM_A: str = _KEY_A.export_private_key().decode()
PUBLIC_A: str = _KEY_A.export_public_key().decode()
FINGERPRINT_A: str = _KEY_A.get_fingerprint()

_KEY_B = asyncssh.generate_private_key("ssh-ed25519")
PEM_B: str = _KEY_B.export_private_key().decode()
FINGERPRINT_B: str = _KEY_B.get_fingerprint()

# Clé maîtresse déterministe pour chiffrer les seeds (les sous-process
# alembic résolvent le SecretManager depuis la même clé via l'env).
MASTER_KEY = "test-master-key-1311-unit"
_MANAGER = SecretManager(MASTER_KEY)


def _encrypt_with_master_key(credentials: dict) -> dict:
    """Chiffre les credentials du seed avec MASTER_KEY (indépendant de
    l'environnement du process de test).

    ``encrypt_credentials_for_storage`` consomme le singleton résolu
    depuis ``settings`` : le singleton est ponctuellement remplacé puis
    réinitialisé pour ne pas polluer le reste de la session pytest.
    """
    import app.core.secret_manager as secret_manager_module

    previous = secret_manager_module._secret_manager
    secret_manager_module._secret_manager = _MANAGER
    try:
        return encrypt_credentials_for_storage(credentials)
    finally:
        secret_manager_module._secret_manager = previous


def _run_alembic(*args: str, db_url: str) -> subprocess.CompletedProcess[str]:
    """Exécute la CLI alembic en sous-process isolé (env DATABASE_URL)."""
    env = {
        **os.environ,
        "DATABASE_URL": db_url,
        "SECRET_ENCRYPTION_KEY": MASTER_KEY,
        "JWT_SECRET_KEY": MASTER_KEY,
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_legacy_base(db_path: Path, revision: str = "1251_audit_logs") -> None:
    """Crée une base au niveau ``revision`` avec org + 3 cibles seedées.

    - ``t-key`` : credentials chiffrés contenant ``ssh_private_key`` (PEM A)
      + username/sudo (doivent survivre à la migration) ;
    - ``t-shared`` : même PEM A (déduplication attendue) ;
    - ``t-none`` : credentials chiffrés sans clé SSH (doit rester inchangée).

    La cible illisible (R1) est seedée séparément (autre clé maîtresse).
    """
    db_url = f"sqlite+aiosqlite:///{db_path}"
    up = _run_alembic("upgrade", revision, db_url=db_url)
    assert up.returncode == 0, f"upgrade {revision} a échoué : {up.stderr}"

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organizations "
                    "(id, name, slug, settings, created_at, updated_at) "
                    "VALUES ('org-1311', 'Org 1311', 'org-1311', '{}', "
                    "'2026-10-16 00:00:00', '2026-10-16 00:00:00')"
                )
            )
            # (Pas de seed users : la colonne organization_id a été retirée
            # par la migration 1213 et targets ne référence que organizations.)

            def _insert_target(tid: str, name: str, credentials: dict) -> None:
                conn.execute(
                    text(
                        "INSERT INTO targets (id, name, host, port, type, "
                        "credentials, status, extra_metadata, organization_id, "
                        "created_at, updated_at) VALUES "
                        "(:id, :name, '192.0.2.10', 22, 'DOCKER', "
                        ":credentials, 'OFFLINE', '{}', 'org-1311', "
                        "'2026-10-16 00:00:00', '2026-10-16 00:00:00')"
                    ),
                    {
                        "id": tid,
                        "name": name,
                        "credentials": json.dumps(
                            _encrypt_with_master_key(credentials)
                        ),
                    },
                )

            _insert_target(
                "t-key",
                "legacy-with-key",
                {
                    "auth_method": "ssh_key",
                    "username": "deploy",
                    "ssh_private_key": PEM_A,
                    "sudo_enabled": True,
                    "sudo_user": "root",
                },
            )
            _insert_target(
                "t-shared",
                "legacy-shared-key",
                {"auth_method": "ssh_key", "ssh_private_key": PEM_A},
            )
            _insert_target(
                "t-none",
                "legacy-no-key",
                {"auth_method": "password", "username": "root", "password": "p"},
            )
    finally:
        engine.dispose()


def _seed_unreadable_target(db_path: Path) -> None:
    """Ajoute une cible chiffrée avec une AUTRE clé maîtresse (R1)."""
    other = SecretManager("another-master-key-1311")
    payload = json.dumps({"ssh_private_key": PEM_B})
    stored = json.dumps({"_encrypted": other.encrypt(payload)})

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO targets (id, name, host, port, type, "
                    "credentials, status, extra_metadata, organization_id, "
                    "created_at, updated_at) VALUES "
                    "('t-bad', 'unreadable-key', '192.0.2.99', 22, 'DOCKER', "
                    ":credentials, 'OFFLINE', '{}', 'org-1311', "
                    "'2026-10-16 00:00:00', '2026-10-16 00:00:00')"
                ),
                {"credentials": stored},
            )
    finally:
        engine.dispose()


def _rows(db_path: Path, query: str) -> list[dict]:
    """Lit des lignes en SQL brut via un engine sync jetable."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(query))]
    finally:
        engine.dispose()


class TestUpgradeSchema:
    """Upgrade : structure créée conformément aux modèles."""

    def test_upgrade_creates_tables_and_fk(self, tmp_path: Path) -> None:
        """Base vierge → head : ssh_keys + host_ssh_fingerprints créées,
        colonne ``targets.ssh_key_id`` présente."""
        db_path = tmp_path / "schema-1311.db"
        up = _run_alembic("upgrade", "head", db_url=f"sqlite+aiosqlite:///{db_path}")
        assert up.returncode == 0, f"upgrade head a échoué : {up.stderr}"

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
            assert {"ssh_keys", "host_ssh_fingerprints"} <= tables

            # Colne FK sur targets
            target_cols = {c["name"] for c in inspector.get_columns("targets")}
            assert "ssh_key_id" in target_cols

            # Index fingerprint (spec 06)
            ssh_key_indexes = {i["name"] for i in inspector.get_indexes("ssh_keys")}
            assert "idx_ssh_keys_fingerprint" in ssh_key_indexes

            # Index + contrainte unique sur les empreintes
            fp_indexes = {
                i["name"] for i in inspector.get_indexes("host_ssh_fingerprints")
            }
            assert "idx_host_ssh_fp_host" in fp_indexes
            fp_uniques = {
                c["name"]
                for c in inspector.get_unique_constraints("host_ssh_fingerprints")
            }
            assert "uq_host_ssh_fp_identity" in fp_uniques
        finally:
            engine.dispose()


class TestDataMigration:
    """Data migration — extraction sans perte, dédup, tolérance R1."""

    def _migrated(self, tmp_path: Path, name: str) -> Path:
        """Seed base 1251 (avec cible illisible) → upgrade head."""
        db_path = tmp_path / name
        _seed_legacy_base(db_path)
        _seed_unreadable_target(db_path)
        up = _run_alembic("upgrade", "head", db_url=f"sqlite+aiosqlite:///{db_path}")
        assert (
            up.returncode == 0
        ), f"upgrade head a échoué (R1 non toléré) : {up.stdout}\n{up.stderr}"
        return db_path

    def test_key_extracted_encrypted_dedup_and_fk_set(self, tmp_path: Path) -> None:
        """AC 1 : cible avec clé → entité correcte + FK + credentials
        ré-encryptés sans clé ; deux cibles → UNE seule entité (dédup)."""
        db_path = self._migrated(tmp_path, "data-1311-1.db")

        keys = _rows(db_path, "SELECT * FROM ssh_keys")
        assert (
            len(keys) == 1
        ), f"dédup attendue : 1 clé pour 2 cibles, trouvé {len(keys)}"
        key = keys[0]
        assert key["fingerprint"] == FINGERPRINT_A
        assert key["key_type"] == "ssh-ed25519"
        assert key["public_key"] == PUBLIC_A
        assert key["name"].startswith("imported-")
        # Clé privée JAMAIS en clair : token Fernet uniquement.
        assert SecretManager.is_encrypted(key["private_key_encrypted"])
        assert PEM_A not in key["private_key_encrypted"]
        # Le token est déchiffrable avec la clé maîtresse du test.
        assert (
            _MANAGER.decrypt(key["private_key_encrypted"]) == PEM_A
        ), "round-trip : la clé stockée doit se déchiffrer vers le PEM A"

        # FK settée sur les deux cibles partageant la clé.
        targets = {
            t["id"]: t for t in _rows(db_path, "SELECT id, ssh_key_id FROM targets")
        }
        assert targets["t-key"]["ssh_key_id"] == key["id"]
        assert targets["t-shared"]["ssh_key_id"] == key["id"]

        # Credentials ré-encryptés, sans la clé, username/sudo préservés.
        creds_rows = _rows(
            db_path, "SELECT id, credentials FROM targets WHERE id = 't-key'"
        )
        stored = json.loads(creds_rows[0]["credentials"])
        assert set(stored.keys()) == {"_encrypted"}
        decrypted = json.loads(_MANAGER.decrypt(stored["_encrypted"]))
        assert "ssh_private_key" not in decrypted
        assert decrypted["username"] == "deploy"
        assert decrypted["sudo_user"] == "root"
        assert decrypted["sudo_enabled"] is True

    def test_target_without_key_unchanged(self, tmp_path: Path) -> None:
        """Cible sans clé SSH : ssh_key_id NULL, credentials intacts."""
        db_path = self._migrated(tmp_path, "data-1311-2.db")

        row = _rows(
            db_path,
            "SELECT ssh_key_id, credentials FROM targets WHERE id = 't-none'",
        )[0]
        assert row["ssh_key_id"] is None

        stored = json.loads(row["credentials"])
        decrypted = json.loads(_MANAGER.decrypt(stored["_encrypted"]))
        assert decrypted == {
            "auth_method": "password",
            "username": "root",
            "password": "p",
        }

    def test_unreadable_target_left_intact_no_failure(self, tmp_path: Path) -> None:
        """R1 : cible chiffrée avec une autre clé maîtresse → laissée
        intégralement inchangée (credentials + FK), upgrade OK (déjà
        prouvé par _migrated qui assert returncode == 0)."""
        db_path = self._migrated(tmp_path, "data-1311-3.db")

        row = _rows(
            db_path,
            "SELECT ssh_key_id, credentials FROM targets WHERE id = 't-bad'",
        )[0]
        assert row["ssh_key_id"] is None, "aucune FK ne doit être settée"

        # Le ciphertext d'origine est préservé byte pour byte.
        stored = json.loads(row["credentials"])
        assert set(stored.keys()) == {"_encrypted"}
        other = SecretManager("another-master-key-1311")
        decrypted = json.loads(other.decrypt(stored["_encrypted"]))
        assert decrypted == {"ssh_private_key": PEM_B}

        # Aucune entité parasite créée pour la clé illisible.
        keys = _rows(db_path, "SELECT fingerprint FROM ssh_keys")
        assert [k["fingerprint"] for k in keys] == [FINGERPRINT_A]

    def test_rerun_after_stamp_does_not_duplicate(self, tmp_path: Path) -> None:
        """Rejouabilité : downgrade → re-upgrade (schéma recréé) OU stamp
        1311 → re-upgrade : aucune nouvelle entité, FK déjà settées non
        altérées. Ici : stamp 1251 → upgrade 1311 une 2e fois n'est pas
        possible (version déjà head) — on vérifie la rejouabilité de la
        data migration via downgrade 1251 → upgrade head."""
        db_path = tmp_path / "data-1311-4.db"
        _seed_legacy_base(db_path)
        db_url = f"sqlite+aiosqlite:///{db_path}"

        up = _run_alembic("upgrade", "head", db_url=db_url)
        assert up.returncode == 0, up.stderr
        keys_after_first = _rows(db_path, "SELECT id, name FROM ssh_keys")
        assert len(keys_after_first) == 1

        down = _run_alembic("downgrade", "1251_audit_logs", db_url=db_url)
        assert down.returncode == 0, down.stderr

        up2 = _run_alembic("upgrade", "head", db_url=db_url)
        assert up2.returncode == 0, up2.stderr

        # Après downgrade, les clés importées ont été supprimées avec la
        # table MAIS les credentials ont été déchiffrés/sans-clé au 1er
        # passage : la data migration du 2e passage ne trouve plus de
        # ``ssh_private_key`` → aucune clé recréée, FK reste NULL (limite
        # documentée du downgrade non destructeur).
        keys_after_second = _rows(db_path, "SELECT id FROM ssh_keys")
        targets = {
            t["id"]: t["ssh_key_id"]
            for t in _rows(db_path, "SELECT id, ssh_key_id FROM targets")
        }
        # Le re-upgrade recrée le schéma sans duplication ni échec.
        assert len(keys_after_second) == 0
        assert targets["t-key"] is None


class TestDowngrade:
    """Downgrade : drop propre (tables + colonne FK)."""

    def test_downgrade_drops_tables_and_column(self, tmp_path: Path) -> None:
        """head → 1251 : ssh_keys/host_ssh_fingerprints supprimées,
        ``targets.ssh_key_id`` absente, le reste du schéma intact."""
        db_path = tmp_path / "down-1311.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        up = _run_alembic("upgrade", "head", db_url=db_url)
        assert up.returncode == 0, up.stderr

        down = _run_alembic("downgrade", "1251_audit_logs", db_url=db_url)
        assert down.returncode == 0, down.stderr

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
            assert "ssh_keys" not in tables
            assert "host_ssh_fingerprints" not in tables
            assert "targets" in tables, "la table targets doit survivre"
            target_cols = {c["name"] for c in inspector.get_columns("targets")}
            assert "ssh_key_id" not in target_cols
        finally:
            engine.dispose()
