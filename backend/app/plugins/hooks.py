"""SDK des hooks d'événements des plugins WindFlow (STORY-163 — T1).

Contrat public exposé aux plugins extension/hybrid pour consommer le bus
d'événements canonique (spec 11 § Système d'événements) :

- :class:`PluginEvent` : enveloppe **légère** exposée aux hooks — jamais
  l':class:`~app.core.events.Event` interne brut (réduction de surface :
  ni ``metadata``, ni contrôle de version du bus ne fuient vers les
  plugins) ;
- :class:`PluginHooks` : classe de base à sous-classer ; ses méthodes
  décorées ``@on_event("<canonique>")`` sont assemblées dans un registre
  d'instance ``hooks: dict[str, list[callable]]`` à l'instanciation ;
- :func:`on_event` : décorateur qui valide le nom **au moment du
  décorateur** — seuls les 18 noms canoniques spec 11
  (``domaine.action_passé``) sont acceptés. Les noms de transport
  WebSocket SCREAMING_SNAKE (ex. ``DEPLOYMENT_PROGRESS``) et les
  extra-canoniques (ex. ``organization.created``, sécurité
  ``host.ssh_fingerprint_*``) sont **refusés explicitement** : la
  souscription des plugins marketplace se fait uniquement sur les
  canoniques (avertissement WEBSOCKET-REAL-TIME §4.2, rules 40 —
  réduction de surface d'exposition).

Contrat d'exécution (documenté dans EVENT-BUS.md § Consommateurs
plugins) :

- les hooks sont **asynchrones et non bloquants** : ils réagissent après
  coup et ne peuvent pas refuser une action (les décisions bloquantes
  sont les gates pre-deploy de STORY-170 — hors périmètre ici) ;
- chaque hook est exécuté dans une tâche asyncio isolée avec timeout
  configurable (défaut 30 s, cf. ``plugin_hooks_timeout_seconds``) par
  le pont :class:`~app.services.plugin_hooks_service.PluginHooksService`
  — un hook lent ou en échec ne bloque jamais l'émetteur ;
- les payloads ne contiennent **jamais de secrets** (IDs/noms/statuts
  uniquement, rules 40) ; le hook reçoit une copie défensive (muter
  ``event.data`` ne corrompt pas le payload interne).

Exemple (démonstrateur complet :
``app/plugins/examples/demo_logger_hooks.py``) :

    from app.plugins.hooks import PluginHooks, PluginEvent, on_event

    class MyHooks(PluginHooks):
        @on_event("stack.deployed")
        async def on_deployed(self, event: PluginEvent) -> None:
            ...

        @on_event("deployment.failed")
        async def on_failed(self, event: PluginEvent) -> None:
            ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..core.events import CANONICAL_EVENT_NAMES
from ..core.exceptions import InvalidEventTypeNameError

#: Signature d'un hook enregistré : coroutine recevant un ``PluginEvent``.
PluginHookCallable = Callable[["PluginEvent"], Awaitable[None]]


@dataclass
class PluginEvent:
    """Événement canonique exposé aux hooks de plugins.

    Enveloppe allégée et **défensive** : ``data`` est une copie du
    payload interne (le hook peut la muter librement) et ne contient
    jamais de secrets (contrat des émetteurs, rules 40).
    """

    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    event_id: Optional[str] = None


def on_event(name: str) -> Callable[[PluginHookCallable], PluginHookCallable]:
    """Décorateur de souscription à un événement canonique du bus.

    Valide ``name`` **au moment du décorateur** (fail-fast à l'import du
    module de hooks, pas à la première émission) :

    - le nom doit faire partie des 18 canoniques spec 11
      (``CANONICAL_EVENT_NAMES``) ;
    - les noms SCREAMING_SNAKE (transport WebSocket) et les
      extra-canoniques sont refusés avec un message explicite.

    La fonction décorée est conservée **intacte** (aucun wrapping
    logique) : le registre est assemblé à l'instanciation de la
    :class:`PluginHooks` hôte, qui lit l'attribut ``__on_event__`` posé
    ici sur chaque méthode décorée.

    Args:
        name: Nom d'événement canonique (ex. ``"stack.deployed"``).

    Returns:
        Le décorateur qui marque la méthode (et la retourne inchangée).

    Raises:
        InvalidEventTypeNameError: Si ``name`` n'est pas canonique
            (SCREAMING_SNAKE, extra-canonique ou inconnu).
    """
    if name not in CANONICAL_EVENT_NAMES:
        raise InvalidEventTypeNameError(
            f"@on_event : {name!r} n'est pas un événement canonique spec 11 "
            f"(attendu : domaine.action_passé, ex. 'stack.deployed'). "
            f"Les noms SCREAMING_SNAKE sont des types de transport WebSocket "
            f"(jamais un contrat d'abonnement) et les extra-canoniques "
            f"(organization.*, user.*, sécurité…) ne sont pas transmis aux "
            f"plugins.",
            details={"received": name, "canonical": sorted(CANONICAL_EVENT_NAMES)},
        )

    def decorator(func: PluginHookCallable) -> PluginHookCallable:
        # Marqueur lu par PluginHooks.__init_subclass__/__init__ — la
        # fonction reste inchangée (pas de wrapping, stack trace nette).
        setattr(func, "__on_event__", name)
        return func

    return decorator


class PluginHooks:
    """Classe de base des consommateurs d'événements d'un plugin.

    Sous-classer et décorer les méthodes async avec
    ``@on_event("<canonique>")`` ; à l'instanciation, le registre
    ``hooks`` associe chaque nom canonique à la liste des méthodes
    abonnées (ordre de définition). Plusieurs méthodes peuvent écouter le
    même événement ; un hook peut être abonné à plusieurs événements via
    plusieurs décorations sur des méthodes distinctes.

    Le cycle de vie (enregistrement auprès du pont bus→hooks,
    exécution isolée avec timeout) est géré par
    :class:`~app.services.plugin_hooks_service.PluginHooksService`.
    """

    def __init__(self) -> None:
        self._collect_hooks()

    def _collect_hooks(self) -> None:
        """Assemble le registre d'instance depuis les méthodes décorées.

        Parcourt les attributs de la classe (ordre de définition via
        ``__dict__`` de chaque classe de la MRO, base en dernier) et
        enregistre les méthodes porteuses du marqueur ``__on_event__``.
        """
        self._hooks: Dict[str, List[PluginHookCallable]] = {}
        for klass in reversed(type(self).__mro__):
            for attr_name in klass.__dict__:
                method = getattr(self, attr_name, None)
                if method is None:
                    continue
                name = getattr(method, "__on_event__", None)
                if isinstance(name, str) and name in CANONICAL_EVENT_NAMES:
                    bound = getattr(self, attr_name)
                    self._hooks.setdefault(name, []).append(bound)

    @property
    def hooks(self) -> Dict[str, List[PluginHookCallable]]:
        """Registre en lecture seule : nom canonique → hooks abonnés."""
        return self._hooks

    @property
    def plugin_name(self) -> str:
        """Nom du plugin (id de la classe) pour les logs du pont."""
        return type(self).__name__
