# STORY-122 : Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-2 application (axes A2 + B15, rapport §3) — ampleur **XL**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que chaque endpoint du backend soit protégé par une dépendance `require_role("viewer"|"operator"|"admin"|"super_admin")` appliquant la hiérarchie des 4 rôles et la matrice de permissions de la spec 08, afin qu'un Viewer ne puisse plus exécuter les ~40 endpoints Docker destructeurs ni aucune action modifiante aujourd'hui ouverts à tout utilisateur authentifié.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §3, §7, §14) : la seule protection existante est [`require_superuser`](../../backend/app/auth/dependencies.py:23) ; tout endpoint non marqué « superadmin » est accessible à **tout utilisateur authentifié** — dont les 40 endpoints de [`docker.py`](../../backend/app/api/v1/docker.py:69) (suppression de conteneurs, prune, etc.). Le système policies legacy ([`helper/permissions.py`](../../backend/app/helper/permissions.py:64)) est du code mort non importé, à ne **pas** ressusciter (décision E1 du plan).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Hiérarchie cible : `{"viewer": 0, "operator": 1, "admin": 2, "super_admin": 3}` — spec 08 § Dépendance FastAPI ; `require_role("operator")` = rôle **minimum** ;
- `AuthorizationService` (spec 08 § Implémentation) : superadmin → tous droits ; résolution du rôle via `user_organizations` (posée par STORY-121) avec **cache TTL 300 s** (Redis en mode standard, mémoire en mode léger) ; catégories d'actions lecture/opération/gestion alignées sur la matrice ;
- Application aux **~110 endpoints existants** (~20 fichiers routers, cf. [`api/v1/`](../../backend/app/api/v1/__init__.py:28)) : lecture → `viewer` (tout utilisateur authentifié) ; opérations (start/stop/restart/deploy/rollback/exec/console…) → `operator`+ ; gestion (create/update/delete, hosts, plugins, users, orgs…) → `admin`+ ; paramètres système globaux / admin instance → `super_admin` ;
- Garde-fous §2.G du plan : **aucune suppression d'endpoint** du module Docker (RBAC par-dessus) ; login username/email + register non régressés ; mode dev `disable_auth` (auto-login superadmin) préservé ;
- Mapping non cassant déjà posé par STORY-121 (superuser → Super_Admin, autres → Operator) : vérifier comportementalement ici ;
- Item **le plus invasif du plan** (risque §7.3) : découpage impératif par router lors de l'analyse, avec la matrice de rôles spec 08 comme critère d'acceptation ;
- La cible de couverture 95 % sur les chemins critiques auth/RBAC (rules 35) devient réaliste à l'issue de cette story.

## Critères d'acceptation (AC)

