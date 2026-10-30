"""SDK des gates pre-deploy des plugins WindFlow (STORY-170.2 — T3).

Contrat public exposé aux plugins extension/hybrid pour les **décisions
bloquantes** de déploiement (spec 11 § Hooks de déploiement) — miroir de
:mod:`app.plugins.hooks` (hooks ``@on_event``, asynchrones non bloquants) :

- :class:`DeployImage` : image résolue au moment de la gate (nom, tag,
  digest si explicitement fourni) ;
- :class:`DeployContext` : contexte d'exécution transmis au handler de
  gate (déploiement, cible, images, trigger) ;
- :class:`GateDecision` : décision retournée par le handler —
  :meth:`GateDecision.approve` / :meth:`GateDecision.deny`.

Contrat d'exécution (porté par
:class:`~app.services.plugin_gate_service.PluginGateService`, pas par ce
module) :

- **synchrone bloquant** : contrairement aux hooks ``@on_event`` (qui
  réagissent après coup), une gate **peut refuser** un déploiement — elle
  s'exécute après résolution d'images, **avant création des containers** ;
- **timeout** : chaque gate est exécutée sous ``asyncio.wait_for`` avec
  le timeout du manifest (``deploy_hooks.pre_deploy.timeout``) ou le
  défaut settings ``plugin_gate_timeout_seconds`` (spec 11 : 300 s) ;
- **comportement au timeout** : refus prudent ``GATE_TIMEOUT`` (« on ne
  déploie pas ce qu'on n'a pas pu évaluer ») sauf
  ``on_timeout: approve`` déclaré dans le manifest ;
- **comportement en erreur** (divergence n°4 de l'analyse STORY-170) :
  un handler qui lève une exception (hors timeout) est traité comme un
  ``deny`` raison ``gate_error`` — même logique prudente ;
- **aucune gate enregistrée** : le déploiement suit son cours (le core
  ne bloque jamais par défaut) ;
- **plusieurs gates** : approbation de toutes requise, exécution en
  ordre alphabétique des noms de plugins (déterminisme), premier
  ``deny`` court-circuite ;
- les payloads ne contiennent **jamais de secrets** (IDs/noms/images
  uniquement, rules 40) — la ``reason`` d'un ``deny`` est reprise dans
  les événements de déploiement, ne jamais y placer de données
  sensibles.

Divergence documentée (n°1 de l'analyse STORY-170) : le pipeline actuel
ne résout pas les digests des images (le pull est implicite dans
``deploy_container``/``deploy_compose``). ``DeployImage.digest`` n'est
alimenté que si le digest est **explicitement fourni** dans la
configuration finale (``image: nginx@sha256:…``) ; la résolution
complète tag→digest relève de STORY-174 (WorkloadAdapter).

Exemple :

    from app.plugins.gates import DeployContext, GateDecision

    async def pre_deploy(ctx: DeployContext) -> GateDecision:
        if any(":latest" in img.name for img in ctx.images):
            return GateDecision.deny("images flottantes interdites")
        return GateDecision.approve()

Déclaration manifest (``windflow-plugin.yml``) ::

    deploy_hooks:
      pre_deploy:
        handler: gates.py:pre_deploy
        timeout: 120
        on_timeout: deny
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "DeployContext",
    "DeployImage",
    "GateDecision",
]


@dataclass
class DeployImage:
    """Image déployée, au mieux des données de la configuration finale.

    Attributes:
        name: Nom de l'image, tag inclus si fourni (ex. ``nginx:1.25``).
        tag: Tag isolé (ex. ``1.25``) — ``latest`` implicite si absent.
        digest: Digest ``sha256:…`` **uniquement s'il est explicitement
            fourni** dans la configuration (divergence n°1 — la
            résolution tag→digest relève de STORY-174).
    """

    name: str
    tag: Optional[str] = None
    digest: Optional[str] = None


@dataclass
class DeployContext:
    """Contexte d'exécution d'une gate pre-deploy (spec 11).

    Payload **sans secret** (rules 40) : identifiants, noms et images
    uniquement — jamais les variables d'environnement ni la
    configuration chiffrée du déploiement.

    Attributes:
        deployment_id: ID du déploiement en cours.
        target: Cible de déploiement (``id``/``name``/``host`` au
            mieux des données du pipeline).
        images: Images qui vont être déployées (résolution finale —
            la gate s'exécute avant toute création de container).
        trigger: Origine du déploiement — ``manual`` (les autres
            valeurs spec 11 ``scheduled``/``webhook``/``batch``
            viendront avec le scheduler/batch).
    """

    deployment_id: str
    target: Dict[str, Any] = field(default_factory=dict)
    images: List[DeployImage] = field(default_factory=list)
    trigger: str = "manual"


@dataclass
class GateDecision:
    """Décision d'une gate pre-deploy — ``approve`` ou ``deny``.

    Construite via les classmethods :meth:`approve` / :meth:`deny` ;
    ``reason`` est obligatoire pour un refus (reprise dans les
    événements de déploiement — jamais de donnée sensible, rules 40).
    """

    approved: bool
    reason: Optional[str] = None

    @classmethod
    def approve(cls) -> "GateDecision":
        """Construit une décision d'approbation (le déploiement poursuit)."""
        return cls(approved=True, reason=None)

    @classmethod
    def deny(cls, reason: str) -> "GateDecision":
        """Construit un refus motivé (le déploiement échoue classiquement).

        Args:
            reason: Raison lisible du refus — reprise dans l'événement
                ``deployment.failed`` et les lignes ``deployment_events``
                (ne jamais y placer de secret, rules 40).
        """
        return cls(approved=False, reason=reason)
