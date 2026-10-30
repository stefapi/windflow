"""Module de transition du domaine ``Target`` (STORY-166.1, purge 166.6).

Les définitions **legacy** (``TargetType``, ``TargetStatus``) sont
conservées ici : ``TargetType`` reste utilisé par les stack definitions
(``target_type`` YAML) et ``stacks.target_type`` (divergence n°4 de
STORY-166 — incorporation F3 reportée).

Les enums d'accès (``SSHAuthMethod``, ``AccessLevel``, ``CapabilityType``)
et les enums canoniques (``HostProfile``, ``HostStatus``,
``WorkloadOrigin``) sont **définis** dans :mod:`app.enums.host` et
**re-exportés** ici — tous les imports legacy
``from app.enums.target import X`` continuent de fonctionner sans
modification (AC 2 — transition sans casse).

⚠️ ``TargetStatus`` ne peut pas être un simple alias de ``HostStatus`` :
leurs valeurs divergent (``error``/``maintenance`` legacy vs
``unreachable``/``scanning`` canoniques) — la conversion passe par
:func:`app.helper.target_host_migration.map_target_status`.
"""

from enum import Enum

from .host import (  # noqa: F401
    AccessLevel,
    CapabilityType,
    HostProfile,
    HostStatus,
    SSHAuthMethod,
    WorkloadOrigin,
)


class TargetType(str, Enum):
    """Types de cibles de déploiement supportés (legacy — spec stack definitions)."""

    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    DOCKER_SWARM = "docker_swarm"
    KUBERNETES = "kubernetes"
    VM = "vm"
    PHYSICAL = "physical"


class TargetStatus(str, Enum):
    """Statuts possibles pour une cible (legacy — remplacé par ``HostStatus``)."""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"