- [x] AC 1 : La dépendance `require_role(minimum_role)` (nouveau module `auth/rbac.py` ou équivalent) est implémentée avec la hiérarchie viewer < operator < admin < super_admin ; `User.is_superadmin` = tous droits sur toutes les organisations ; le rôle est résolu via `user_organizations` avec **cache TTL 300 s** (Redis standard / mémoire léger) — test : un changement de rôle est pris en compte au plus tard 300 s après (invalidation au changement de rôle testée). *(STORY-122.1)*
- [x] AC 2 : **Tous** les endpoints existants (~110, ~20 routers : users, targets, stacks, deployments, docker — dont les 40 endpoints —, plugins + plugin_registry, organizations, schedules, admin/*, compute, discovery, stats, import/export…) sont protégés par `require_role(...)` conformément à la matrice spec 08 ; vérifié par une **matrice rôle×endpoint représentative** en tests : viewer → `403` sur `DELETE /docker/containers/{id}` et sur les POST/PUT/DELETE de gestion ; operator → `200` sur les actions opérationnelles et `403` sur la gestion ; admin → gestion `200` dans son organisation ; `super_admin` requis sur l'admin instance (`admin/*`, création d'organisation…). *(122.2-122.6 volets + 122.7 vérification exhaustive structurelle : 140 routes, 0 non protégée)*
- [x] AC 3 : **Protections d'escalade** : le **dernier superadmin** n'est ni démotable ni désactivable (`409`/`400` avec message explicite) ; un Admin ne peut pas modifier un rôle supérieur ou égal au sien ni se promouvoir ; le rôle `Super_Admin` n'est pas attribuable via l'API d'organisations (rôle système). *(STORY-122.4)*
- [x] AC 4 : Isolation organisationnelle : un utilisateur n'accède pas aux ressources d'une organisation à laquelle il n'appartient pas (`403`/`404` selon la matrice) — vérifié sur un échantillon représentatif (stacks, targets, deployments). *(STORY-122.3 + consolidation 122.7)*
- [x] AC 5 : Tests de sécurité obligatoires écrits et passants : `401` sans token, `403` rôle insuffisant, `404` ressource étrangère — sur un échantillon par router ; non-régression : `disable_auth` fonctionne en dev, login username/email + register non régressés, aucun endpoint Docker supprimé ; couverture ≥ 80 % sur les modules touchés, **viser 95 %** sur auth/RBAC. *(122.2-122.6 échantillons + 122.7 consolidation : rbac.py 100 %, authorization_service 98 %)*

## Références spécification

- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — **intégral** : § Rôles, § Matrice des permissions (référence unique), § RBAC par famille, § Implémentation (modèle, `AuthorizationService`, cache TTL 300 s, `require_role`), § Permissions sur les endpoints plugin (lecture Viewer, écriture Operator, config Admin), § Gestion des utilisateurs ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Sécurité → RBAC (« permissions vérifiées après authentification, par famille »), § Administration (Super Admin) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Principes (« moindre privilège, rôle par défaut Viewer »), § Sécurité du Docker socket (« un Viewer ne peut pas démarrer un container ») ;
- `.roo/rules/40-security.md` — checklist AuthN/AuthZ (RBAC côté API = source de vérité) et tests de sécurité obligatoires ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §3 (~110 endpoints, rôles actuels auth/superadmin, docker.py 40 endpoints), §7.4 (`require_superuser` seul), §14 (« Pas de RBAC granulaire ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-2, §2.A A2, §2.B B15, §7.3 (découpage par router), §7.1 (mapping non cassant).

## Dépendances

- **STORY-121** (modèle `user_organizations` + rôles + migration des données) — et transitivement STORY-120.
- Est un prérequis de : STORY-124 (RBAC s'applique aux clés API) ; conditionne le modèle Hosts et `/compute` élargi en P2 (STORY-163, STORY-170).

## Sous-stories

> Découpe proactive réalisée par `split-story` le 2026-09-08 (complexité détectée par `analyse-story` Phase 2.5 : ~14 tâches / ~26 fichiers / ~118 endpoints vérifiés — les 4 critères remplis). Découpage par groupes de routers exigé par le plan (§7.3). L'exploration complète (inventaire des 35+15+15+10+9+8+8+6+13+5+11 routes, patterns, marqueurs intérimaires) est embarquée dans le contexte technique de chaque sous-story.

- [x] STORY-122.1 : Socle RBAC — `auth/rbac.py`, hiérarchie 4 rôles et cache TTL 300 s — Couvre AC 1
- [x] STORY-122.2 : Application RBAC au module Docker — 35 endpoints — Couvre AC 2 (volet Docker), AC 5 (échantillon)
- [x] STORY-122.3 : Application RBAC — stacks, deployments, schedules et isolation organisationnelle — Couvre AC 2 (volet), AC 4
- [x] STORY-122.4 : Application RBAC — organizations, users et protections d'escalade — Couvre AC 3, AC 2 (volet)
- [x] STORY-122.5 : Application RBAC — plugins, registry, targets et endpoints de lecture — Couvre AC 2 (volet)
- [x] STORY-122.6 : Application RBAC — admin instance et canaux WebSocket — Couvre AC 2 (volet)
- [x] STORY-122.7 : RBAC — matrice transverse, non-régression et couverture — Couvre AC 2 (exhaustivité), AC 5

**Ordre d'implémentation :** 122.1 (socle, bloquante) → 122.2 → 122.3 → 122.4 → 122.5 → 122.6 (parallélisables entre elles) → 122.7 (transverse, après toutes).

**Répartition des AC :** AC 1 → 122.1 · AC 3 → 122.4 · AC 4 → 122.3 · AC 5 → 122.7 (consolidation) avec échantillons par router dans 122.2-122.6 · AC 2 (transverse par nature) → volets 122.2-122.6, vérification exhaustive finale 122.7.

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 7/7 sous-stories terminées ✅
- [x] STORY-122.1 : Socle RBAC — require_role, hiérarchie, cache TTL
- [x] STORY-122.2 : RBAC Docker (35 endpoints)
- [x] STORY-122.3 : RBAC stacks/deployments/schedules + isolation
- [x] STORY-122.4 : RBAC organizations/users + protections d'escalade
- [x] STORY-122.5 : RBAC plugins/registry/targets/lectures
- [x] STORY-122.6 : RBAC admin instance + WebSocket
- [x] STORY-122.7 : Matrice transverse + non-régression + couverture

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.

## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.

## Notes d'implémentation (clôture)

**Date :** 2026-09-12

Story close via ses 7 sous-stories (toutes DONE) — voir les notes d'implémentation de chaque sous-story pour le détail (fichiers, décisions, divergences, tests).

**Bilan :**
- 140 routes API protégées par `require_role(...)` conformément à la matrice spec 08 (test structurel anti-oubli en CI : `test_rbac_exhaustivite.py`) ;
- 5 canaux WebSocket matriciels (terminal operator+, 4 autres viewer+) avec refus 1008 avant accept ;
- Protections d'escalade (dernier superadmin, admin vs rôles supérieurs) et isolation organisationnelle vérifiées ;
- Couverture chemins critiques : `auth/rbac.py` 100 %, `authorization_service.py` 98 % (cible 95 % dépassée) ;
- Non-régression : 1376 tests unitaires verts, `disable_auth`/login username+email/register/logout préservés, aucun endpoint supprimé (§2.G).
