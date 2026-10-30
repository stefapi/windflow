"""Renommage Target→Host : tables ``hosts``/``host_capabilities`` + data migration (STORY-166.1)

Migration du volet modèle de STORY-166 (P2-4, spec 06 § Host et §
Migration de ``targets`` vers ``hosts``) : l'entité ``Target`` devient
``Host`` — schéma canonique, enums canoniques, capacités éclatées —
**sans perte de données** (credentials chiffrés copiés octet à octet,
jamais déchiffrés — STORY-103, rules 40).

⚠️ **Backup préalable obligatoire** (procédure documentée) :

    cp data/windflow.db data/windflow.db.bak-1661   # SQLite dev
    # ou pg_dump windflow > windflow-1661.bak.sql    # PostgreSQL

La migration droppe ``targets``/``target_capabilities`` après
validation : en cas d'échec en cours de route, **restaurer le backup**
(le downgrade est un no-op documenté — cf. fin de docstring).

Tables de correspondance arbitrées (story 166.1, analyse 2026-10-24)
====================================================================

1. ``TargetType`` (6 valeurs) → ``HostProfile`` (3 valeurs) — règle en
   deux dimensions : valeur de l'enum × caractère local/distant du host
   (``host ∈ {localhost, 127.0.0.1}``), capacités scannées comme
   tie-breaker pour le repli ``kubernetes`` :

=====================  =====================  =========================
``TargetType``        host localhost/127.0.0.1   host distant
=====================  =====================  =========================
``docker``            ``host_baremetal``     ``host_remote_docker``
``docker_compose``    ``host_baremetal``     ``host_remote_docker``
``docker_swarm``      ``host_baremetal``     ``host_remote_docker``
``kubernetes`` (repli) ``host_baremetal``    ``host_remote_docker`` si
                                             capacité ``docker``
                                             disponible, sinon
                                             ``host_baremetal``
``vm``                ``host_baremetal``     ``host_baremetal``
``physical``          ``host_baremetal``     ``host_baremetal``
=====================  =====================  =========================

Justifications : ``host_kubernetes`` est supprimé (spec 02 — les grappes
multi-nœuds deviendront l'entité ``Cluster``, Roadmap Phase 2) : un host
kubernetes redevient un substrat individuel ; ``host_remote_docker`` est
réservé au pilotage Docker distant (TCP/API) ; une VM est un substrat
individuel (pas de ``host_vm`` — le caractère VM reste visible via
``installed_engines``). La donnée « kubernetes » n'est pas perdue :
``extra_metadata.migrated_type`` trace l'enum source.

2. ``TargetStatus`` → ``HostStatus`` :

=================  =================  =====================================
``TargetStatus``   ``HostStatus``     Justification
=================  =================  =====================================
``online``         ``online``         identique
``offline``        ``offline``        identique
``error``          ``unreachable``   sémantique canonique « injoignable »
``maintenance``    ``offline``        choix opérateur, pas un état sondé
=================  =================  =====================================

``HostStatus.scanning`` n'a pas d'antécédent legacy (posé par
``mark_scan_in_progress``).

3. Mapping des colonnes : ``id, name, description, host, port,
   credentials, ssh_key_id, extra_metadata, scan_success, os_info,
   access_profile, organization_id, created_at, updated_at`` copiés
   verbatim ; ``type``→``profile`` (+ trace ``migrated_type``) ;
   ``status``→``status`` (table 2) ; ``scan_date``→``last_scan_at`` ;
   ``last_check`` conservée ; ``platform_info``→``hardware_info`` ;
   ``installed_engines`` alimenté depuis ``target_capabilities`` ;
   ``origin`` = ``managed`` (défaut).

Détails d'implémentation :

- Les bases legacy persistent les enums en **noms de membres**
  (``'ONLINE'``, ``'DOCKER'`` — SQLEnum sans ``values_callable`` dans la
  baseline) ; les helpers de mapping lisent les **deux formes** (nom ou
  valeur) — la data migration boucle en Python (lisible, testable) avec
  les mêmes règles que :mod:`app.helper.target_host_migration` (tests
  unitaires dédiés).
- Colonnes enum créées en ``sa.Enum`` avec les **valeurs** canoniques
  (alignées sur ``values_callable`` des modèles) : ``alembic check``
  reste sans diff modèles ↔ migrations.
- **Défensive** : si ``targets`` est absente du schéma (base déjà
  canonique — ex. ``create_all`` avec les modèles courants), la
  migration est un no-op journalisé ; ``targets`` ET ``hosts``
  coexistant = état incohérent → ``RuntimeError`` avant toute écriture.
- Retarget des **3 FK réelles** : ``deployments.target_id``→
  ``deployments.host_id`` (batch 2 temps : add colonne → copie →
  batch final drop/FK/not null, pattern STORY-120/1311) ;
  ``host_ssh_fingerprints`` rebuild par rename/copy (FK anonyme inline
  SQLite non adressable par ``drop_constraint``) ; FK
  ``host_capabilities.host_id`` créée native vers ``hosts.id``.
- Validation avant drop : comptages hôtes/capacités identiques avant/
  après — tout écart abort la migration (``RuntimeError``) avant toute
  perte ; log INFO sans donnée sensible.
- Mode offline (``--sql``) : DDL seul (pattern 1311), aucune donnée.
- Downgrade : **non reconstructible** (l'éclat ``hardware_info``/
  ``installed_engines`` et le mapping N→3 perdent la forme originale) —
  no-op documenté avec message de restauration de backup, pattern 1341.

Revision ID: 1661_targets_to_hosts
Revises: 1341_normalize_event_names
Create Date: 2026-10-24 23:00:00.000000+00:00

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context as alembic_context
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "1661_targets_to_hosts"
down_revision: Union[str, None] = "1341_normalize_event_names"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Valeurs canoniques des enums persistées (valeurs, pas noms de membres
# — alignées sur les modèles ``values_callable``).
_PROFILE_VALUES = ("host_baremetal", "host_proxmox", "host_remote_docker")
_STATUS_VALUES = ("online", "offline", "unreachable", "scanning")
_ORIGIN_VALUES = ("managed", "adopted", "external")
_CAPABILITY_VALUES = (
    "libvirt",
    "virsh",
    "virtualbox",
    "vagrant",
    "proxmox",
    "qemu_kvm",
    "multipass",
    "docker",
    "docker_compose",
    "docker_swarm",
    "podman",
    "podman_compose",
    "lxc",
    "lxd",
    "incus",
    "runc",
    "crun",
    "containerd",
    "buildah",
    "skopeo",
    "kubectl",
    "kubeadm",
    "k3s",
    "microk8s",
    "helm",
)


def _create_hosts_tables() -> None:
    """Étape 1 — tables canoniques ``hosts`` et ``host_capabilities``.

    Colonnes ``sa.Enum`` persistant les **valeurs** d'enum (mêmes membres
    que les modèles ``values_callable``) : ``alembic check`` reste sans
    diff après migration.
    """
    op.create_table(
        "hosts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        # Schéma canonique (spec 06 — STORY-166.1)
        sa.Column(
            "profile",
            sa.Enum(*_PROFILE_VALUES, name="hostprofile"),
            nullable=False,
            comment="Profil canonique (host_baremetal, host_proxmox, host_remote_docker)",
        ),
        sa.Column(
            "status", sa.Enum(*_STATUS_VALUES, name="hoststatus"), nullable=False
        ),
        sa.Column(
            "hardware_info",
            sa.JSON(),
            nullable=True,
            comment="Informations matérielles détectées lors du dernier scan",
        ),
        sa.Column(
            "installed_engines",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="Moteurs détectés (payload {capability_type, version, is_available})",
        ),
        sa.Column(
            "last_scan_at",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp of the last capabilities scan",
        ),
        sa.Column(
            "origin",
            sa.Enum(*_ORIGIN_VALUES, name="workloadorigin"),
            nullable=False,
            server_default="managed",
            comment="Origine du workload (managed, adopted, external)",
        ),
        # Colonnes conservées verbatim de targets (credentials chiffrés
        # STORY-103 — jamais déchiffrés pendant la migration)
        sa.Column("credentials", sa.JSON(), nullable=False),
        sa.Column(
            "ssh_key_id",
            sa.String(length=36),
            nullable=True,
            comment="Clé SSH réutilisable (FK ssh_keys.id — SET NULL)",
        ),
        sa.Column("last_check", sa.DateTime(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "scan_success",
            sa.Boolean(),
            nullable=True,
            comment="Indicates if the last capabilities scan succeeded",
        ),
        sa.Column(
            "os_info",
            sa.JSON(),
            nullable=True,
            comment="Operating system information detected during the last scan",
        ),
        sa.Column(
            "access_profile",
            sa.JSON(),
            nullable=True,
            comment="Access profile detected during the last scan (SSH user, sudo, capabilities)",
        ),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ssh_key_id"], ["ssh_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("hosts", schema=None) as batch_op:
        batch_op.create_index("ix_hosts_name", ["name"], unique=False)
        batch_op.create_index(
            "ix_hosts_organization_id", ["organization_id"], unique=False
        )

    op.create_table(
        "host_capabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("host_id", sa.String(length=36), nullable=False),
        sa.Column(
            "capability_type",
            sa.Enum(*_CAPABILITY_VALUES, name="capabilitytype"),
            nullable=False,
        ),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=True),
        sa.Column(
            "details",
            sa.JSON(),
            nullable=True,
            comment="Informations supplémentaires retournées par le scanner",
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(),
            nullable=False,
            comment="Date de détection de la capacité",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "host_id", "capability_type", name="uq_host_capability_type"
        ),
    )
    with op.batch_alter_table("host_capabilities", schema=None) as batch_op:
        batch_op.create_index("ix_host_capabilities_host_id", ["host_id"], unique=False)


def _copy_targets_data() -> None:
    """Étapes 2-4 — copie ``targets``→``hosts`` + capacités éclatées.

    Data migration en Python : les règles d'arbitrage (notamment le
    tie-breaker ``kubernetes`` × capacité docker) sont portées par
    :mod:`app.helper.target_host_migration` — mêmes règles que les tests
    unitaires du helper. Les credentials chiffrés sont copiés **octet à
    octet** (structure JSON réinsérée à l'identique, jamais déchiffrée).
    """
    from app.enums.target import TargetType
    from app.helper.target_host_migration import (
        map_target_status,
        map_target_to_host_profile,
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    targets_t = sa.Table("targets", metadata, autoload_with=bind)
    caps_t = sa.Table("target_capabilities", metadata, autoload_with=bind)
    hosts_t = sa.Table("hosts", metadata, autoload_with=bind)
    host_caps_t = sa.Table("host_capabilities", metadata, autoload_with=bind)

    caps_by_target: dict[str, list[dict]] = {}
    for cap in bind.execute(sa.select(caps_t)).mappings().all():
        caps_by_target.setdefault(cap["target_id"], []).append(dict(cap))

    for row in bind.execute(sa.select(targets_t)).mappings().all():
        raw_type = row["type"]

        # Tie-breaker kubernetes : capacité docker **disponible**.
        caps = caps_by_target.get(row["id"], [])
        has_docker_capability = any(
            str(cap["capability_type"]).lower() == "docker"
            and bool(cap["is_available"])
            for cap in caps
        )

        profile = map_target_to_host_profile(
            raw_type, row["host"], has_docker_capability
        )
        status = map_target_status(row["status"])

        # Trace de l'enum source : valeur legacy canonique (les bases
        # legacy stockent le nom 'DOCKER', on persiste la valeur
        # 'docker' — cohérent avec TargetType(migrated_type)).
        try:
            if isinstance(raw_type, str):
                try:
                    source_value = TargetType(raw_type).value
                except ValueError:
                    source_value = TargetType[raw_type.upper()].value
            else:
                source_value = str(raw_type).lower()
        except (ValueError, KeyError):
            source_value = str(raw_type).lower()

        extra_metadata = dict(row["extra_metadata"] or {})
        extra_metadata["migrated_type"] = source_value

        # Éclat des capacités : payload {capability_type, version,
        # is_available} par capacité (spec 06 ``installed_engines``).
        installed_engines = [
            {
                "capability_type": str(cap["capability_type"]).lower(),
                "version": cap["version"],
                "is_available": bool(cap["is_available"]),
            }
            for cap in caps
        ]

        bind.execute(
            hosts_t.insert().values(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                host=row["host"],
                port=row["port"],
                profile=profile.value,
                status=status.value,
                hardware_info=row["platform_info"],
                installed_engines=installed_engines,
                last_scan_at=row["scan_date"],
                origin="managed",
                # Credentials chiffrés : copie verbatim (jamais déchiffrés).
                credentials=row["credentials"],
                ssh_key_id=row["ssh_key_id"],
                last_check=row["last_check"],
                extra_metadata=extra_metadata,
                scan_success=row["scan_success"],
                os_info=row["os_info"],
                access_profile=row["access_profile"],
                organization_id=row["organization_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )

    # Étape 4 — copie ligne à ligne target_capabilities → host_capabilities
    for cap in bind.execute(sa.select(caps_t)).mappings().all():
        bind.execute(
            host_caps_t.insert().values(
                id=cap["id"],
                host_id=cap["target_id"],
                capability_type=str(cap["capability_type"]).lower(),
                is_available=cap["is_available"],
                version=cap["version"],
                details=cap["details"],
                detected_at=cap["detected_at"],
                created_at=cap["created_at"],
                updated_at=cap["updated_at"],
            )
        )


def _retarget_deployments_fk() -> None:
    """Étape 5a — ``deployments.target_id`` → ``deployments.host_id``.

    Batch en 2 temps (SQLite) : ajout de ``host_id`` nullable → copie
    des valeurs → batch final (drop index/colonne legacy, FK vers
    ``hosts.id``, NOT NULL, index recréé) — pattern éprouvé STORY-131.1.
    """
    with op.batch_alter_table("deployments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("host_id", sa.String(length=36), nullable=True))

    op.execute("UPDATE deployments SET host_id = target_id")

    with op.batch_alter_table("deployments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployments_target_id"))
        batch_op.drop_column("target_id")
        batch_op.create_foreign_key(
            "fk_deployments_host_id",
            "hosts",
            ["host_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.alter_column("host_id", existing_type=sa.String(36), nullable=False)
        batch_op.create_index("ix_deployments_host_id", ["host_id"], unique=False)


def _fingerprints_points_to_targets(bind: sa.engine.Connection) -> bool:
    """Vrai si la FK de ``host_ssh_fingerprints`` référence ``targets``.

    Réflexion moteur-agnostique (SQLite + PostgreSQL) — utilisée pour
    retargeter y compris dans le chemin no-op (base déjà ``hosts`` mais
    fingerprints recréée vers ``targets`` par la 1311, ex. simulation
    ``create_all`` stampée baseline).
    """
    inspector = sa.inspect(bind)
    if "host_ssh_fingerprints" not in inspector.get_table_names():
        return False
    return any(
        fk.get("referred_table") == "targets"
        for fk in inspector.get_foreign_keys("host_ssh_fingerprints")
    )


def _retarget_fingerprints_fk() -> None:
    """Étape 5b — ``host_ssh_fingerprints.host_id`` → ``hosts.id``.

    La FK existante (migration 1311) est **anonyme inline** : non
    adressable par ``batch drop_constraint`` (aucun nom en base SQLite).
    Rebuild déterministe par rename/copy : la table est recréée à
    l'identique (colonnes + contraintes 1311) avec la FK retargetée.
    """
    # SQLite : l'index suit la table renommée — le dropper d'abord pour
    # pouvoir le recréer sur la nouvelle table (même nom, spec 1311).
    op.drop_index("idx_host_ssh_fp_host", table_name="host_ssh_fingerprints")
    op.rename_table("host_ssh_fingerprints", "_1661_host_ssh_fingerprints_old")
    op.create_table(
        "host_ssh_fingerprints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "host_id",
            sa.String(length=36),
            nullable=False,
            comment="Host (hosts.id — STORY-166.1)",
        ),
        sa.Column(
            "hostname",
            sa.String(length=255),
            nullable=False,
            comment="Adresse de connexion vérifiée",
        ),
        sa.Column(
            "port", sa.Integer(), nullable=False, comment="Port SSH de l'hôte vérifié"
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
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "host_id", "hostname", "port", "key_type", name="uq_host_ssh_fp_identity"
        ),
    )
    with op.batch_alter_table("host_ssh_fingerprints", schema=None) as batch_op:
        batch_op.create_index("idx_host_ssh_fp_host", ["host_id"], unique=False)

    op.execute(
        "INSERT INTO host_ssh_fingerprints "
        "(id, host_id, hostname, port, key_type, fingerprint, accepted, "
        "accepted_at, created_at) "
        "SELECT id, host_id, hostname, port, key_type, fingerprint, accepted, "
        "accepted_at, created_at FROM _1661_host_ssh_fingerprints_old"
    )
    op.drop_table("_1661_host_ssh_fingerprints_old")


def _validate_and_drop() -> None:
    """Étapes 6-7 — validation par comptage puis drop des tables legacy.

    Garde-fou (AC 1) : les comptages hosts/targets et capacités doivent
    être identiques — tout écart lève ``RuntimeError`` (le drop n'a pas
    lieu, aucune perte). Log INFO sans donnée sensible.
    """
    bind = op.get_bind()
    targets_count = bind.execute(sa.text("SELECT COUNT(*) FROM targets")).scalar_one()
    hosts_count = bind.execute(sa.text("SELECT COUNT(*) FROM hosts")).scalar_one()
    caps_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM target_capabilities")
    ).scalar_one()
    host_caps_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM host_capabilities")
    ).scalar_one()

    logger.info(
        "Migration 1661 validation: hosts=%s (targets=%s), "
        "host_capabilities=%s (target_capabilities=%s)",
        hosts_count,
        targets_count,
        host_caps_count,
        caps_count,
    )

    if hosts_count != targets_count:
        raise RuntimeError(
            f"Validation échouée : {hosts_count} hosts copiés pour "
            f"{targets_count} targets — migration abortée avant drop"
        )
    if host_caps_count != caps_count:
        raise RuntimeError(
            f"Validation échouée : {host_caps_count} host_capabilities "
            f"pour {caps_count} target_capabilities — migration abortée"
        )

    op.drop_table("target_capabilities")
    op.drop_table("targets")


def upgrade() -> None:
    if alembic_context.is_offline_mode():
        # Génération SQL hors ligne : DDL seul, aucune donnée à migrer
        # (pattern 1311).
        _create_hosts_tables()
        return

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "targets" not in tables:
        if "hosts" not in tables:
            # Base sans targets ni hosts (état inattendu) : créer le
            # schéma canonique vide plutôt qu'échouer.
            logger.info("Migration 1661 : targets absente — création hosts vide")
            _create_hosts_tables()
        else:
            # Base déjà canonique (ex. create_all avec les modèles
            # courants STORY-166.1) : no-op journalisé — sauf la FK de
            # ``host_ssh_fingerprints`` si la 1311 l'a (re)créée vers
            # ``targets`` (simulation create_all stampée baseline).
            logger.info(
                "Migration 1661 : schéma déjà canonique (hosts présente, "
                "targets absente) — no-op"
            )
        if _fingerprints_points_to_targets(bind):
            _retarget_fingerprints_fk()
        return

    if "hosts" in tables:
        raise RuntimeError(
            "Migration 1661 : tables hosts ET targets coexistantes — "
            "état incohérent, abort avant toute écriture (restaurer le backup)"
        )

    # Étape 1 : schéma canonique
    _create_hosts_tables()
    # Étapes 2-4 : data migration (Python, helpers partagés/testés)
    _copy_targets_data()
    # Étape 5 : retarget des FK existantes vers hosts.id
    _retarget_deployments_fk()
    _retarget_fingerprints_fk()
    # Étapes 6-7 : validation par comptage, puis drop
    _validate_and_drop()


def downgrade() -> None:
    """Downgrade **no-op documenté** (pattern 1341 — irreversible).

    La reconstruction de ``targets`` depuis ``hosts`` n'est pas fiable :
    l'éclat ``hardware_info``/``installed_engines`` et le mapping
    6→3 valeurs perdent la forme originale (seul ``migrated_type``
    survit). Procédure de retour arrière : **restaurer le backup**
    pris avant l'upgrade (cf. docstring d'en-tête).
    """
    logger.warning(
        "Downgrade 1661 non supporté (irreversible) — restaurer le backup "
        "de base pris avant l'upgrade (procédure en docstring de la révision)"
    )
