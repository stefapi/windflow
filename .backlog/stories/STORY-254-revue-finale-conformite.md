# STORY-254 : Revue finale de conformité — audit specs ↔ code de bout en bout et tableau de conformité (clôture du plan)

**Statut :** TODO
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** Clôture du plan de remédiation (au-delà de P3-5 : écran de contrôle final annoncé en notes de conception de l'epic) — ampleur **M**

> ⚠️ **Numérotation** : cette story porte le numéro STORY-254 conformément au découpage final de la phase 5 (les éditions antérieures citaient « STORY-254 » pour le rangement documentaire — la phase 5 a réordonné : 253 = rangement documentaire, 254 = revue finale de conformité).

## Description

En tant que responsable technique WindFlow, je veux exécuter une **revue de conformité de bout en bout** après toutes les vagues de remédiation (P0-P3) : ré-exécuter une passe d'analyse d'écart specs ↔ code selon la même méthode que le rapport initial, vérifier que tous les écarts traités sont **clos ou explicitement reportés** (Roadmap), et produire un **tableau de conformité final** (domaine → statut CONFORME / REPORTÉ / ÉCART RÉSIDUEL), afin de certifier qu'il ne reste **aucun écart bloquant non tracé** à l'issue du cycle de remédiation.

**Problème constaté** : le rapport d'analyse d'écart initial (repris dans [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §2) a déclenché 36 stories sur 4 vagues ; rien ne garantit aujourd'hui qu'après exécution, chaque écart identifié est bien résolu, reporté ou assumé — cette story est l'**écran de contrôle final** du plan complet (cf. notes de conception de l'epic : « la revue croisée sert de validation finale du plan complet »).

## Contexte technique

*(à remplir par analyse-story)*

Méthode de la passe d'audit (même méthode que le rapport initial) :

1. **Re-dérouler l'analyse d'écart par domaine** — reprendre les sections du rapport initial (§1 API, §2 Authentification, §3 RBAC, §4 Modèle de données, §5 Workloads/compute, §6 Architecture/event-driven, §7 Sécurité, §8 WebSocket, §9 Stacks definitions, §10 Plugins, §11 IA, §12 Automatisation, §14 Déploiement, §15 Observabilité, §16 Tests) et pour chacune confronter spec ↔ code livré (inspection réelle : endpoints, modèles, tests, configuration) ;
2. **Croiser avec le backlog** : chaque écart du rapport initial doit être couvert par une story DONE (epics EPIC-011→014) ou explicitement reporté (plan §6 hors périmètre → [`Roadmap.md`](../../docs/Roadmap.md)) ;
3. **Produire le tableau de conformité final** : `domaine → statut` parmi :
   - **CONFORME** — l'écart est résolu et vérifié (test/inspection à l'appui) ;
   - **REPORTÉ** — l'écart est explicitement hors périmètre, tracé dans la Roadmap ou une initiative dédiée (ex. F8 backup, Keycloak, Vault, VMs/K8s…) ;
   - **ÉCART RÉSIDUEL** — écart restant non prévu : doit être **tracé** (nouvelle story ou bug) — critère de done : **zéro écart bloquant non tracé** (les écarts résiduels mineurs acceptés sont tracés en WONT_FIX/divergence documentée) ;
4. **Vérifier les écrans de contrôle** des vagues : grep Celery (STORY-130.2), import-check code mort (STORY-250), matrice RBAC (STORY-122), couverture par domaine ≥ 80 % (rules 35) ;
5. **Formaliser le rapport final** : document de conformité (dans `docs/` ou mise à jour du plan de remédiation avec statuts), présentant le tableau, les preuves d'exécution et les reportés.

Contraintes :
- Cette story est une **revue** : elle ne corrige pas de code — tout écart découvert est tracé (story/bug) et priorisé, jamais corrigé en silence ;
- S'appuyer sur [`backend_status.md`](../../docs/backend_status.md) régénéré par STORY-253 et sur les specs corrigées par STORY-252 (prérequis) ;
- Les arbitrages non validés par l'utilisateur (ex. F3/F4/F5/F6 si refusés en STORY-252) apparaissent comme ÉCART RÉSIDUEL **tracé à arbitrage utilisateur**, pas comme des oublis.

## Critères d'acceptation (AC)

- [ ] AC 1 : Une passe d'analyse d'écart specs ↔ code a été ré-exécutée sur **tous les domaines du rapport initial** (même méthode, mêmes sections de référence), en s'appuyant sur le code réellement fusionné — pas sur les intentions des stories.
- [ ] AC 2 : Le **tableau de conformité final** est produit (domaine → CONFORME / REPORTÉ / ÉCART RÉSIDUEL, avec preuve/référence pour chaque ligne) et publie dans la documentation projet.
- [ ] AC 3 : Chaque item P0 (5), P1 (11), P2 (15) et P3 (5) du plan est couvert : story DONE vérifiée, ou divergence/report tracé ; les items du plan §6 (hors périmètre) sont confirmés reportés dans [`Roadmap.md`](../../docs/Roadmap.md).
- [ ] AC 4 : **Zéro écart bloquant non tracé** : tout écart résiduel découvert pendant l'audit fait l'objet d'une story, d'un bug ou d'une décision WONT_FIX documentée (l'arbitrage d'acceptation appartient à l'utilisateur).
- [ ] AC 5 : Le rapport final est daté, référencé depuis le plan de remédiation (statut « exécuté ») et le backlog (kanban) ; la CI reste verte (aucune modification de code).

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — document integral : §2 (axes A-G = rapport d'écart repris), §3 (arbitrages), §4 (vagues P0-P3 et critères de done), §5 (dépendances), §6 (hors périmètre → reportés attendus), §8.2 (correspondance rapport ↔ plan) ;
- [`backend_status.md`](../../docs/backend_status.md) — état réel post-remédiation (régénéré par STORY-253 — prérequis) ;
- [`Roadmap.md`](../../docs/Roadmap.md) — destination des reportés (Phase 2 : VMs/K8s/Apps/Clusters/marketplace ; Phase 5 : IA, check-updates) ;
- [`docs/general_specs/`](../../docs/general_specs/README.md) — l'ensemble des 19 specs (objet de la confrontation) ;
- `.roo/rules/35-testing-quality-gates.md` — cibles de couverture à vérifier (≥ 80 %, 95 % chemins critiques auth/RBAC/déploiement).

## Dépendances

- **Toutes les vagues P0-P2 terminées** (EPIC-011/012/013) et les stories P3 sœurs exécutées : STORY-250 (purge), STORY-251 (CircuitBreaker), **STORY-252** (specs corrigées — prérequis direct), **STORY-253** (`backend_status.md` régénéré — prérequis direct).
- Cette story **clôt le plan** : elle ne peut être finalisée qu'en dernier.

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
