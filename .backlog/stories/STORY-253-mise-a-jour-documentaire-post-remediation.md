# STORY-253 : Mise à jour documentaire post-remédiation — `backend_status.md`, rules `.roo`, CHANGELOG (P3-5)

**Statut :** TODO
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-5 (rangement documentaire) — ampleur **S/M**

> ⚠️ **Numérotation** : cette story porte le numéro STORY-253 conformément au découpage final de la phase 5 (les éditions antérieures citaient « STORY-254 » pour le rangement documentaire — la phase 5 a réordonné : 253 = rangement documentaire, 254 = revue finale de conformité).

## Description

En tant que développeur WindFlow, je veux régénérer et mettre à jour la documentation d'état du projet après exécution des vagues P0-P2 — [`docs/backend_status.md`](../../docs/backend_status.md) (inventaire réel du code), les rules `.roo` pertinentes (40-sécurité, 20-architecture, 35-tests) et le CHANGELOG — afin que la documentation interne décrive **l'état réel post-remédiation** et ne perpétue plus d'écart « annoncé vs réel ».

**Problème constaté** : [`backend_status.md`](../../docs/backend_status.md) (daté du 30/08/2026) décrit l'état **pré-remédiation** : RBAC binaire, credentials en clair, Celery fantôme, scheduler CRUD sans moteur, absence d'Alembic, zones de test à zéro… Après les vagues P0-P2, la majorité de ces constats sera obsolète. Les rules `.roo` contiennent des mentions devenues fausses (ex. 05-tech-stack : « Celery prévu mais pas encore intégré », mention Dockerfile.worker) et le CHANGELOG ne trace pas encore la remédiation.

## Contexte technique

*(à remplir par analyse-story)*

Périmètre documentaire consolidé :

**1. [`docs/backend_status.md`](../../docs/backend_status.md)** — régénération après les vagues P0-P2 :
- Reprendre la structure du document existant (inventaire par module, endpoints, architecture, sécurité, tests & couverture, points forts/points faibles §17-18) ;
- Mettre à jour chaque section impactée : auth/RBAC (STORY-121/122), migrations (STORY-120), secrets (STORY-103), scheduler (STORY-160/161), bus événements (STORY-162/163), WebSocket (STORY-164/165), modèle Host (STORY-166), plugins réels (STORY-169/170), observabilité (STORY-172)… ;
- Les sections devenues fausses (ex. « résilience non câblée » si STORY-251 l'a câblée) sont corrigées ou supprimées ;
- Dater la nouvelle édition et tracer le lien avec le plan de remédiation exécuté.

**2. Rules `.roo/rules/`** — mises à jour ciblées :
- [`40-security.md`](../../.roo/rules/40-security.md) : vérifier l'alignement post-remédiation (Argon2 effectif, secrets chiffrés, brute-force, audit trail) ;
- [`20-architecture-and-api.md`](../../.roo/rules/20-architecture-and-api.md) : mettre à jour si les endpoints/contrats ont changé (enveloppes, pagination, `/hosts`, dépréciation `/auth/me` de STORY-250) ;
- [`35-testing-quality-gates.md`](../../.roo/rules/35-testing-quality-gates.md) : actualiser les zones de test (les « zones zéro » comblées par les vagues P2) ;
- [`05-tech-stack.md`](../../.roo/rules/05-tech-stack.md) : retirer les mentions Celery/Dockerfile.worker si STORY-130 fait (⚠️ la skill `update-rules` peut être utilisée pour synchroniser les rules avec le code réel).

**3. [`CHANGELOG.md`](../../CHANGELOG.md)** :
- Tracer la remédiation backend : vagues P0-P2 (et P3 au fil de leur finalisation), breaking changes éventuels (enveloppes API STORY-126, dépréciations `/auth/me`, `/targets`).

Éléments existants à réutiliser / contraintes :
- **Ne pas modifier les specs générales** (`docs/general_specs/`) — c'est le rôle de STORY-252 ;
- La mise à jour de `backend_status.md` doit refléter **le code réellement fusionné** (vérifications par inspection, pas par copie des intentions des stories) ;
- Coordination STORY-252 ↔ STORY-253 : la revue croisée specs ↔ backend_status.md (AC 2 de STORY-252) n'est possible que si ce document est à jour — séquencer 253 avant ou avec 252.

## Critères d'acceptation (AC)

- [ ] AC 1 : [`backend_status.md`](../../docs/backend_status.md) régénéré/actualisé : chaque section obsolète corrigée (RBAC, secrets, Alembic, scheduler, bus, WS, modèle, plugins, observabilité, tests), nouvelle édition datée, plus aucun constat « pré-remédiation » non signalé comme résolu.
- [ ] AC 2 : Les rules `.roo` ciblées (40, 20, 35, 05) sont à jour : plus de mention « Celery prévu mais non intégré » si STORY-130 fait, structure des endpoints/contrats alignée, zones de test réelles — cohérence rules ↔ code vérifiée.
- [ ] AC 3 : [`CHANGELOG.md`](../../CHANGELOG.md) trace la remédiation (vagues, fonctionnalités, breaking changes : enveloppes API, dépréciations `/auth/me` et `/targets`).
- [ ] AC 4 : Relecture finale : plus d'écart « annoncé vs réel » sur les points traités par la remédiation (critère de done du plan P3-5) ; les écarts résiduels éventuels sont explicitement listés (renvoi vers STORY-254 pour le tableau de conformité final).
- [ ] AC 5 : Documentation uniquement — aucun code modifié ; la CI documentaire (liens internes valides) reste verte.

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P3-5 (critère de done : « Relecture : plus d'écart "annoncé vs réel" sur les points traités »), §8.1 (P3-5 rangement) ;
- [`backend_status.md`](../../docs/backend_status.md) — document à régénérer (structure actuelle à reprendre) ;
- `.roo/rules/01-Project-management.md` — documentation projet (`doc/`) et workflow backlog ;
- `.roo/rules/05-tech-stack.md`, `20-architecture-and-api.md`, `35-testing-quality-gates.md`, `40-security.md` — rules à synchroniser ;
- [`CHANGELOG.md`](../../CHANGELOG.md) — format existant à respecter.

## Dépendances

- **Vagues P0-P2 terminées** (et idéalement STORY-250/251 purgées) : le document décrit l'état final du code.
- Coordonnée avec **STORY-252** (corrections de specs) — la revue croisée de STORY-252 dépend du `backend_status.md` actualisé par cette story.
- Prépare **STORY-254** (revue finale de conformité : le tableau de conformité s'appuie sur ce document à jour).

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
