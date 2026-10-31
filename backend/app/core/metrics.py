"""Instrumentation Prometheus centrale — séries HTTP, déploiements, scheduler (STORY-172).

Contrat de nommage (décision D3 de l'analyse — une seule vérité, les
dashboards/alertes référencent exactement ces noms) :

=========================  =============  ===========================================
Famille                    Série (type)   Labels
=========================  =============  ===========================================
HTTP                       ``windflow_http_requests_total`` (Counter)      ``method``, ``path`` (normalisé), ``status``
HTTP                       ``windflow_http_request_duration_seconds`` (Histogram)  ``method``, ``path``
Déploiements               ``windflow_deployments_total`` (Counter)       ``result`` ∈ ``success`` | ``failed``
Déploiements               ``windflow_deployment_duration_seconds`` (Histogram)     —
Déploiements               ``windflow_deployments_active`` (Gauge)        —
Scheduler                  ``windflow_scheduler_executions_total`` (Counter)       ``status`` ∈ ``success`` | ``failed`` | ``skipped``
 Scheduler                  ``windflow_scheduler_execution_duration_seconds`` (Histogram)  —
 Résilience                 ``windflow_circuit_breaker_state`` (Gauge)      ``name`` (0=closed, 1=half_open, 2=open)
 Résilience                 ``windflow_circuit_breaker_failures_total`` (Counter)     ``name``
 WebSocket                  ``windflow_websocket_*`` (14 séries)           inchangées (définies dans
                                                                           :mod:`app.websocket.metrics`)
 =========================  =============  ===========================================

Pourquoi instrumenter **à la source** et non via un consommateur du bus
d'événements (décision D2) : le bus STORY-162 dispatche in-memory **et**
Redis Pub/Sub selon la config → un consommateur compterait deux fois les
mêmes transitions entre instances. Les points d'instrumentation choisis
(``DeploymentService.update_status``, boucles d'exécution du moteur
scheduler) sont synchrones, uniques et testables unitairement.

Tous les helpers ``record_*`` sont **best-effort** : une métrique qui
échoue n'est jamais autorisée à casser un déploiement ou une exécution
(pattern observabilité — try/except + log, jamais de re-raise).

Aucune donnée sensible dans les labels (rules 40) : ni query string, ni
token, ni paramètre d'URL — les chemins HTTP sont normalisés via
:func:`normalize_path` (cardinalité bornée, anti-DoS mémoire).
"""

import logging
import re
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ============================================================================
# SÉRIES HTTP (collectées par le middleware Timing — décision D4)
# ============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "windflow_http_requests_total",
    "Nombre total de requêtes HTTP traitées par l'API WindFlow",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "windflow_http_request_duration_seconds",
    "Durée des requêtes HTTP (secondes) par route normalisée",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ============================================================================
# SÉRIES DÉPLOIEMENTS (instrumentées dans DeploymentService.update_status)
# ============================================================================

DEPLOYMENTS_TOTAL = Counter(
    "windflow_deployments_total",
    "Nombre total de déploiements terminés par résultat",
    ["result"],  # 'success' | 'failed'
)

DEPLOYMENT_DURATION = Histogram(
    "windflow_deployment_duration_seconds",
    "Durée de bout en bout des déploiements (created_at → transition terminale)",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0),
)

DEPLOYMENTS_ACTIVE = Gauge(
    "windflow_deployments_active",
    "Nombre de déploiements dans un statut non terminal (approximation pilotée "
    "par update_status — une création crashée avant tout update_status n'est "
    "pas comptée)",
)

# ============================================================================
# SÉRIES SCHEDULER (instrumentées dans le moteur scheduler_engine)
# ============================================================================

SCHEDULER_EXECUTIONS = Counter(
    "windflow_scheduler_executions_total",
    "Nombre total d'exécutions de tâches planifiées par statut terminal",
    ["status"],  # 'success' | 'failed' | 'skipped'
)

