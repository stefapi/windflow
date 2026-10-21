"""Tables ssh_keys / host_ssh_fingerprints + data migration des clés SSH (STORY-131.1)

Migration du volet modèles & migrations de STORY-131 (P1-9, spec 06 §
Entités d'accès distant (SSH), spec 15 § Hosts distants) :

1. **Schéma additif** :

   - ``ssh_keys`` — clés SSH réutilisables : clé privée **chiffrée au
     repos** (token Fernet via le SecretManager, STORY-103) ; ``fingerprint``
     ``SHA256:<base64nopad>`` indexé (déduplication / identification) ;
   - ``host_ssh_fingerprints`` — empreintes known_hosts (socle TOFU,
     consommé par STORY-131.2/131.3) ; contrainte UNIQUE
     ``(host_id, hostname, port, key_type)`` (une empreinte par serveur et
     par algorithme). Arbitrage F3 : ``host_id`` référence ``targets.id``
     (l'entité « Host » des specs n'existe pas en base — renommage STORY-166) ;
   - ``targets.ssh_key_id`` — FK nullable ``ssh_keys.id`` ``ON DELETE SET
     NULL`` : N cibles référencent la même clé (AC 2 de la story mère).

2. **Data migration « sans perte »** (AC 1) : extraction des
   ``credentials.ssh_private_key`` existants (déchiffrés via les helpers
   STORY-103.2 de ``app.models.target``) vers des entités ``ssh_keys``
   **dédupliquées par fingerprint**, puis ré-encryption des credentials
   sans la clé privée (username/password/sudo_* inchangés).

   Tolérance R1 : tout échec (clé maîtresse changée → déchiffrement
   impossible, PEM invalide, passphrase manquante) laisse la cible
   **intégralement inchangée** avec un simple ``logger.warning`` — le
   ``upgrade head`` ne doit **jamais** échouer. Aucune donnée sensible
   n'est loggée (identifiant de ligne uniquement).

   L'import applicatif (SecretManager, helpers, asyncssh) est **paresseux**
   et exécuté uniquement en mode online : le mode offline (``--sql``)
   n'a ni connexion ni données à migrer.

3. **Downgrade non destructif** : drop des tables et de la colonne
   ``targets.ssh_key_id``. Les clés importées ne sont **pas** ré-inlinées
   dans les credentials (la clé publique exportée et la suppression du
   champ d'origine rendent la reconstruction non réversible) — documenté
   comme limite assumée.

Revision ID: 1311_ssh_keys
Revises: 1251_audit_logs
Create Date: 2026-10-16 21:00:00.000000+00:00

"""

