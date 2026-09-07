"""Baseline du schéma existant — ~10 modèles ORM (STORY-120.1)

Reproduit à l'identique le schéma créé historiquement par
``Base.metadata.create_all()`` (backend/app/database.py) : tables,
clés primaires String(36), FK avec ``ondelete``, index, contraintes
uniques, defaults et comments — compatible SQLite et PostgreSQL.

Sur une base **existante** (créée par create_all) :
``alembic stamp baseline`` puis ``alembic upgrade head`` → no-op.

Revision ID: baseline
Revises:
Create Date: 2026-09-07 21:07:24.782111+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_organizations_name"), ["name"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_organizations_slug"), ["slug"], unique=True
        )

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "task_type",
            sa.Enum(
                "CLEANUP_LOGS",
                "HEALTH_CHECK",
                "GIT_SYNC",
                "RETRY_DEPLOYMENTS",
                "CUSTOM",
                name="tasktype",
            ),
            nullable=False,
        ),
        sa.Column("cron_expression", sa.String(length=100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=50), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_scheduled_tasks_name"), ["name"], unique=False
        )

    op.create_table(
        "stacks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template", sa.JSON(), nullable=False),
        sa.Column(
            "variables",
            sa.JSON(),
            nullable=False,
            comment="Variables configurables au format simple",
        ),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column(
            "target_type",
            sa.String(length=50),
            nullable=False,
            comment="Type de déploiement supporté par ce stack",
        ),
        sa.Column(
            "target_parameters",
            sa.JSON(),
            nullable=True,
            comment="Paramètres spécifiques à la target (ex: volumes à supprimer)",
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("downloads", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("icon_url", sa.String(length=500), nullable=True),
        sa.Column("screenshots", sa.JSON(), nullable=False),
        sa.Column("documentation_url", sa.String(length=500), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("license", sa.String(length=100), nullable=True),
        sa.Column(
            "deployment_name",
            sa.String(length=255),
            nullable=True,
            comment="Nom par défaut du déploiement (template)",
        ),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("stacks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_stacks_category"), ["category"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_stacks_is_archived"), ["is_archived"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_stacks_is_public"), ["is_public"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_stacks_name"), ["name"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_stacks_organization_id"),
            ["organization_id"],
            unique=False,
        )

    op.create_table(
        "targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "DOCKER",
                "DOCKER_COMPOSE",
                "DOCKER_SWARM",
                "KUBERNETES",
                "VM",
                "PHYSICAL",
                name="targettype",
            ),
            nullable=False,
        ),
        sa.Column("credentials", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ONLINE", "OFFLINE", "ERROR", "MAINTENANCE", name="targetstatus"),
            nullable=False,
        ),
        sa.Column("last_check", sa.DateTime(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "scan_date",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp of the last capabilities scan",
        ),
        sa.Column(
            "scan_success",
            sa.Boolean(),
            nullable=True,
            comment="Indicates if the last capabilities scan succeeded",
        ),
        sa.Column(
            "platform_info",
            sa.JSON(),
            nullable=True,
            comment="Platform capabilities detected during the last scan",
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
            comment="Access profile detected during the last scan "
            "(SSH user, sudo, capabilities)",
        ),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("targets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_targets_name"), ["name"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_targets_organization_id"),
            ["organization_id"],
            unique=False,
        )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("keycloak_id", sa.String(length=255), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keycloak_id"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_users_organization_id"),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_users_username"), ["username"], unique=True
        )

    op.create_table(
        "deployments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stack_id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "DEPLOYING",
                "RUNNING",
                "FAILED",
                "STOPPED",
                "ROLLING_BACK",
                name="deploymentstatus",
            ),
            nullable=False,
        ),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column(
            "container_id",
            sa.String(length=128),
            nullable=True,
            comment="ID du conteneur Docker créé par ce déploiement",
        ),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column(
            "rendered_target_parameters",
            sa.JSON(),
            nullable=True,
            comment="Target parameters rendus avec Jinja lors de la création "
            "du déploiement",
        ),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("task_started_at", sa.DateTime(), nullable=True),
        sa.Column("task_retry_count", sa.Integer(), nullable=False),
        sa.Column("deploy_duration_seconds", sa.Float(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(), nullable=True),
        sa.Column("stopped_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["stack_id"], ["stacks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("deployments", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_deployments_container_id"),
            ["container_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_deployments_name"), ["name"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_deployments_organization_id"),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_deployments_stack_id"), ["stack_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_deployments_target_id"), ["target_id"], unique=False
        )

    op.create_table(
        "plugins",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Identifiant unique du plugin (kebab-case)",
        ),
        sa.Column(
            "version",
            sa.String(length=50),
            nullable=False,
            comment="Version du plugin (semver)",
        ),
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            comment="Nom affiché dans l'UI",
        ),
        sa.Column(
            "description", sa.Text(), nullable=True, comment="Description du plugin"
        ),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            comment="Catégorie du plugin (PluginCategory value)",
        ),
        sa.Column(
            "type",
            sa.String(length=20),
            nullable=False,
            comment="Type de plugin (PluginType value)",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Statut du plugin (PluginStatus value)",
        ),
        sa.Column(
            "manifest_data",
            sa.JSON(),
            nullable=False,
            comment="Manifest validé complet (JSON)",
        ),
        sa.Column(
            "config_values",
            sa.JSON(),
            nullable=False,
            comment="Valeurs de configuration saisies par l'utilisateur",
        ),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column(
            "installed_by",
            sa.String(length=36),
            nullable=True,
            comment="ID de l'utilisateur ayant installé le plugin",
        ),
        sa.Column("installed_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["installed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("plugins", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_plugins_name"), ["name"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_plugins_organization_id"),
            ["organization_id"],
            unique=False,
        )

    op.create_table(
        "stack_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stack_id", sa.String(length=36), nullable=False),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            comment="Numéro de version incrémental",
        ),
        sa.Column(
            "compose_content",
            sa.Text(),
            nullable=False,
            comment="Contenu YAML du compose à cette version",
        ),
        sa.Column(
            "variables",
            sa.JSON(),
            nullable=False,
            comment="Variables à cette version",
        ),
        sa.Column(
            "change_summary",
            sa.String(length=500),
            nullable=True,
            comment="Résumé des modifications",
        ),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["stack_id"], ["stacks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("stack_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_stack_versions_stack_id"), ["stack_id"], unique=False
        )

    op.create_table(
        "target_capabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column(
            "capability_type",
            sa.Enum(
                "LIBVIRT",
                "VIRSH",
                "VIRTUALBOX",
                "VAGRANT",
                "PROXMOX",
                "QEMU_KVM",
                "MULTIPASS",
                "DOCKER",
                "DOCKER_COMPOSE",
                "DOCKER_SWARM",
                "PODMAN",
                "PODMAN_COMPOSE",
                "LXC",
                "LXD",
                "INCUS",
                "RUNC",
                "CRUN",
                "CONTAINERD",
                "BUILDAH",
                "SKOPEO",
                "KUBECTL",
                "KUBEADM",
                "K3S",
                "MICROK8S",
                "HELM",
                name="capabilitytype",
            ),
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
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "target_id", "capability_type", name="uq_target_capability_type"
        ),
    )
    with op.batch_alter_table("target_capabilities", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_target_capabilities_target_id"),
            ["target_id"],
            unique=False,
        )

    op.create_table(
        "plugin_hook_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "plugin_id",
            sa.String(length=36),
            nullable=False,
            comment="ID du plugin concerné",
        ),
        sa.Column(
            "hook_name",
            sa.String(length=50),
            nullable=False,
            comment="Nom du hook (on_install, on_configure, on_start, on_stop, "
            "on_uninstall)",
        ),
        sa.Column(
            "script_path",
            sa.String(length=500),
            nullable=False,
            comment="Chemin du script shell exécuté",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Statut : pending, running, success, failed",
        ),
        sa.Column(
            "exit_code",
            sa.Integer(),
            nullable=True,
            comment="Code de retour du processus (null si timeout ou non exécuté)",
        ),
        sa.Column(
            "stdout",
            sa.Text(),
            nullable=False,
            comment="Sortie standard capturée (tronquée à 10 000 caractères)",
        ),
        sa.Column(
            "stderr",
            sa.Text(),
            nullable=False,
            comment="Sortie d'erreur capturée (tronquée à 10 000 caractères)",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            comment="Date/heure de début d'exécution",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
            comment="Date/heure de fin d'exécution",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
            comment="Durée d'exécution en millisecondes",
        ),
        sa.Column(
            "triggered_by",
            sa.String(length=36),
            nullable=True,
            comment="ID de l'utilisateur ayant déclenché le hook",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Message d'erreur en cas d'échec",
        ),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("plugin_hook_logs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_plugin_hook_logs_plugin_id_hook_name",
            ["plugin_id", "hook_name"],
            unique=False,
        )
        batch_op.create_index(
            "ix_plugin_hook_logs_started_at", ["started_at"], unique=False
        )


def downgrade() -> None:
    # Drops dans l'ordre inverse des dépendances (enfants d'abord).
    with op.batch_alter_table("plugin_hook_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_plugin_hook_logs_started_at")
        batch_op.drop_index("ix_plugin_hook_logs_plugin_id_hook_name")

    op.drop_table("plugin_hook_logs")
    with op.batch_alter_table("target_capabilities", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_target_capabilities_target_id"))

    op.drop_table("target_capabilities")
    with op.batch_alter_table("stack_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stack_versions_stack_id"))

    op.drop_table("stack_versions")
    with op.batch_alter_table("plugins", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_plugins_organization_id"))
        batch_op.drop_index(batch_op.f("ix_plugins_name"))

    op.drop_table("plugins")
    with op.batch_alter_table("deployments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployments_target_id"))
        batch_op.drop_index(batch_op.f("ix_deployments_stack_id"))
        batch_op.drop_index(batch_op.f("ix_deployments_organization_id"))
        batch_op.drop_index(batch_op.f("ix_deployments_name"))
        batch_op.drop_index(batch_op.f("ix_deployments_container_id"))

    op.drop_table("deployments")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_username"))
        batch_op.drop_index(batch_op.f("ix_users_organization_id"))
        batch_op.drop_index(batch_op.f("ix_users_email"))

    op.drop_table("users")
    with op.batch_alter_table("targets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_targets_organization_id"))
        batch_op.drop_index(batch_op.f("ix_targets_name"))

    op.drop_table("targets")
    with op.batch_alter_table("stacks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stacks_organization_id"))
        batch_op.drop_index(batch_op.f("ix_stacks_name"))
        batch_op.drop_index(batch_op.f("ix_stacks_is_public"))
        batch_op.drop_index(batch_op.f("ix_stacks_is_archived"))
        batch_op.drop_index(batch_op.f("ix_stacks_category"))

    op.drop_table("stacks")
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scheduled_tasks_name"))

    op.drop_table("scheduled_tasks")
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_organizations_slug"))
        batch_op.drop_index(batch_op.f("ix_organizations_name"))

    op.drop_table("organizations")
