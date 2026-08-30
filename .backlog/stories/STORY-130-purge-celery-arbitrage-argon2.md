# STORY-130 : Purge Celery + arbitrage Argon2 — suppression du double runtime fantôme et migration Argon2id (P1-11 + P1-10)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-11 (axes F1 + E10, rapports §6/§9.1) + P1-10 (arbitrage F2, rapport §2) — ampleur **S+S**

## Description

En tant que mainteneur de WindFlow, je veux (1) **purger le double runtime Celery fantôme** (`celery_app.py`, `Dockerfile.worker`, cibles Makefile associées) pour assumer un runtime asyncio unique (arbitrage F1 validé), et (2) **documenter l'upgrade path Argon2id** en migrant le hachage des mots de passe de bcrypt vers Argon2id via l'upgrade automatique au login (arbitrage F2 : le code est correct, c'est la spec 07 qui doit être corrigée), afin d'éliminer la surface de test/déploiement morte et d'aligner le hashage sur les rules sécurité.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2, §6, §9.1, §14) : [`celery_app.py`](../../backend/app/celery_app.py:19) est complet mais **jamais importé** — le runtime réel est asyncio ([`DeploymentOrchestrator`](../../backend/app/services/deployment_orchestrator.py:21), boucle de santé lifespan, [`background_tasks.py`](../../backend/app/tasks/background_tasks.py)) ; la dépendance Celery n'est même pas installable via Poetry. Côté hash : le code utilise passlib/bcrypt alors que les rules 40 imposent argon2-cffi — l'arbitrage F2 tranche : **migrer le code** vers Argon2id et corriger la spec 07.

## Contexte technique

*(à remplir par analyse-story)*

**Partie 1 — Purge Celery (P1-11, F1/E10)** :
- Supprimer : [`backend/app/celery_app.py`](../../backend/app/celery_app.py:19), [`infrastructure/docker/Dockerfile.worker`](../../infrastructure/docker/Dockerfile.worker) ;
- Retirer : cibles Makefile associées (`docker-build-worker`, ett toute référence worker) + services `windflow-worker` des compose files (docker-compose.yml, -dev, -extensions, -prod) — attention à ne pas casser les compose sains ;
- Vérifier l'absence de références résiduelles : CI (workflows `.gitea/`), scripts (`scripts/`, `dev/`), `env.example`, documentation (docs générales) — les specs 04/05 sont couvertes par STORY-252 (P3-4, EPIC-014) : **ne pas les modifier ici** (répartition du plan) ;
- Écran de contrôle : `grep -ri celery` sur le dépôt (hors backlog/docs de planification) → aucun résultat ;
- La tâche de cleanup logs (Beat schedule 2h/jour) disparaît avec le fichier : s'assurer qu'aucun comportement essentiel n'était réellement porté par Celery (constat : rien — jamais importé) ; la purge des refresh tokens expirés (STORY-123) et de l'audit (STORY-125) passe par des jobs asyncio documentés dans ces stories.

**Partie 2 — Argon2id (P1-10, F2)** :
- [`user_service.py`](../../backend/app/services/user_service.py:20) : l'upgrade automatique au login **existe déjà** (`verify_and_update_user`) — s'appuyer dessus avec passlib + `argon2-cffi` (dépendance à ajouter — justifiée par l'arbitrage) ; paramètres Argon2id documentés (alignés rules 40 : argon2-cffi) ;
- Compatibilité : login d'un utilisateur au hash bcrypt → vérification bcrypt puis **re-hash Argon2id** écrit en base ; **aucun reset de mot de passe requis** ; double lecture pendant la transition ;
- **Spec 07 à corriger** : remplacer « bcrypt (cost 12) » par Argon2id (chapitres Core vs plugin, flow login, synthèse 15 § Auth) — la mission autorise « répercuter dans la spec dans cette story ou la P3 selon le plan » : le plan place les corrections consolidées en **P3-4 (STORY-252)** — cette story documente donc l'upgrade path et **réserve** la modification consolidée des specs 07/15 à STORY-252 (signalée en divergence contrôlée dans l'epic) ;
- Comptes seed/admin créés après migration : hashés Argon2id dès la création ([`database_seed.py`](../../backend/app/database_seed.py)) ;
- `PUT /auth/password` (STORY-129) et register hashent en Argon2id.

## Critères d'acceptation (AC)

- [ ] AC 1 : [`celery_app.py`](../../backend/app/celery_app.py:19) et [`Dockerfile.worker`](../../infrastructure/docker/Dockerfile.worker) sont supprimés ; les cibles Makefile et services compose liés au worker sont retirés ; `make docker-build` ne build plus d'image worker ; `grep -ri celery` (code, CI, scripts, env, docs hors backlog/specs P3) ne retourne **aucune référence** ; CI et tests verts.
- [ ] AC 2 : La dépendance `argon2-cffi` est ajoutée (Poetry) ; le login d'un utilisateur bcrypt → **hash re-haché Argon2id en base après login** (test) ; **aucun reset de mot de passe requis** (tous les comptes existants continuent de se connecter) ; comptes nouvellement créés hashés Argon2id.
- [ ] AC 3 : L'upgrade path est **documenté** (notes d'implémentation + mention dans la story) : paramètres Argon2id, transition double lecture, renvoi de la correction consolidée des specs 07/15 à STORY-252 (P3-4) avec les arbitrages F5 (JWT 15 min) et F1 (specs 04/05) ;
- [ ] AC 4 : `make lint` + `make backend-test` verts ; non-régression complète des flux auth (login username/email, register, refresh, disable_auth).

## Références spécification

- [`docs/general_specs/04-architecture.md`](../../docs/general_specs/04-architecture.md) + [`docs/general_specs/05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) — runtime de tâches (specs à corriger en P3-4, référencées ici pour traçabilité F1) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § hashage (bcrypt cost 12 — à corriger en Argon2id via STORY-252 conformément à l'arbitrage F2), § flow de login (upgrade au login) ;
- `.roo/rules/40-security.md` — bibliothèques d'authentification : passlib + **argon2-cffi** (hash des mots de passe) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §9.1 (Celery jamais importé), §2 (bcrypt vs rules), §14 (deux lignes « Celery non intégré ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §3 F1 (asyncio assumé) et F2 (Argon2, corriger le code), §4 P1-10/P1-11, §7.4 arbitrages 1-2 (validés).

## Dépendances

- **Arbitrages F1 et F2 validés par l'utilisateur** (plan §7.4 — validation acquise lors de la création des epics).
- Interaction : STORY-123 (purge refresh tokens expirés en asyncio — ne pas réintroduire Celery pour ça), STORY-129 (hash du nouveau mot de passe), STORY-252 (EPIC-014, corrections consolidées de specs 04/05/07/15).

## Sous-stories

*(section réservée — ampleur S+S, découpe non prévue ; les deux volets sont indépendants et peuvent être traités séparément si l'analyse le juge utile)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
