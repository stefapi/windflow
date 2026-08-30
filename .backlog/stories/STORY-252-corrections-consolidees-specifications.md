# STORY-252 : Corrections consolidées des spécifications — arbitrages F1-F6 appliqués aux specs (P3-4)

**Statut :** TODO
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-4 (arbitrages F1, F2, F5, F3, F4, F6 + retombée nomenclature P2-2) — ampleur **M**

> ⚠️ **Numérotation** : cette story porte le numéro STORY-252 conformément au découpage final de la phase 5 (les éditions antérieures des epics EPIC-012/EPIC-013 et de STORY-130 la citaient comme « STORY-253 » — référence corrigée lors de l'audit de cohérence).

## Description

En tant que responsable technique WindFlow, je veux appliquer aux spécifications générales les arbitrages validés du plan de remédiation (Argon2 remplace bcrypt — F2 ; JWT 15 min — F5 ; incorporation des surfaces HORS SPEC — F3 ; suppression des références Celery — F1 ; bus asyncio/Redis Pub/Sub — F6 ; annotation de phasage du modèle directeur — F4), afin que **les specs reflètent le code livré** et qu'il ne subsiste plus d'écart « annoncé vs réel » côté documentation contractuelle.

**Problème constaté** : plusieurs specs divergent du code, soit parce que le code est meilleur (JWT 15 min réel vs 30 min spec), soit parce que le plan a arbitré (Celery abandonné, Argon2 adopté, surfaces API existantes à incorporer). Les corrections ont été **volontairement différées** jusqu'ici (répartition du plan : STORY-130, STORY-162, STORY-166, STORY-173 livrent le code et renvoient les corrections consolidées de specs à la vague P3).

## Contexte technique

*(à remplir par analyse-story)*

Modifications consolidées attendues, **chacune citée avec son chapitre** :

| Spéc | Chapitre concerné | Correction | Arbitrage |
|------|-------------------|------------|-----------|
| [`07-authentification.md`](../../docs/general_specs/07-authentification.md) | § Authentification par mot de passe | Remplacer « bcrypt (cost 12) » par **Argon2id** (passlib + argon2-cffi, upgrade au login) | F2 |
| [`07-authentification.md`](../../docs/general_specs/07-authentification.md) | § Access token (JWT) + § Configuration (`ACCESS_TOKEN_EXPIRE_MINUTES=30`) + § Exemples (`expires_in: 1800`) | Durée access token **30 min → 15 min** (le code est plus sûr) | F5 |
| [`09-api.md`](../../docs/general_specs/09-api.md) | § API Mode Infra — vue Compute + § Endpoints transverses + nouvelles sections | **Incorporation des surfaces HORS SPEC** : `/compute/*` (dont `browse`/`prune` de STORY-173), `/discovery/*`, `/stats/*`, import/export stacks, `admin/stacks-management`, `plugin_registry` — avec enveloppes/pagination conformes aux stories P1 | F3 |
| [`09-api.md`](../../docs/general_specs/09-api.md) | § API par famille › Hosts | Documenter le **double nommage `/targets` → `/hosts`** avec période d'alias de compatibilité (livré par STORY-166) | F3/F4 |
| [`04-architecture.md`](../../docs/general_specs/04-architecture.md) | § Architecture globale / § Architecture du core (runtime de tâches) | Supprimer les références **Celery** ; documenter le runtime **asyncio** unique (lifespan + scheduler engine) — si STORY-130 est fait | F1 |
| [`04-architecture.md`](../../docs/general_specs/04-architecture.md) | § Communication et temps réel › Bus d'événements internes | Préciser : interface `Bus` canonique, implémentation **in-memory (asyncio) par défaut + Redis Pub/Sub optionnel** (pas de Redis Streams à ce stade) | F6 |
| [`05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) | § Traitement asynchrone — Celery | Remplacer la section Celery par le traitement asynchrone **asyncio** ; mettre à jour § Récapitulatif des dépendances (retrait Celery, ajout argon2-cffi) | F1/F2 |
| [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) | § Vue d'ensemble + § Migration de `targets` vers `hosts` | Annoter le **déploiement phasé** du modèle directeur : étapes 1-2 livrées (tables support, `Host` + `origin`), étape 3 (`Apps`/`Machines`/`Clusters`) reportée Roadmap Phase 2 | F4 |
| [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) | § Profils d'installation / § Installation mode standard | Retirer toute référence au **worker Celery** (service compose, build) si STORY-130 est fait ; vérifier la cohérence d'`alembic upgrade head` (STORY-120) | F1 |
| [`15-securite.md`](../../docs/general_specs/15-securite.md) | § synthèse auth (si bcrypt cité) | Aligner la mention du hash sur Argon2id (cohérence avec 07) | F2 |

Éléments existants à réutiliser / contraintes :
- Les chapitres exacts (lignes) seront fixés par `analyse-story` après relecture des specs ; le tableau ci-dessus fixe le **périmètre contractualisé** ;
- ⚠️ **Validation utilisateur préalable obligatoire** (plan §7.4) : F1 et F2 sont déjà validés (acquiescement documenté lors de la création des epics P1 — cf. STORY-130) ; **F3, F4, F5, F6 restent à confirmer par l'utilisateur avant édition des specs** — si un arbitrage est refusé, ne pas l'appliquer et tracer la divergence (l'arbitrage appartient à l'utilisateur) ;
- Cohérence croisée : les exemples OpenAPI intégrés aux specs (durées de token, endpoints) doivent correspondre au code livré ;
- La nomenclature des événements (retombée de P2-2/STORY-162 : table de correspondance ancien→nouveau) est reflétée dans les specs concernées (04 § bus, 11 § liste canonique) si STORY-162 l'a documentée côté code.

## Critères d'acceptation (AC)

- [ ] AC 1 : Chaque modification de spec est **traçable** : spec ↔ chapitre ↔ arbitrage (F1/F2/F3/F4/F5/F6) ↔ story livreuse (STORY-130/160/162/166/173…) — tableau de correspondance fourni dans les notes d'implémentation.
- [ ] AC 2 : Relecture croisée specs ↔ [`backend_status.md`](../../docs/backend_status.md) (actualisé par STORY-253) : **plus d'écart « annoncé vs réel »** sur les points traités (JWT 15 min, Argon2, absence de Celery, surfaces incorporées, phasage modèle, bus d'événements).
- [ ] AC 3 : La validation utilisateur des arbitrages §7.4 (F3/F4/F5/F6) est **acquise et documentée** avant édition ; tout arbitrage refusé est tracé en divergence sans édition de spec.
- [ ] AC 4 : Les documents internes restent cohérents : liens et renvois entre specs valides (00-index, « Voir aussi »), exemples de requêtes/réponses alignés sur le code (ex. `expires_in: 900`).
- [ ] AC 5 : Revue documentaire terminée (relecture croisée) ; aucun impact code attendu — si un écart code est découvert pendant la revue, il est signalé (bug ou story) et non corrigé en silence.

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §3 (arbitrages F1-F6 détaillés), §4 P3-4, §7.4 (arbitrages nécessitant validation utilisateur), §8.1 (P3 couvre F1/F2/F5 docs) ;
- [`07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par mot de passe, § Access token (JWT), § Configuration, § Exemples de requêtes et réponses ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Conventions générales, § API Mode Infra — vue Compute, § API par famille › Hosts, § Endpoints transverses ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Architecture globale, § Architecture du core, § Communication et temps réel › Bus d'événements internes ;
- [`05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) — § Traitement asynchrone — Celery, § Récapitulatif des dépendances ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Vue d'ensemble, § Migration de `targets` vers `hosts`, § Profils canoniques ;
- [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) — § Profils d'installation, § Installation mode standard, § Configuration initiale ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — synthèse auth (cohérence Argon2) ;
- `.roo/rules/40-security.md` — bibliothèques d'auth (passlib + argon2-cffi) : les rules imposent déjà Argon2, la spec 07 s'aligne.

## Dépendances

- ⚠️ **Validation utilisateur des arbitrages §7.4** (F3, F4, F5, F6 — F1/F2 déjà acquis lors de la création de STORY-130).
- **Vagues P0-P2 terminées** — les specs reflètent le code livré : STORY-130 (F1/F2 effectifs), STORY-160 (runtime scheduler asyncio), STORY-162 (bus + nomenclature), STORY-166 (modèle Host — F4 étape 2), STORY-173 (compute — F3).
- Étroitement coordonnée avec **STORY-253** (mise à jour documentaire : `backend_status.md` et la revue croisée specs ↔ status doivent être cohérents).

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