SCHEDULER_DURATION = Histogram(
    "windflow_scheduler_execution_duration_seconds",
    "Durée d'exécution des tâches planifiées (secondes)",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 600.0),
)

# ============================================================================
# SÉRIES RÉSILIENCE — CIRCUIT BREAKERS (STORY-251)
# ============================================================================

CIRCUIT_BREAKER_STATE = Gauge(
    "windflow_circuit_breaker_state",
    "État d'un circuit breaker (0=closed, 1=half_open, 2=open)",
    ["name"],
)

CIRCUIT_BREAKER_FAILURES = Counter(
    "windflow_circuit_breaker_failures_total",
    "Nombre total d'échecs comptés par un circuit breaker",
    ["name"],
)

# ============================================================================
# NORMALISATION DES CHEMINS (cardinalité bornée — décision D4)
# ============================================================================

# Segment UUID canonique (8-4-4-4-12 hex) → {id}
_UUID_SEGMENT_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# Segment purement numérique → {n}
_NUMERIC_SEGMENT_RE = re.compile(r"^\d+$")

# Chemin du scrape Prometheus — le middleware ne compte pas son propre scrape.
METRICS_SCRAPE_PATH = "/api/v1/metrics"


def normalize_path(path: str) -> str:
    """Normalise un chemin HTTP pour les labels de métriques.

    Substitue les segments variables par des marqueurs afin de borner la
    cardinalité des séries (un UUID ou un id numérique par requête créerait
    une série par ressource — DoS mémoire) :

    - segment UUID → ``{id}`` (ex. ``/api/v1/stacks/550e8400-e29b-…/deploy``
      → ``/api/v1/stacks/{id}/deploy``) ;
    - segment purement numérique → ``{n}`` (ex. ``/api/v1/hosts/42`` →
      ``/api/v1/hosts/{n}``) ;
    - les chemins statiques restent inchangés.

    La query string n'est **jamais** incluse : l'appelant passe
    ``request.url.path`` (jamais ``str(request.url)``) — elle peut contenir
    des tokens (rules 40). Par précaution, tout ``?`` résiduel est tronqué.
    """
    if not path:
        return path
    # Défense en profondeur : tronquer une éventuelle query string résiduelle.
    path = path.split("?", 1)[0]
    segments = path.split("/")
    normalized = [
        (
            "{id}"
            if _UUID_SEGMENT_RE.match(seg)
            else "{n}" if _NUMERIC_SEGMENT_RE.match(seg) else seg
        )
        for seg in segments
    ]
    return "/".join(normalized)


# ============================================================================
# HELPERS D'ENREGISTREMENT (best-effort — jamais de re-raise)
# ============================================================================


def record_http_request(method: str, path: str, status: str, duration: float) -> None:
    """Enregistre une requête HTTP terminée (compteur + histogramme).

    Args:
        method: Méthode HTTP (``GET``, ``POST``…).
        path: Chemin **déjà normalisé** (:func:`normalize_path`).
        status: Code de statut HTTP en chaîne (``"200"``, ``"500"``…).
        duration: Durée de traitement en secondes.
    """
    try:
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)
    except Exception:  # pragma: no cover — défense en profondeur best-effort
        logger.exception(
            "Métrique HTTP impossible (métrique ignorée): %s %s status=%s",
            method,
            path,
            status,
        )


