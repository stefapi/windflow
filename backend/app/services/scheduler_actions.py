"""Handlers d'actions scheduler core (STORY-160.3).

Chaque action du [registre canonique](action_registry.py) (STORY-160.1)
exécutée par le [moteur](scheduler_engine.py) (STORY-160.2) est portée
par un handler conforme au contrat ``Callable[[dict], Awaitable[Any]]``
— il reçoit les paramètres **validés** (``model_dump`` du
``params_schema`` de l'action) et lève une
:class:`~app.core.exceptions.WindFlowException` en cas d'échec
(convertie en exécution ``failed`` par le moteur, jamais un crash).

Inventaire livré :

=======================  =========================================
Action                   Handler
=======================  =========================================
``host.scan``            :func:`host_scan` — rescan réel d'une cible
                         via :class:`TargetScannerService`
``compute.docker.prune`` :func:`compute_docker_prune` — prune Docker
                         protégé (dry-run défaut, liste
                         ``windflow-plugin-*`` épargnée, audit)
``stack.backup``         :func:`stack_backup` — **stub tracé** (renvoi
                         F8/initiative backup)
``admin.backup``         :func:`admin_backup` — **stub tracé** (renvoi
                         F8/initiative backup)
``notification.send``    :func:`notification_send` — **stub tracé**
                         (renvoi P2-15) ; accepte le payload d'événement
                         en paramètres additionnels et le journalise
                         **masqué**
=======================  =========================================

Sécurité (rules 40, checklist story) :

- exécution **sans contexte utilisateur** (système) — les actions
  destructrices (prune réel) ne sont posables que par des définitions
  créées par un Admin (RBAC à la création, STORY-160.1) ;
- paramètres re-validés par le schéma Pydantic de l'action **avant**
  toute consommation (défense en profondeur derrière le moteur) ;
- **audit systématique** de l'exécution réelle du prune
  (:func:`AuditService.log` — ``_sanitize_details``) ;
- logs sans ``parameters`` bruts ni credentials ; payload d'événement
  potentiellement sensible masqué avant journalisation.

Divergences tracées (notes d'implémentation de la story) :

- la story demande une terminaison ``skipped`` pour les stubs, mais
  ``mark_skipped`` n'est pas atteignable sans modifier le moteur
  (interdit — 160.2 DONE) : les handlers stub lèvent une
  :class:`ActionNotImplementedError` explicite → exécution ``failed``
  documentée « non implémentée » (jamais de succès silencieux, l'esprit
  de l'AC est préservé) ;
- STORY-173 non fusionnée à ce stade → le handler prune consomme les
  wrappers protégés locaux posés dans
  [`docker_client_service.py`](docker_client_service.py)
  (``prune_images``/``prune_volumes``).
"""

import logging
from typing import Any

from ..core.exceptions import NotFoundError, WindFlowException
from .audit_service import AuditService
from .docker_client_service import DockerClientService, PruneResult
from .target_scanner_service import TargetScannerService

logger = logging.getLogger(__name__)

# Renvois explicites des stubs (jamais de succès silencieux).
_BACKUP_STUB_REASON = "action non implémentée (renvoi F8 — initiative backup)"
_NOTIFICATION_STUB_REASON = "action non implémentée (renvoi P2-15)"


class ActionNotImplementedError(WindFlowException):
    """Levée par les handlers stub — terminaison explicite et documentée.

    Hérite de :class:`WindFlowException` (rules 30) ; interceptée par le
    moteur (STORY-160.2) et convertie en exécution ``failed`` portant la
    raison du renvoi (F8 / P2-15) — jamais de succès silencieux.
    """


def _sanitize_payload(params: dict[str, Any]) -> str:
    """Masque les valeurs du payload pour journalisation (rules 40).

    Le payload d'un événement peut véhiculer des données sensibles : on
    ne journalise que les **clés**, jamais les valeurs.
    """
    return ", ".join(sorted(params.keys())) or "(aucun)"


# ---------------------------------------------------------------------------
# host.scan — rescan réel d'une cible
# ---------------------------------------------------------------------------


