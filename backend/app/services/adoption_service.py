"""
Service d'adoption d'objets découverts.

Fonctions métier pour :
- Collecter les données détaillées d'un objet découvert (GET adoption-data)
- Exécuter l'adoption : créer Stack + Deployment en DB, labeliser les containers
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import yaml
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.deployment import Deployment, DeploymentStatus
from ..models.stack import Stack
from ..schemas.adoption import (
    AdoptionEnvVar,
    AdoptionNetwork,
    AdoptionPortMapping,
    AdoptionRequest,
    AdoptionResponse,
    AdoptionServiceData,
    AdoptionVolume,
    AdoptionWizardData,
)
from ..services.container_classifier import (
    LABEL_COMPOSE_PROJECT,
    LOCAL_TARGET_ID,
    LOCAL_TARGET_NAME,
)
from ..services.docker_client_service import DockerClientService

logger = logging.getLogger(__name__)

# Heuristique : clés d'environnement considérées comme secrètes
_SECRET_PATTERNS = re.compile(
    r"(?i)(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE|CREDENTIAL|AUTH_KEY|ACCESS_KEY)"
)


# =============================================================================
# Helpers
# =============================================================================


def _is_secret_env(key: str) -> bool:
    """Retourne True si la clé d'environnement semble être un secret."""
    return bool(_SECRET_PATTERNS.search(key))


def _parse_env_from_inspect(env_list: list[str]) -> list[AdoptionEnvVar]:
    """
    Parse la liste Env depuis l'inspect Docker.

    Args:
        env_list: Liste de chaînes "KEY=VALUE" depuis ContainerDetail.Config.Env

    Returns:
        Liste de AdoptionEnvVar avec détection automatique des secrets.
    """
    result: list[AdoptionEnvVar] = []
    for entry in env_list:
        if "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        result.append(
            AdoptionEnvVar(
                key=key,
                value=value,
                is_secret=_is_secret_env(key),
            )
        )
    return result


def _parse_volumes_from_inspect(mounts: list[dict]) -> list[AdoptionVolume]:
    """
    Parse les volumes depuis l'inspect Docker (Mounts).

    Args:
        mounts: Liste de dicts depuis ContainerDetail.Mounts

    Returns:
        Liste de AdoptionVolume.
    """
    result: list[AdoptionVolume] = []
    for m in mounts:
        mount_type = m.get("Type", "bind")
        source = m.get("Source") or m.get("Name")
        destination = m.get("Destination", "")
        mode = m.get("RW", True) and "rw" or "ro"
        result.append(
            AdoptionVolume(
                source=source,
                destination=destination,
                mode=mode,
                type=mount_type,
            )
        )
    return result


def _parse_networks_from_inspect(
    network_settings: dict,
) -> list[AdoptionNetwork]:
    """
    Parse les réseaux depuis l'inspect Docker (NetworkSettings.Networks).

    Args:
        network_settings: Dict NetworkSettings complet.

    Returns:
        Liste de AdoptionNetwork.
    """
    result: list[AdoptionNetwork] = []
    networks = network_settings.get("Networks", {})
    for name, info in networks.items():
        # Le réseau par défaut a un nom qui finit par "default" ou est "bridge"
        is_default = name in ("bridge", "host", "none") or "default" in name
        result.append(
            AdoptionNetwork(
                name=name,
                driver=(
                    info.get("Driver", "bridge") if isinstance(info, dict) else "bridge"
                ),
                is_default=is_default,
            )
        )
    return result


def _parse_ports_from_inspect(
    network_settings: dict,
) -> list[AdoptionPortMapping]:
    """
    Parse les ports depuis l'inspect Docker (NetworkSettings.Ports).

    Args:
        network_settings: Dict NetworkSettings complet.

    Returns:
        Liste de AdoptionPortMapping.
    """
    result: list[AdoptionPortMapping] = []
    ports = network_settings.get("Ports", {})
    for container_port_proto, bindings in ports.items():
        if not bindings:
            continue
        # Parser "80/tcp" → container_port=80, protocol=tcp
        parts = container_port_proto.split("/")
        container_port = int(parts[0]) if parts else 0
        protocol = parts[1] if len(parts) > 1 else "tcp"

        for binding in bindings:
            result.append(
                AdoptionPortMapping(
                    host_ip=binding.get("HostIp", "0.0.0.0"),
                    host_port=int(binding.get("HostPort", 0)),
                    container_port=container_port,
                    protocol=protocol,
                )
            )
    return result