def record_deployment_transition(
    new_status: str, duration: Optional[float], old_status: Optional[str] = None
) -> None:
    """Enregistre une transition de statut de déploiement (décision D8).

    Sémantique (appelée par ``DeploymentService.update_status``, uniquement
    quand ``old_status != new_status``) :

    - transition vers ``running`` → compteur ``result="success"`` +1, gauge
      active −1 (si l'ancien statut était non terminal) ;
    - transition vers ``failed`` → compteur ``result="failed"`` +1, gauge
      active −1 (si l'ancien statut était non terminal) ;
    - transition vers ``pending`` / ``deploying`` / ``rolling_back`` → gauge
      active +1 ;
    - transition vers un statut terminal (``running`` / ``failed`` /
      ``stopped``) avec ``duration`` fourni → observation de la durée de
      bout en bout (``now − created_at``, disponible dans les deux cas —
      ``deploy_duration_seconds`` n'est calculé qu'aux arrêts).

    Args:
        new_status: Nouveau statut (valeur de l'enum, minuscule).
        duration: Durée de bout en bout en secondes (``None`` hors
            transition terminale).
        old_status: Statut précédent (valeur de l'enum, minuscule) —
            nécessaire à la correction de la gauge active.
    """
    try:
        old = str(old_status).lower() if old_status is not None else None
        new = str(new_status).lower()

        terminal = {"running", "failed", "stopped"}
        old_was_active = old is not None and old not in terminal

        if new == "running":
            DEPLOYMENTS_TOTAL.labels(result="success").inc()
            if old_was_active:
                DEPLOYMENTS_ACTIVE.dec()
        elif new == "failed":
            DEPLOYMENTS_TOTAL.labels(result="failed").inc()
            if old_was_active:
                DEPLOYMENTS_ACTIVE.dec()
        elif new == "stopped":
            if old_was_active:
                DEPLOYMENTS_ACTIVE.dec()
        elif new in ("pending", "deploying", "rolling_back"):
            DEPLOYMENTS_ACTIVE.inc()

        if new in terminal and duration is not None and duration >= 0:
            DEPLOYMENT_DURATION.observe(duration)
    except Exception:  # best-effort : jamais casser un déploiement
        logger.exception(
            "Métrique déploiement impossible (métrique ignorée): %s → %s",
            old_status,
            new_status,
        )


def record_circuit_state(name: str, state_value: int) -> None:
    """Enregistre l'état d'un circuit breaker (STORY-251).

    Args:
        name: Nom du circuit — noms statiques (``docker_engine``,
            ``plugin_registry``) ou ``ssh:{host_id}`` (UUID d'hôte
            stable). **Jamais** de hostname libre ni de query string :
            cardinalité bornée, aucune donnée sensible en label
            (rules 40/45).
        state_value: ``0`` = closed, ``1`` = half_open, ``2`` = open.
    """
    try:
        CIRCUIT_BREAKER_STATE.labels(name=name).set(state_value)
    except Exception:  # best-effort : jamais casser un appel protégé
        logger.exception(
            "Métrique circuit breaker impossible (métrique ignorée): state=%s",
            state_value,
        )


def record_circuit_failure(name: str) -> None:
    """Incrémente le compteur d'échecs d'un circuit breaker (STORY-251).

    Args:
        name: Nom du circuit (mêmes règles de cardinalité que
            :func:`record_circuit_state`).
    """
    try:
        CIRCUIT_BREAKER_FAILURES.labels(name=name).inc()
    except Exception:  # best-effort : jamais casser un appel protégé
        logger.exception("Métrique circuit breaker impossible (métrique ignorée)")


def record_scheduler_execution(status: str, duration: Optional[float] = None) -> None:
    """Enregistre l'exécution d'une tâche scheduler (statut terminal).

    Seuls les statuts terminaux + ``skipped`` sont exposés (``running`` est
    éphémère — gauge inutile, aligné sur le domaine fermé spec 06).

    Args:
        status: ``"success"`` | ``"failed"`` | ``"skipped"``.
        duration: Durée d'exécution en secondes (absente pour ``skipped``).
    """
    try:
        SCHEDULER_EXECUTIONS.labels(status=status).inc()
        if duration is not None and duration >= 0:
            SCHEDULER_DURATION.observe(duration)
    except Exception:  # best-effort : jamais casser une exécution
        logger.exception(
            "Métrique scheduler impossible (métrique ignorée): status=%s",
            status,
        )