async def host_scan(params: dict[str, Any]) -> dict[str, Any]:
    """Handler de ``host.scan`` : rescan de la cible et persistance.

    Résout la cible ``target_id`` en base, délègue à
    :meth:`TargetScannerService.scan_and_update_target`
    (dispatch interne localhost/remote, TOFU STRICT) et retourne un
    résultat typé borné (machines découvertes = capacités détectées,
    durée) — jamais les credentials ni le détail du scan.

    Args:
        params: Paramètres validés (``HostScanParams.model_dump()``) —
            ``target_id`` requis.

    Returns:
        Résumé typé du scan (``target_id``, ``name``, capacités
        détectées, durée).

    Raises:
        NotFoundError: Cible inexistante.
        WindFlowException: Toute erreur du scanner (exécution ``failed``
            par le moteur).
    """
    import time

    from ..database import AsyncSessionLocal
    from ..models.target import Target

    target_id = str(params["target_id"])
    started = time.monotonic()
    async with AsyncSessionLocal() as session:
        target = await session.get(Target, target_id)
        if target is None:
            raise NotFoundError("Target", target_id)
        scanner = TargetScannerService()
        try:
            updated = await scanner.scan_and_update_target(target, session)
        except Exception as exc:
            # L'échec du scanner doit rester lisible côté moteur, sans
            # jamais exposer des credentials dans le message.
            raise WindFlowException(
                f"host.scan : échec du scan de la cible " f"({type(exc).__name__})"
            ) from exc
        duration = time.monotonic() - started
        capabilities = _extract_capabilities(updated)
        logger.info(
            "host.scan : cible %s rescannée (%d capacité(s), %.3fs) — " "statut=%s",
            target_id,
            len(capabilities),
            duration,
            getattr(updated, "status", None),
        )
        return {
            "target_id": target_id,
            "name": updated.name,
            "capabilities": capabilities,
            "duration_seconds": round(duration, 3),
        }


def _extract_capabilities(target: Any) -> list[str]:
    """Extrait les noms de capacités du ``access_profile`` de la cible."""
    profile = getattr(target, "access_profile", None) or {}
    standard = profile.get("standard_capabilities") or []
    elevated = profile.get("elevated_capabilities") or []
    return sorted(set(standard) | set(elevated))


# ---------------------------------------------------------------------------
# compute.docker.prune — action destructive protégée
# ---------------------------------------------------------------------------


async def compute_docker_prune(params: dict[str, Any]) -> dict[str, Any]:
    """Handler de ``compute.docker.prune`` : prune Docker protégé.

    Garanties (sémantique STORY-173, wrappers locaux 160.3) :

    - **dry-run par défaut** : sans ``dry_run=False`` explicite dans la
      définition (posée par un Admin — RBAC à la création), aucune
      suppression n'est effectuée (estimation uniquement) ;
    - **liste protégée** : les ressources ``windflow-plugin-*`` sont
      épargnées par construction côté wrappers ;
    - **audit systématique** de l'exécution réelle (qui/quoi/quand via
      la définition — acteur système) ;
    - résultat typé borné (comptages, espace) — jamais de payload brut.

    Args:
        params: Paramètres validés (``DockerPruneParams.model_dump()``)
            — ``resource`` (``images``|``volumes``), ``dry_run`` (défaut
            ``True``), ``force`` (défaut ``False``).

    Returns:
        Le résumé :func:`PruneResult` sérialisé en dict.

    Raises:
        WindFlowException: Toute erreur du démon Docker.
    """
    resource = str(params["resource"])
    dry_run = bool(params.get("dry_run", True))
    force = bool(params.get("force", False))
    client = DockerClientService()
    try:
        if resource == "images":
            result = await client.prune_images(dry_run=dry_run, force=force)
        else:
            result = await client.prune_volumes(dry_run=dry_run, force=force)
    finally:
        await client.close()
    if not dry_run:
        await _audit_prune(result)
    logger.info(
        "compute.docker.prune : resource=%s dry_run=%s pruned=%d "
        "spared=%d reclaimed=%d bytes",
        result.resource,
        result.dry_run,
        result.pruned_count,
        result.spared_count,
        result.space_reclaimed_bytes,
    )
    return {
        "resource": result.resource,
        "dry_run": result.dry_run,
        "pruned_count": result.pruned_count,
        "space_reclaimed_bytes": result.space_reclaimed_bytes,
        "spared_count": result.spared_count,
    }


