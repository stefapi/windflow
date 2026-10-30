"""Helpers purs de mapping ``Target``→``Host`` (STORY-166.1).

Centralisent en Python pur les tables de correspondance arbitrées en
analyse (story 166.1, section Contexte technique) : les **mêmes règles**
sont appliquées par la data migration Alembic ``1661`` (SQL ``CASE`` +
EXISTS pour le tie-breaker ``kubernetes``) et par ces fonctions —
testables unitairement sans base de données.

Aucune donnée sensible manipulée (valeurs d'enum et adresses de host
uniquement).

Tables de correspondance (source de vérité : story 166.1)
---------------------------------------------------------

``TargetType`` (6 valeurs) → ``HostProfile`` (3 valeurs) — règle en deux
dimensions : valeur de l'enum × caractère local/distant du host
(``host ∈ {localhost, 127.0.0.1}``), avec les capacités scannées
(``docker`` disponible dans ``target_capabilities``) comme tie-breaker
pour le repli ``kubernetes`` :

=====================  ====================  ==============================
``TargetType``         host localhost/127.0.0.1   host distant
=====================  ====================  ==============================
``docker``             ``host_baremetal``    ``host_remote_docker``
``docker_compose``     ``host_baremetal``    ``host_remote_docker``
``docker_swarm``       ``host_baremetal``    ``host_remote_docker``
``kubernetes`` (repli) ``host_baremetal``    ``host_remote_docker`` si
                                             capacité ``docker`` disponible,
                                             sinon ``host_baremetal``
``vm``                 ``host_baremetal``    ``host_baremetal``
``physical``           ``host_baremetal``    ``host_baremetal``
=====================  ====================  ==============================

``TargetStatus`` → ``HostStatus`` :

=================  =================  =====================================
``TargetStatus``   ``HostStatus``     Justification
=================  =================  =====================================
``online``         ``online``         identique
``offline``        ``offline``        identique
``error``          ``unreachable``   sémantique canonique « injoignable »
``maintenance``    ``offline``        choix opérateur, pas un état sondé
=================  =================  =====================================

``HostStatus.scanning`` n'a pas d'antécédent legacy : il devient l'état
posé par ``mark_scan_in_progress`` (comportement du ``scan_success=None``
conservé, exploitation en STORY-166.3).
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from ..enums.host import HostProfile, HostStatus
from ..enums.target import TargetStatus, TargetType

#: Enum cible du coerceur (membre ↔ valeur brute).
_EnumT = TypeVar("_EnumT", bound=Enum)


def _coerce_enum_member(raw: str | _EnumT, enum_cls: type[_EnumT]) -> _EnumT:
    """Normalise une valeur stockée **nom ou valeur** vers le membre d'enum.

    Les bases legacy (baseline Alembic) persistent les **noms de membres**
    (``'ONLINE'``, ``'DOCKER'`` — SQLEnum sans ``values_callable``), les
    nouvelles écritures les **valeurs** (``'online'``, ``'docker'``) : la
    migration ``1661`` lit les deux formes. La casse est neutralisée
    (noms uppercase stockés, valeurs lowercase).

    Args:
        raw: Valeur brute lue en base (ou membre déjà résolu).
        enum_cls: Classe d'enum cible (``TargetType``/``TargetStatus``).

    Returns:
        Le membre d'enum correspondant.

    Raises:
        ValueError: Si aucune correspondance nom ni valeur.
    """
    if isinstance(raw, enum_cls):
        return raw
    if isinstance(raw, str):
        try:
            return enum_cls(raw)
        except ValueError:
            pass
        try:
            return enum_cls[raw.upper()]
        except KeyError:
            pass
    raise ValueError(
        f"Valeur {raw!r} ne correspond à aucun nom ni valeur de {enum_cls.__name__}"
    )


#: Adresses considérées comme locales pour l'arbitrage du profil : un
#: Docker piloté via socket local = pilotage direct de la machine
#: (``host_baremetal``), ``host_remote_docker`` est réservé au pilotage
#: distant (TCP/API).
LOCALHOST_ADDRESSES: frozenset[str] = frozenset({"localhost", "127.0.0.1"})


def is_local_host_address(host_address: str | None) -> bool:
    """Retourne vrai si l'adresse désigne la machine locale.

    Args:
        host_address: Valeur de la colonne ``host`` (adresse IP ou
            hostname), éventuellement ``None``.

    Returns:
        ``True`` si l'adresse normalisée (trim + casse basse) est dans
        :data:`LOCALHOST_ADDRESSES`.
    """
    if not host_address:
        return False
    return host_address.strip().lower() in LOCALHOST_ADDRESSES


def map_target_to_host_profile(
    target_type: TargetType | str,
    host_address: str | None,
    has_docker_capability: bool = False,
) -> HostProfile:
    """Mappe un ``TargetType`` (6 valeurs) vers un ``HostProfile`` canonique.

    Règle arbitrée (divergence n°2 de STORY-166 — voir module) :

    - ``docker``/``docker_compose``/``docker_swarm`` distant →
      ``host_remote_docker`` (pilotage Docker distant) ; en local →
      ``host_baremetal`` (socket local = pilotage direct) ;
    - ``kubernetes`` (repli — ``host_kubernetes`` supprimé, spec 02) :
      l'host redevient un substrat individuel ; distant avec capacité
      scannée ``docker`` disponible → ``host_remote_docker``, sinon
      ``host_baremetal`` ;
    - ``vm``/``physical`` → ``host_baremetal`` (une VM est un substrat
      individuel — pas de ``host_vm`` dans ``HostProfile`` ; le caractère
      VM reste visible via ``installed_engines``).

    La valeur source n'est pas perdue : la migration la trace dans
    ``extra_metadata.migrated_type`` et ``installed_engines``.

    Args:
        target_type: Valeur de l'enum legacy (membre ou valeur brute).
        host_address: Adresse du host (arbitrage local/distant).
        has_docker_capability: Capacité scannée ``docker`` **disponible**
            (tie-breaker du repli ``kubernetes`` uniquement).

    Returns:
        Le profil canonique ``HostProfile``.

    Raises:
        ValueError: Si ``target_type`` n'est pas une valeur legacy connue.
    """
    if target_type is None:  # type: ignore[unreachable]
        raise ValueError("target_type est requis")
    member: TargetType = _coerce_enum_member(target_type, TargetType)

    if member in (
        TargetType.DOCKER,
        TargetType.DOCKER_COMPOSE,
        TargetType.DOCKER_SWARM,
    ):
        if is_local_host_address(host_address):
            return HostProfile.HOST_BAREMETAL
        return HostProfile.HOST_REMOTE_DOCKER

    if member is TargetType.KUBERNETES:
        # Repli (host_kubernetes supprimé) : substrat individuel. Le
        # pilotage Docker distant étant le seul usage distinguant
        # host_remote_docker, il ne s'applique qu'à un host distant
        # disposant réellement d'un Docker scanné.
        if not is_local_host_address(host_address) and has_docker_capability:
            return HostProfile.HOST_REMOTE_DOCKER
        return HostProfile.HOST_BAREMETAL

    # vm / physical : substrats individuels → host_baremetal.
    return HostProfile.HOST_BAREMETAL


def map_target_status(status: TargetStatus | str) -> HostStatus:
    """Mappe un ``TargetStatus`` legacy vers un ``HostStatus`` canonique.

    Table arbitrée (divergence n°3 de STORY-166) : ``online``/``offline``
    identiques, ``error`` → ``unreachable`` (sémantique canonique
    « injoignable »), ``maintenance`` → ``offline`` (choix opérateur, pas
    un état sondé — proposition de la mère validée en analyse).

    Args:
        status: Membre ou valeur brute du legacy ``TargetStatus``.

    Returns:
        Le statut canonique ``HostStatus``.

    Raises:
        ValueError: Si ``status`` n'est pas une valeur legacy connue.
    """
    member_status: TargetStatus = _coerce_enum_member(status, TargetStatus)

    mapping: dict[TargetStatus, HostStatus] = {
        TargetStatus.ONLINE: HostStatus.ONLINE,
        TargetStatus.OFFLINE: HostStatus.OFFLINE,
        TargetStatus.ERROR: HostStatus.UNREACHABLE,
        TargetStatus.MAINTENANCE: HostStatus.OFFLINE,
    }
    return mapping[member_status]