def _generate_compose_preview(services: list[AdoptionServiceData]) -> str:
    """
    Génère un aperçu docker-compose.yml depuis les données collectées.

    Args:
        services: Liste des services détectés.

    Returns:
        Chaîne YAML du docker-compose.yml.
    """
    compose: dict = {"version": "3.8", "services": {}}

    for svc in services:
        svc_def: dict = {"image": svc.image}

        if svc.env_vars:
            svc_def["environment"] = {ev.key: ev.value for ev in svc.env_vars}

        if svc.volumes:
            svc_def["volumes"] = [
                (
                    f"{v.source}:{v.destination}:{v.mode}"
                    if v.source
                    else f"{v.destination}:{v.mode}"
                )
                for v in svc.volumes
            ]

        if svc.ports:
            svc_def["ports"] = [
                (
                    f"{p.host_ip}:{p.host_port}:{p.container_port}"
                    if p.host_ip != "0.0.0.0"
                    else f"{p.host_port}:{p.container_port}"
                )
                for p in svc.ports
                if p.host_port > 0
            ]

        if svc.networks:
            non_default = [n.name for n in svc.networks if not n.is_default]
            if non_default:
                svc_def["networks"] = non_default

        # Nettoyer les clés vides
        svc_def = {k: v for k, v in svc_def.items() if v}
        svc_def["image"] = svc.image  # toujours présent

        compose["services"][svc.name] = svc_def

    return yaml.dump(compose, default_flow_style=False, sort_keys=False)


# =============================================================================
# Fonction 1 : GET adoption-data
# =============================================================================


async def get_adoption_data(
    db: AsyncSession,
    org_id: str,
    item_type: str,
    item_id: str,
) -> AdoptionWizardData:
    """
    Collecte les données détaillées d'un objet découvert pour le wizard.

    Args:
        db: Session de base de données.
        org_id: ID de l'organisation.
        item_type: Type d'objet (container, composition, helm_release).
        item_id: ID de l'objet (ex: compose:myproject@local).

    Returns:
        AdoptionWizardData avec inventaire complet et aperçu Compose.

    Raises:
        HTTPException 503: Si Docker n'est pas accessible.
        HTTPException 404: Si l'objet découvert n'est pas trouvé.
    """
    docker: Optional[DockerClientService] = None

    try:
        # Créer un client Docker
        docker = DockerClientService()
        if not await docker.ping():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Docker n'est pas accessible. Vérifiez que Docker est en cours d'exécution.",
            )

        # Lister tous les containers
        all_containers = await docker.list_containers(all=True)

        # Parser item_id pour extraire le projet/target
        project_name: Optional[str] = None
        target_id = LOCAL_TARGET_ID
        target_name = LOCAL_TARGET_NAME

        if item_type == "composition" and item_id.startswith("compose:"):
            # Format : "compose:<project>@<target>"
            parts = item_id[len("compose:") :]
            if "@" in parts:
                project_name, target_id = parts.split("@", 1)
            else:
                project_name = parts

        # Filtrer les containers du projet
        matched_containers = []
        if project_name:
            for c in all_containers:
                compose_project = c.labels.get(LABEL_COMPOSE_PROJECT, "")
                if compose_project == project_name:
                    matched_containers.append(c)
        elif item_type == "container":
            # Container unique : chercher par ID dans item_id
            # Format possible : "container:<id>@<target>"
            cid = item_id
            if cid.startswith("container:"):
                cid = cid[len("container:") :]
            if "@" in cid:
                cid, _ = cid.split("@", 1)
            for c in all_containers:
                if c.id == cid or c.id.startswith(cid):
                    matched_containers.append(c)
                    break

        if not matched_containers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Objet découvert '{item_id}' introuvable. "
                "Il a peut-être été supprimé ou Docker a été redémarré.",
            )

        # Construire les données de chaque service
        services: list[AdoptionServiceData] = []
        for c in matched_containers:
            env_vars: list[AdoptionEnvVar] = []
            volumes: list[AdoptionVolume] = []
            networks: list[AdoptionNetwork] = []
            ports: list[AdoptionPortMapping] = []

            # Inspecter le container pour les détails
            try:
                detail = await docker.inspect_container(c.id)

                # Env vars depuis Config.Env
                env_list = detail.get("Config", {}).get("Env", [])
                env_vars = _parse_env_from_inspect(env_list)

                # Volumes depuis Mounts
                mounts = detail.get("Mounts", [])
                volumes = _parse_volumes_from_inspect(mounts)

                # Réseaux depuis NetworkSettings
                ns = detail.get("NetworkSettings", {})
                networks = _parse_networks_from_inspect(ns)
                ports = _parse_ports_from_inspect(ns)

            except Exception as e:
                logger.warning(f"Impossible d'inspecter le container {c.id}: {e}")

            services.append(
                AdoptionServiceData(
                    name=c.name,
                    image=c.image,
                    status=c.state,
                    env_vars=env_vars,
                    volumes=volumes,
                    networks=networks,
                    ports=ports,
                    cpu_percent=0.0,
                    memory_usage="0M",
                )
            )

        # Déterminer le nom du projet
        name = project_name or matched_containers[0].name
        technology = "docker-compose" if project_name else "docker"

        # Générer l'aperçu Compose
        generated_compose = _generate_compose_preview(services)

        return AdoptionWizardData(
            discovered_id=item_id,
            name=name,
            type=item_type,  # type: ignore
            technology=technology,
            target_id=target_id,
            target_name=target_name,
            services=services,
            generated_compose=generated_compose,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la collecte des données d'adoption: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erreur lors de la collecte des données: {str(e)}",
        )
    finally:
        if docker:
            await docker.close()