import logging
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import context as alembic_context
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "1311_ssh_keys"
down_revision: Union[str, None] = "1251_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _migrate_ssh_private_keys_to_entities() -> None:
    """Extrait les ``ssh_private_key`` des cibles vers des ``ssh_keys``.

    Data migration tolérante (R1) : chaque cible est traitée
    indépendamment — en cas d'échec (déchiffrement impossible, PEM
    invalide), la cible est laissée intacte et un warning sans donnée
    sensible est loggé.
    """
    if alembic_context.is_offline_mode():
        # Génération SQL hors ligne : aucune base connectée, aucune
        # donnée à migrer (DDL seul).
        return

    # Imports applicatifs paresseux : le contexte Alembic (env.py) a déjà
    # résolu ``backend/`` dans sys.path et importé ``app.models``.
    import asyncssh

    from app.core.secret_manager import get_secret_manager
    from app.models.target import (
        decrypt_credentials_from_storage,
        encrypt_credentials_for_storage,
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    targets_table = sa.Table("targets", metadata, autoload_with=bind)
    ssh_keys_table = sa.Table("ssh_keys", metadata, autoload_with=bind)

    # Déduplication par fingerprint (AC 2 de la story mère) : les lignes
    # préexistantes comptent (rejouabilité après ``alembic stamp``).
    key_id_by_fingerprint: dict[str, str] = {
        row.fingerprint: row.id
        for row in bind.execute(
            sa.select(ssh_keys_table.c.fingerprint, ssh_keys_table.c.id)
        ).fetchall()
    }
    used_names: set[str] = set(
        bind.execute(sa.select(ssh_keys_table.c.name)).scalars().all()
    )

    now = datetime.now(timezone.utc)
    manager = get_secret_manager()

    rows = bind.execute(
        sa.select(targets_table.c.id, targets_table.c.credentials)
    ).fetchall()
    for row in rows:
        target_id = row.id
        stored = row.credentials
        if not isinstance(stored, dict) or not stored:
            continue
        try:
            credentials = decrypt_credentials_from_storage(stored)
            private_key = credentials.get("ssh_private_key")
            if not isinstance(private_key, str) or not private_key:
                # Aucune clé SSH à migrer : la cible reste inchangée.
                continue

            passphrase = credentials.get("ssh_private_key_passphrase")
            key = asyncssh.import_private_key(
                private_key,
                passphrase if isinstance(passphrase, str) and passphrase else None,
            )
            fingerprint = key.get_fingerprint()
            algorithm = key.algorithm
            key_type = (
                algorithm.decode("ascii", "replace")
                if isinstance(algorithm, bytes)
                else str(algorithm)
            )
            public_key = key.export_public_key().decode("ascii", "replace")

            if fingerprint not in key_id_by_fingerprint:
                fingerprint_tail = fingerprint.split(":", 1)[-1][:8]
                name = f"imported-{fingerprint_tail}"
                suffix = 2
                while name in used_names:
                    name = f"imported-{fingerprint_tail}-{suffix}"
                    suffix += 1
                new_id = str(uuid4())
                bind.execute(
                    ssh_keys_table.insert().values(
                        id=new_id,
                        name=name,
                        key_type=key_type,
                        public_key=public_key,
                        # Jamais de clé privée en clair en colonne : token
                        # Fernet exclusivement (checklist sécurité rules 40).
                        private_key_encrypted=manager.encrypt(private_key),
                        fingerprint=fingerprint,
                        created_at=now,
                    )
                )
                key_id_by_fingerprint[fingerprint] = new_id
                used_names.add(name)

            # Retrait de la clé (et de sa passphrase) des credentials puis
            # ré-encryption — username/password/sudo_* inchangés.
            credentials.pop("ssh_private_key", None)
            credentials.pop("ssh_private_key_passphrase", None)
            bind.execute(
                targets_table.update()
                .where(targets_table.c.id == target_id)
                .values(
                    ssh_key_id=key_id_by_fingerprint[fingerprint],
                    credentials=encrypt_credentials_for_storage(credentials),
                    updated_at=now,
                )
            )
        except Exception:
            # R1 — tolérance : la cible est laissée intégralement inchangée
            # (credentials et ssh_key_id), l'upgrade ne doit jamais échouer.
            # Warning sans aucune donnée sensible (id de ligne uniquement).
            logger.warning(
                "1311: cible %s laissée inchangée — déchiffrement ou import "
                "de la clé SSH impossible (clé maîtresse modifiée ou PEM "
                "invalide)",
                target_id,
            )


def upgrade() -> None:
    # ── 1. Table ssh_keys (spec 06 § SSHKey) ───────────────────────────
    op.create_table(
        "ssh_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Nom d'affichage unique de la clé",
        ),
        sa.Column(
            "key_type",
            sa.String(length=20),
            nullable=False,
            comment="Algorithme (ssh-ed25519 recommandé, ssh-rsa accepté)",
        ),
        sa.Column(
            "public_key",
            sa.Text(),
            nullable=False,
            comment="Partie publique (déploiement authorized_keys)",
        ),
        sa.Column(
            "private_key_encrypted",
            sa.Text(),
            nullable=False,
            comment="Clé privée chiffrée (token Fernet) — jamais en clair",
        ),
        sa.Column(
            "fingerprint",
            sa.String(length=100),
            nullable=False,
            comment="Empreinte SHA256:<base64nopad> (identification, dédup)",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(),
            nullable=True,
            comment="Dernière session SSH réussie utilisant cette clé",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    with op.batch_alter_table("ssh_keys", schema=None) as batch_op:
        batch_op.create_index("idx_ssh_keys_fingerprint", ["fingerprint"], unique=False)

    # ── 2. Table host_ssh_fingerprints (spec 06 § HostSSHFingerprint) ──
    op.create_table(
        "host_ssh_fingerprints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "host_id",
            sa.String(length=36),
            nullable=False,
            comment="Cible (targets.id — arbitrage F3, renommage STORY-166)",
        ),
        sa.Column(
            "hostname",
            sa.String(length=255),
            nullable=False,
            comment="Adresse de connexion vérifiée",
        ),
        sa.Column(
            "port",
            sa.Integer(),
            nullable=False,
            comment="Port SSH de l'hôte vérifié",
        ),
        sa.Column(
            "key_type",
            sa.String(length=20),
            nullable=False,
            comment="Algorithme de la clé d'hôte (ssh-ed25519…)",
        ),
        sa.Column(
            "fingerprint",
            sa.String(length=100),
            nullable=False,
            comment="Empreinte attendue SHA256:<base64nopad>",
        ),
        sa.Column(
            "accepted",
            sa.Boolean(),
            nullable=False,
            comment="TRUE après acceptation explicite (TOFU)",
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(),
            nullable=True,
            comment="Date d'acceptation explicite",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "host_id",
            "hostname",
            "port",
            "key_type",
            name="uq_host_ssh_fp_identity",
        ),
    )
    with op.batch_alter_table("host_ssh_fingerprints", schema=None) as batch_op:
        batch_op.create_index("idx_host_ssh_fp_host", ["host_id"], unique=False)

    # ── 3. FK targets.ssh_key_id (nullable, SET NULL — N cibles ↔ 1 clé) ──
    with op.batch_alter_table("targets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ssh_key_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_targets_ssh_key_id",
            "ssh_keys",
            ["ssh_key_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # ── 4. Data migration (AC 1 « sans perte », tolérante R1) ─────────
    _migrate_ssh_private_keys_to_entities()


def downgrade() -> None:
    # Non destructif : les clés importées ne sont pas ré-inlinées dans les
    # credentials (limite documentée — la clé publique exportée et le retrait
    # du champ d'origine rendent la reconstruction non réversible).
    with op.batch_alter_table("targets", schema=None) as batch_op:
        batch_op.drop_column("ssh_key_id")

    op.drop_table("host_ssh_fingerprints")
    op.drop_table("ssh_keys")
