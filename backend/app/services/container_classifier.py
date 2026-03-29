"""
Classifier de containers Docker.

Logique pure de classification par labels Docker — aucune I/O, aucun async.
Fonctions testables unitairement sans mock.

Stratégie de classification (par labels Docker) :
  windflow.managed=true                  → managed (groupé par stack_id)
  com.docker.compose.project (sans wf)   → discovered (groupé par projet)
  aucun des deux                         → standalone
"""

from collections import defaultdict

from ..services.docker_client_service import ContainerInfo

# Labels WindFlow posés sur les containers lors du déploiement
LABEL_WINDFLOW_MANAGED = "windflow.managed"
LABEL_WINDFLOW_STACK_ID = "windflow.stack_id"

# Label Docker Compose standard
LABEL_COMPOSE_PROJECT = "com.docker.compose.project"
LABEL_COMPOSE_CONFIG_FILES = "com.docker.compose.project.config_files"

# Placeholder pour la target locale (Docker sur Unix socket)
LOCAL_TARGET_ID = "local"
LOCAL_TARGET_NAME = "Local Docker"


def is_windflow_managed(labels: dict[str, str]) -> bool:
    """
    Retourne True si le container est géré par WindFlow.

    Un container est considéré managé si le label ``windflow.managed``
    est présent et vaut ``"true"`` (insensible à la casse).

    Args:
        labels: Labels du container Docker.

    Returns:
        True si le container est managé WindFlow.
    """
    return labels.get(LABEL_WINDFLOW_MANAGED, "").lower() == "true"


def is_compose_project(labels: dict[str, str]) -> bool:
    """
    Retourne True si le container fait partie d'un projet Docker Compose.

    Détecté via la présence du label ``com.docker.compose.project``.

    Args:
        labels: Labels du container Docker.

    Returns:
        True si le container appartient à un projet Compose.
    """
    return LABEL_COMPOSE_PROJECT in labels


def classify_containers(
    containers: list[ContainerInfo],
) -> tuple[
    dict[str, list[ContainerInfo]],  # managed: {stack_id: [containers]}
    dict[str, list[ContainerInfo]],  # discovered: {project_name: [containers]}
    list[ContainerInfo],  # standalone: [containers]
]:
    """
    Classe les containers Docker en 3 catégories.

    Priorité : ``windflow.managed`` > ``compose`` > ``standalone``.
    Un container ayant à la fois le label WindFlow et Compose sera
    classé dans ``managed`` (WindFlow prioritaire).

    Args:
        containers: Liste brute des containers Docker.

    Returns:
        Tuple (managed_by_stack_id, discovered_by_project, standalone_list).
    """
    managed: dict[str, list[ContainerInfo]] = defaultdict(list)
    discovered: dict[str, list[ContainerInfo]] = defaultdict(list)
    standalone: list[ContainerInfo] = []

    for c in containers:
        if is_windflow_managed(c.labels):
            stack_id = c.labels.get(LABEL_WINDFLOW_STACK_ID, "unknown")
            managed[stack_id].append(c)
        elif is_compose_project(c.labels):
            project = c.labels[LABEL_COMPOSE_PROJECT]
            discovered[project].append(c)
        else:
            standalone.append(c)

    return dict(managed), dict(discovered), standalone
