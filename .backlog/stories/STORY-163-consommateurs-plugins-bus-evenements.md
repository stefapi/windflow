# STORY-163 : Consommateurs plugins du bus — hooks `@on_event`, enregistrement de `deployment_notifications` et émission de `DEPLOYMENT_PROGRESS` (P2-2, partie consommateurs — axe C6)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-2 (axe C6, rapports §6/§10) — ampleur **M**

## Description

En tant que développeur de plugins WindFlow, je veux que les hooks `@on_event` des extension/hybrid plugins consomment réellement les ~18 événements canoniques émis par le bus (STORY-162), que le module interne `deployment_notifications` — défini mais jamais enregistré — soit enregistré, et que le type transport `DEPLOYMENT_PROGRESS` — défini mais jamais émis — soit effectivement émis par le pipeline de déploiement, afin que la promesse « les plugins réagissent aux événements core » (spec 11) devienne vraie au lieu d'un contrat dormant.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §10.1](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md), [`backend_status.md`](../../docs/backend_status.md) §8.5) : aucun plugin ne consomme les événements canoniques (C6) ; [`deployment_notifications.py`](../../backend/app/websocket/plugins/deployment_notifications.py) n'est pas importé par [`plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) (seuls `audit_logger`, `deployment_monitor`, `subscription` sont enregistrés) — son auto-enregistrement à l'import n'a jamais lieu ; `DEPLOYMENT_PROGRESS` est défini dans [`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py), écouté par `deployment_monitor`/`deployment_notifications` et le handler frontend [`useDeploymentWebSocket.ts`](../../frontend/src/composables/useDeploymentWebSocket.ts) existe — mais **aucun code ne l'émet** (`broadcast_deployment_progress()` sans appelant, aucune méthode `emit_progress_update`).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Socle hooks plugins** : [`plugin_lifecycle_service.py`](../../backend/app/services/plugin_lifecycle_service.py:40) exécute les hooks lifecycle ; le mécanisme d'abonnement `@on_event` (spec 11 § Implémentation des hooks, classe `PluginHooks`) doit être câblé sur le bus canonique de STORY-162 — les hooks sont **asynchrones et non bloquants** (ils réagissent après coup, ne peuvent pas refuser une action — les décisions bloquantes sont les gates de STORY-170) ;
- **Enregistrement** : importer/enregistrer `deployment_notifications` dans [`websocket/plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) — c'est un module de broadcast interne (G38), sans rapport avec les plugins marketplace : ne pas confondre les deux familles ;
- **Émission de `DEPLOYMENT_PROGRESS`** : décision du plan « émis ou retiré » → **émettre** (le handler frontend existe et l'attend) ; ajouter une émission de progression structurée (étapes `pulling`/`stopping`/`removing`/`creating`/`starting` du pipeline de déploiement, cf. batch update spec 09) via `broadcast_deployment_progress()` existant + une méthode d'émission côté service (le pattern `emit_status_change` de [`deployment_events.py`](../../backend/app/services/deployment_events.py:22) sert de modèle) ;
- ⚠️ Ne pas brancher un workflow, trigger scheduler ou plugin marketplace sur les noms SCREAMING_SNAKE — la souscription des plugins marketplace se fait **uniquement** sur les événements canoniques `domaine.action_passé` (avertissement spec WEBSOCKET §4.2) ;
- Un plugin d'exemple (extension) consommant au moins 2 événements canoniques (`stack.deployed`, `deployment.failed`) sert de démonstrateur testable ;
- Garde-fou §2.G : ne pas casser l'architecture des modules de broadcast internes.

## Critères d'acceptation (AC)

- [ ] AC 1 : Le mécanisme `@on_event("<événement canonique>")` branche les hooks de plugins sur le bus ; test : un hook abonné à `stack.deployed` est appelé avec les données de l'événement quand une stack est déployée ; un hook lent ou en échec **ne bloque jamais** l'émetteur (isolation d'exécution, erreur journalisée).
- [ ] AC 2 : `deployment_notifications` est enregistré au démarrage (import effectif dans `plugins/__init__.py`) et reçoit les événements de déploiement — test : un changement de statut de déploiement déclenche son traitement (notification/broadcast selon son contrat actuel).
- [ ] AC 3 : `DEPLOYMENT_PROGRESS` est **effectivement émis** par le pipeline de déploiement aux étapes clés — test : un déploiement de test produit des messages `DEPLOYMENT_PROGRESS` reçus par les abonnés (et le consommateur frontend documenté), avec payload d'étape cohérent (`step`, progression) ; plus aucun « type défini jamais émis » ni handler frontend mort.
- [ ] AC 4 : Un plugin extension démonstrateur consomme ≥ 2 événements canoniques (ex. `stack.deployed` → action, `deployment.failed` → journalisation/notification) — testé unitairement sans déploiement marketplace complet ; les noms SCREAMING_SNAKE ne sont utilisés que côté transport WS, jamais comme contrat d'abonnement.
- [ ] AC 5 : Non-régression des modules internes existants (`audit_logger`, `deployment_monitor`, `subscription`) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Système d'événements (liste canonique, « les extension/hybrid plugins s'y abonnent »), § Implémentation des hooks (`PluginHooks`, `@on_event`, exemple Traefik), § Bus d'événements (interface identique pour les plugins quel que soit le mode) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Triggers (exemple `deployment.failed` → `notification.send`), § Plugin n8n (triggers sur événements canoniques) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (messages `DEPLOYMENT_*`, batch update : étapes `pulling`→`starting`, `progress`) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §4.2-4.3 (couche transport vs canonique, tableau d'articulation), §6 (handler frontend `handleProgress` jamais alimenté), §10.1 (`DEPLOYMENT_PROGRESS` jamais émis, `deployment_notifications` non enregistré — recommandation) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-2 (B7 : « `DEPLOYMENT_PROGRESS` émis ou retiré, `deployment_notifications` enregistré »), §2.C C6 ;
- [`backend_status.md`](../../docs/backend_status.md) — §8.5 (4 plugins WS, `deployment_notifications` non importé), §9.4 (bridge seul handler réel).

## Dépendances

- **STORY-162** (bus canonique + nomenclature) — prérequis direct.
- Interagit avec la story notifications P2-15 (canal in-app/webhook consommateur d'événements) et **STORY-160** (triggers événement du scheduler consomment les mêmes événements).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