async def _audit_prune(result: PruneResult) -> None:
    """Audite une exécution réelle de prune (action destructive).

    Best-effort (:func:`AuditService.log` ne lève jamais) ; ``details``
    passe par ``_sanitize_details`` — seuls comptages et volumes de
    données sont persistés, jamais de paramètre brut.
    """
    await AuditService.log(
        "scheduler.compute.docker.prune",
        resource_type="docker",
        resource_id=result.resource,
        details={
            "dry_run": result.dry_run,
            "pruned_count": result.pruned_count,
            "space_reclaimed_bytes": result.space_reclaimed_bytes,
            "spared_count": result.spared_count,
            "protected_prefix": "windflow-plugin-*",
        },
    )


# ---------------------------------------------------------------------------
# Stubs tracés — terminaison explicite (jamais de succès silencieux)
# ---------------------------------------------------------------------------


async def stack_backup(params: dict[str, Any]) -> None:
    """Handler stub de ``stack.backup`` (renvoi F8 — initiative backup).

    Journalise l'appel (paramètres masqués — clés uniquement) puis lève
    :class:`ActionNotImplementedError` : l'exécution se termine en
    ``failed`` avec la raison explicite du renvoi.
    """
    logger.info(
        "stack.backup : stub appelé (paramètres masqués : %s) — %s",
        _sanitize_payload(params),
        _BACKUP_STUB_REASON,
    )
    raise ActionNotImplementedError(f"stack.backup : {_BACKUP_STUB_REASON}")


async def admin_backup(params: dict[str, Any]) -> None:
    """Handler stub de ``admin.backup`` (renvoi F8 — initiative backup)."""
    logger.info(
        "admin.backup : stub appelé (paramètres masqués : %s) — %s",
        _sanitize_payload(params),
        _BACKUP_STUB_REASON,
    )
    raise ActionNotImplementedError(f"admin.backup : {_BACKUP_STUB_REASON}")


async def notification_send(params: dict[str, Any]) -> None:
    """Handler stub de ``notification.send`` (renvoi P2-15).

    Accepte le payload d'événement en paramètres additionnels (trigger
    événement — STORY-160.3 tâche 6) et le journalise **masqué** : les
    valeurs ne sont jamais journalisées, seules les clés le sont
    (payload potentiellement sensible, rules 40).
    """
    logger.info(
        "notification.send : stub appelé (paramètres masqués : %s) — %s",
        _sanitize_payload(params),
        _NOTIFICATION_STUB_REASON,
    )
    raise ActionNotImplementedError(f"notification.send : {_NOTIFICATION_STUB_REASON}")


# ---------------------------------------------------------------------------
# Enregistrement au registre (Tâche 5)
# ---------------------------------------------------------------------------


def register_scheduler_actions() -> None:
    """Enregistre les handlers de ce module au registre canonique.

    Pattern du registre (STORY-160.1) : remplacement de la définition
    par une copie ``dataclasses.replace`` portant le handler, puis
    remplacement dans ``_REGISTRY`` — les actions réelles
    (``host.scan``, ``compute.docker.prune``) passent ``implemented``
    à ``True`` **déjà posé par 160.1**, les stubs restent
    ``implemented=False`` (renvois F8/P2-15 tracés) tout en portant un
    handler exécutable dont la terminaison est documentée.

    Idempotent (réenregistrement sûr) ; appelé à l'import du module.
    """
    from dataclasses import replace

    from . import action_registry as registry

    handlers = {
        "host.scan": host_scan,
        "compute.docker.prune": compute_docker_prune,
        "stack.backup": stack_backup,
        "admin.backup": admin_backup,
        "notification.send": notification_send,
    }
    for name, handler in handlers.items():
        definition = registry.get_action(name)
        registry._REGISTRY[name] = replace(definition, handler=handler)
    logger.debug(
        "Handlers scheduler enregistrés au registre : %s",
        ", ".join(sorted(handlers)),
    )
