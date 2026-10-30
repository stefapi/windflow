"""Plugin démonstrateur — gate pre-deploy Trivy de référence (STORY-170.3).

Implémentation **simplifiée** de la gate Trivy décrite spec 11
(§ Exemple illustratif — plugin Trivy) : exemple canonique d'une gate
``deploy_hooks.pre_deploy`` écrite contre le SDK
:class:`~app.plugins.gates` (STORY-170.2), pattern
``demo_logger_hooks.py`` (STORY-163).

Modes implémentés (divergence n°5 de l'analyse STORY-170 — scan réel
hors périmètre, relève du plugin catalogue) :

- **``never`` (défaut) — réel** : aucune analyse, décision
  déterministe ``approve`` — la gate ne bloque jamais. C'est le
  comportement réellement exécuté par ce démonstrateur ;
- **tout autre critère — bloquant simulé** : ``deny`` avec raison
  descriptive marquée ``[SIMULÉ]`` et compteurs factices constants —
  permet de tester le chemin ``deny`` de bout en bout (pipeline →
  ``GateDeniedError``) sans exécuter Trivy.

Matrice de critères spec 11 (exposée via la config du manifest —
``block_criteria``) :

    ============ ===========================================
    Critère      Blocage quand
    ============ ===========================================
    never        Jamais (défaut)
    any          Toute vulnérabilité
    critical_high  >= 1 critique **ou** haute
    critical     >= 1 critique
    more_than_current  Total nouvelle image > total image courante
    ============ ===========================================

Conventions sécurité du scanner, codées en constantes (AC 1) :

- :data:`TRIVY_IMAGE` — image du scanner **épinglée par version**
  (jamais ``:latest`` : le scanner lui-même ne doit pas devenir un
  vecteur de chaîne d'approvisionnement). Documentée, non exécutée
  ici ;
- :data:`CACHE_VOLUME` — cache des bases de vulnérabilités dans un
  volume ``windflow-plugin-trivy-cache``, protégé du prune par le
  pattern ``windflow-plugin-*`` (spec 09 § Prune, STORY-173) ;
- :data:`PENDING_TAG_SUFFIX` — flux protégé par **tag temporaire**
  ``<tag>-windflow-pending`` : l'image candidate est tirée puis
  scannée sous ce tag ; en cas de refus l'image candidate est
  supprimée (le conteneur reste sur l'ancienne), en cas d'approbation
  le tag original est restauré. Flux **documenté simplifié** à ce
  stade (divergence n°5) — non exécuté par ce démonstrateur.

Configuration : le handler ne reçoit que le
:class:`~app.plugins.gates.DeployContext` (payload sans secret) — la
config du plugin arrive par variable d'environnement
``PLUGIN_CONFIG_BLOCK_CRITERIA``, posée par le core selon la
convention ``PLUGIN_CONFIG_*`` des hooks lifecycle (STORY-169.3/169.4).

Manifest d'exemple (``windflow-plugin.yml`` — matrice complète via le
champ select ``block_criteria``, liste ``config`` du schéma
``PluginManifest``) :

    name: trivy
    version: 0.1.0
    type: extension
    category: security
    config:
      - key: block_criteria
        label: Critère de blocage
        description: Bloque le déploiement quand…
        type: select
        default: never
        options:
          - {value: never, label: "Jamais (défaut)"}
          - {value: any, label: "Toute vulnérabilité"}
          - {value: critical_high, label: "≥ 1 critique ou haute"}
          - {value: critical, label: "≥ 1 critique"}
          - {value: more_than_current, label: "Total > image courante"}
    deploy_hooks:
      pre_deploy:
        handler: gates.py:pre_deploy
        timeout: 300
        on_timeout: deny

**Non enregistré par défaut** : module exemple hors montage — chargé
uniquement si copié dans le ``plugins_base_dir`` d'une installation
réelle (STORY-169). Dans un plugin installé (chargé dynamiquement hors
package), l'import SDK est absolu —
``from app.plugins.gates import DeployContext, GateDecision``.

Sécurité (rules 40) : aucune donnée sensible dans les raisons de refus
ni les logs — nom d'image, compteurs simulés et critère uniquement.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Final, Tuple

from ..gates import DeployContext, GateDecision

logger = logging.getLogger("windflow.plugins.demo")

__all__ = [
    "BLOCK_CRITERIA",
    "CACHE_VOLUME",
    "DEFAULT_BLOCK_CRITERIA",
    "PENDING_TAG_SUFFIX",
    "SIMULATED_FINDINGS",
    "TRIVY_IMAGE",
    "pre_deploy",
]

# ── Conventions sécurité scanner (AC 1 — documentées, non exécutées) ─────────

#: Image du scanner Trivy, **épinglée par version** — jamais ``:latest``
#: (le scanner ne doit pas devenir un vecteur de chaîne
#: d'approvisionnement, spec 11 § Plugin Trivy). La mise à jour est un
#: acte délibéré (ici : version de référence au moment de l'écriture).
TRIVY_IMAGE: Final[str] = "aquasec/trivy:0.58.1"

#: Volume Docker du cache des bases de vulnérabilités — protégé du
#: prune par le pattern ``windflow-plugin-*`` (spec 09 § Prune,
#: STORY-173).
CACHE_VOLUME: Final[str] = "windflow-plugin-trivy-cache"

#: Suffixe du **tag temporaire** du flux de scan protégé : l'image
#: candidate est tirée/scannée sous ``<tag>-windflow-pending`` ; refus
#: → image candidate supprimée (l'ancienne reste), approbation → tag
#: original restauré puis recréation (spec 11 § Plugin Trivy).
PENDING_TAG_SUFFIX: Final[str] = "-windflow-pending"

# ── Matrice de critères spec 11 ──────────────────────────────────────────────

#: Critères de blocage supportés (matrice spec 11) — ``never`` défaut.
BLOCK_CRITERIA: Final[Tuple[str, ...]] = (
    "never",
    "any",
    "critical_high",
    "critical",
    "more_than_current",
)

#: Critère par défaut — la gate ne bloque jamais tant que la config
#: du plugin ne dit pas le contraire (fail-safe).
DEFAULT_BLOCK_CRITERIA: Final[str] = "never"

#: Clé de la variable d'environnement portant le critère (convention
#: ``PLUGIN_CONFIG_*`` des hooks lifecycle, STORY-169.3).
_BLOCK_CRITERIA_ENV: Final[str] = "PLUGIN_CONFIG_BLOCK_CRITERIA"

#: Compteurs de vulnérabilités **factices constants** (mode bloquant
#: simulé, divergence n°5) — base descriptive de la raison de refus.
SIMULATED_FINDINGS: Final[Dict[str, int]] = {
    "critical": 2,
    "high": 5,
    "medium": 12,
    "low": 30,
}

#: Total simulé de l'image **courante** (critère ``more_than_current``
#: uniquement) — choisi pour que le total simulé de la candidate (49)
#: soit supérieur, donc bloquant.
_SIMULATED_CURRENT_TOTAL: Final[int] = 47


def _load_block_criteria() -> str:
    """Lit le critère de blocage depuis la config du plugin.

    Source : variable d'environnement ``PLUGIN_CONFIG_BLOCK_CRITERIA``
    (convention ``PLUGIN_CONFIG_*``). **Fail-safe** : valeur absente ou
    inconnue → ``never`` (la gate ne bloque jamais sur une config
    impropre — on n'invente pas un blocage).

    Returns:
        Le critère validé (toujours dans :data:`BLOCK_CRITERIA`).
    """
    raw = os.environ.get(_BLOCK_CRITERIA_ENV, DEFAULT_BLOCK_CRITERIA)
    criteria = raw.strip().lower() if isinstance(raw, str) else ""
    if criteria not in BLOCK_CRITERIA:
        logger.warning(
            "DemoTrivyGate : critère de blocage %r invalide ou absent — "
            "fail-safe vers 'never' (jamais bloquant)",
            raw,
        )
        return DEFAULT_BLOCK_CRITERIA
    return criteria


def _describe_simulated_findings(criteria: str) -> str:
    """Construit le descriptif factice correspondant au critère.

    Args:
        criteria: Critère de blocage validé (≠ ``never``).

    Returns:
        Fragment descriptif — ex. ``"2 CRITICAL, 5 HIGH"`` pour
        ``critical_high`` (le blocage simulé respecte le critère : seules
        les sévérités visées par le critère sont citées, avec un total
        simulé supérieur pour ``more_than_current``).
    """
    if criteria == "critical":
        return f"{SIMULATED_FINDINGS['critical']} CRITICAL"
    if criteria == "critical_high":
        return (
            f"{SIMULATED_FINDINGS['critical']} CRITICAL, "
            f"{SIMULATED_FINDINGS['high']} HIGH"
        )
    if criteria == "more_than_current":
        total = sum(SIMULATED_FINDINGS.values())
        return (
            f"total {total} vulnérabilités > "
            f"{_SIMULATED_CURRENT_TOTAL} (image courante)"
        )
    # "any" (et tout autre critère validé non couvert ci-dessus) :
    # toute vulnérabilité compte → toutes les sévérités citées.
    return (
        f"{SIMULATED_FINDINGS['critical']} CRITICAL, "
        f"{SIMULATED_FINDINGS['high']} HIGH, "
        f"{SIMULATED_FINDINGS['medium']} MEDIUM, "
        f"{SIMULATED_FINDINGS['low']} LOW"
    )


async def pre_deploy(ctx: DeployContext) -> GateDecision:
    """Gate pre-deploy Trivy de référence (simplifiée, divergence n°5).

    Comportement :

    - critère ``never`` (défaut, absent ou inconnu — fail-safe) →
      ``approve`` **réel** : aucune analyse, la gate ne bloque jamais ;
    - tout autre critère de la matrice spec 11 → ``deny`` **simulé** :
      raison descriptive ``"<image> : [SIMULÉ] <compteurs> (critère
      <criteria>)"`` sur la première image du contexte (court-circuit,
      comme le ferait le scan réel) — permet de tester le chemin
      ``deny`` de bout en bout sans exécuter Trivy ;
    - critère bloquant mais **aucune image** dans le contexte →
      ``approve`` : rien à scanner, rien à bloquer.

    Args:
        ctx: Contexte de déploiement (payload sans secret — rules 40).

    Returns:
        La décision ``approve``/``deny`` pour le pipeline.
    """
    criteria = _load_block_criteria()
    if criteria == DEFAULT_BLOCK_CRITERIA:
        return GateDecision.approve()

    if not ctx.images:
        # Rien à scanner (déploiement sans image résolue) — ne pas
        # bloquer sur du vide.
        return GateDecision.approve()

    # Scan réel hors périmètre (divergence n°5) : la première image
    # porte le refus simulé — mêmes information qu'un rapport réel
    # (image, sévérités visées, critère), marqué [SIMULÉ].
    image = ctx.images[0]
    detail = _describe_simulated_findings(criteria)
    return GateDecision.deny(f"{image.name} : [SIMULÉ] {detail} (critère {criteria})")