# =============================================================================
# Fonction 2 : POST adopt
# =============================================================================


async def adopt_discovered_item(
    db: AsyncSession,
    org_id: str,
    request: AdoptionRequest,
) -> AdoptionResponse:
    """
    Adopte un objet découvert en le convertissant en stack managée.

    Étapes :
    1. Vérifier l'existence de l'objet découvert (via Docker)
    2. Vérifier l'unicité du nom de stack
    3. Créer un Stack en DB
    4. Créer un Deployment en DB (status=running car containers actifs)
    5. Best-effort : tenter de labeliser les containers

    Args:
        db: Session de base de données.
        org_id: ID de l'organisation.
        request: Données de la requête d'adoption.

    Returns:
        AdoptionResponse avec les IDs créés.

    Raises:
        HTTPException 404: Objet découvert introuvable.
        HTTPException 409: Nom de stack déjà pris.
        HTTPException 503: Docker indisponible.
    """
    # 1. Vérifier l'unicité du nom de stack
    existing = await db.execute(
        select(Stack).where(
            Stack.name == request.stack_name,
            Stack.organization_id == org_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Une stack nommée '{request.stack_name}' existe déjà.",
        )

    # 2. Collecter les containers Docker correspondants
    docker: Optional[DockerClientService] = None
    container_ids: list[str] = []
    target_id = request.target_id or LOCAL_TARGET_ID
    compose_content = request.compose_content

    try:
        docker = DockerClientService()
        if not await docker.ping():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Docker n'est pas accessible.",
            )

        all_containers = await docker.list_containers(all=True)

        # Filtrer les containers de l'objet
        if request.item_type == "composition":
            project_name = None
            item_id = request.discovered_id
            if item_id.startswith("compose:"):
                parts = item_id[len("compose:") :]
                if "@" in parts:
                    project_name, _ = parts.split("@", 1)
                else:
                    project_name = parts

            if project_name:
                for c in all_containers:
                    if c.labels.get(LABEL_COMPOSE_PROJECT) == project_name:
                        container_ids.append(c.id)

        elif request.item_type == "container":
            cid = request.discovered_id
            if cid.startswith("container:"):
                cid = cid[len("container:") :]
            if "@" in cid:
                cid, _ = cid.split("@", 1)
            for c in all_containers:
                if c.id == cid or c.id.startswith(cid):
                    container_ids.append(c.id)
                    break

        if not container_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Objet découvert '{request.discovered_id}' introuvable.",
            )

        # Si pas de compose_content fourni, générer un aperçu
        if not compose_content:
            # Collecter les infos basiques pour le template
            services_data: list[AdoptionServiceData] = []
            for c in all_containers:
                if c.id in container_ids:
                    services_data.append(
                        AdoptionServiceData(
                            name=c.name,
                            image=c.image,
                            status=c.state,
                        )
                    )
            compose_content = _generate_compose_preview(services_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la vérification Docker: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erreur Docker: {str(e)}",
        )

    # 3. Créer la Stack en DB
    stack_id = str(uuid4())
    now = datetime.now(timezone.utc)

    new_stack = Stack(
        id=stack_id,
        name=request.stack_name,
        description=f"Stack adoptée depuis objet découvert ({request.item_type})",
        template={"version": "3.8", "services": {}},  # Template initial
        variables={},
        organization_id=org_id,
        version="1.0.0",
        category="adopted",
        tags=["adopted", request.item_type],
        deployment_name=request.stack_name,
        created_at=now,
        updated_at=now,
    )
    db.add(new_stack)

    # 4. Créer le Deployment en DB
    deployment_id = str(uuid4())
    new_deployment = Deployment(
        id=deployment_id,
        stack_id=stack_id,
        target_id=target_id,
        organization_id=org_id,
        name=request.stack_name,
        status=DeploymentStatus.RUNNING,  # Les containers tournent déjà
        config={"compose_content": compose_content},
        variables={
            "volume_strategy": request.volume_strategy.value,
            "network_strategy": request.network_strategy.value,
        },
        deployed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(new_deployment)

    await db.commit()
    await db.refresh(new_stack)
    await db.refresh(new_deployment)

    # 5. Best-effort : tenter de labeliser les containers
    # Note: Docker ne permet pas de modifier les labels d'un container en cours
    # d'exécution via POST /containers/{id}/update. Les labels sont figés.
    # Les labels WindFlow seront posés au prochain cycle de déploiement.
    logger.info(
        f"Adoption réussie: stack_id={stack_id}, deployment_id={deployment_id}, "
        f"containers={container_ids}. Les labels WindFlow seront posés au prochain déploiement."
    )

    # Fermer le client Docker
    if docker:
        await docker.close()

    return AdoptionResponse(
        success=True,
        stack_id=stack_id,
        stack_name=request.stack_name,
        deployment_id=deployment_id,
        message=(
            f"Objet '{request.discovered_id}' adopté avec succès sous le nom "
            f"'{request.stack_name}'. {len(container_ids)} container(s) associé(s)."
        ),
    )
