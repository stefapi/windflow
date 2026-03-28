"""
Helpers utilitaires pour le module Compute.

Fonctions pures réutilisables : formatage mémoire, parsing de ports,
extraction d'uptime et filtrage des vues compute.
"""

from typing import Optional

from ..schemas.compute import (
    ContainerPortMapping,
    DiscoveredItem,
    StandaloneContainer,
    StackWithServices,
)


def format_memory(bytes_val: int) -> str:
    """
    Formate une valeur en bytes vers une string lisible.

    Examples:
        >>> format_memory(103809024)
        '99M'
        >>> format_memory(1073741824)
        '1.0G'
        >>> format_memory(0)
        '0M'
    """
    if bytes_val <= 0:
        return "0M"
    kb = bytes_val / 1024
    if kb < 1024:
        return f"{kb:.0f}K"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.0f}M"
    gb = mb / 1024
    return f"{gb:.1f}G"


def parse_ports(ports_data: list[dict]) -> list[ContainerPortMapping]:
    """
    Parse les ports Docker vers ContainerPortMapping.

    Docker retourne: ``[{"IP": "0.0.0.0", "PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}]``

    Seuls les ports avec PublicPort ET PrivatePort sont retenus.

    Args:
        ports_data: Liste brute des ports depuis l'API Docker.

    Returns:
        Liste de ContainerPortMapping filtrée.
    """
    result: list[ContainerPortMapping] = []
    for p in ports_data:
        if p.get("PublicPort") and p.get("PrivatePort"):
            result.append(
                ContainerPortMapping(
                    host_ip=p.get("IP", "0.0.0.0"),
                    host_port=p["PublicPort"],
                    container_port=p["PrivatePort"],
                    protocol=p.get("Type", "tcp"),
                )
            )
    return result


def extract_uptime(status: str) -> Optional[str]:
    """
    Extrait l'uptime depuis le champ status Docker.

    Examples:
        >>> extract_uptime("Up 2 hours")
        'Up 2 hours'
        >>> extract_uptime("Exited (0) 3 minutes ago")
        >>> extract_uptime("")

    Args:
        status: Champ status brut de Docker.

    Returns:
        L'uptime si le container est "Up", sinon None.
    """
    if status.startswith("Up"):
        return status
    return None


def apply_filters(
    managed_stacks: list[StackWithServices],
    discovered_items: list[DiscoveredItem],
    standalone_list: list[StandaloneContainer],
    type_filter: Optional[str] = None,
    technology: Optional[str] = None,
    target_id_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[StackWithServices], list[DiscoveredItem], list[StandaloneContainer]]:
    """
    Applique les filtres sur les 3 sections de la vue compute.

    Les filtres sont combinés (AND) : chaque filtre actif réduit le résultat.
    Le filtre ``type_filter`` vide les sections non concernées.
    Le filtre ``search`` est insensible à la casse sur le nom.

    Args:
        managed_stacks: Stacks managées WindFlow.
        discovered_items: Projets Compose découverts.
        standalone_list: Containers standalone.
        type_filter: "managed", "discovered" ou "standalone".
        technology: Filtre par technologie exacte.
        target_id_filter: Filtre par target_id.
        status_filter: Filtre par status (running, stopped, etc.).
        search: Recherche textuelle insensible à la casse.

    Returns:
        Tuple des 3 listes filtrées.
    """
    # Filtre de type : vide les sections non concernées
    if type_filter:
        if type_filter == "managed":
            discovered_items = []
            standalone_list = []
        elif type_filter == "discovered":
            managed_stacks = []
            standalone_list = []
        elif type_filter == "standalone":
            managed_stacks = []
            discovered_items = []

    # Recherche textuelle
    if search:
        search_lower = search.lower()
        managed_stacks = [s for s in managed_stacks if search_lower in s.name.lower()]
        discovered_items = [d for d in discovered_items if search_lower in d.name.lower()]
        standalone_list = [c for c in standalone_list if search_lower in c.name.lower()]

    # Filtre par statut
    if status_filter:
        managed_stacks = [s for s in managed_stacks if s.status == status_filter]
        standalone_list = [c for c in standalone_list if c.status == status_filter]

    # Filtre par target
    if target_id_filter:
        managed_stacks = [s for s in managed_stacks if s.target_id == target_id_filter]
        discovered_items = [d for d in discovered_items if d.target_id == target_id_filter]
        standalone_list = [c for c in standalone_list if c.target_id == target_id_filter]

    # Filtre par technologie
    if technology:
        managed_stacks = [s for s in managed_stacks if s.technology == technology]
        discovered_items = [d for d in discovered_items if d.technology == technology]

    return managed_stacks, discovered_items, standalone_list
