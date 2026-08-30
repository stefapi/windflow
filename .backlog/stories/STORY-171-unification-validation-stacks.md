# STORY-171 : Unification de la validation des stacks — fusionner `stack_loader_service` (allégé) et la validation admin en un moteur unique + correction des bornes numériques `min/max` (P2-6 — axes B8, B9)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-6 (axes B8, B9, rapports §9) — ampleur **M**

## Description

En tant que développeur WindFlow, je veux que la validation des stack definitions passe par un **moteur unique de règles** — le même au seed de démarrage et à l'import/validate admin — avec [`stack_loader_service.py`](../../backend/app/services/stack_loader_service.py) allégé en consommateur de ce moteur, et que les bornes numériques des formulaires soient corrigées (`minimum`/`maximum` servis au formulaire, `min`/`max` ne plus être silencieusement ignorés), afin que `stacks_definitions/postgresql.yaml` cesse de ressortir « invalide » via l'API admin alors qu'il passe le seed.

**Problème constaté** ([STACK-DEFINITIONS.md § Deux chargeurs, deux validations](../../docs/technical_specs/STACK-DEFINITIONS.md), [`backend_status.md`](../../docs/backend_status.md) §5) : deux chemins de validation divergent — le seed utilise [`stack_definitions_loader.py:22`](../../backend/app/services/stack_definitions_loader.py:22) avec le schéma Pydantic `StackDefinition` **strict** ; l'admin ([`admin/stacks_management.py:16`](../../backend/app/api/v1/admin/stacks_management.py:16)) utilise [`stack_loader_service.py:18`](../../backend/app/services/stack_loader_service.py:18) avec une vérification manuelle **allégée** (métadonnées réduites, types de variables sans `integer` ni `group`) — conséquence : `postgresql.yaml` (qui utilise `integer` et `group`) se charge au démarrage mais ressort **invalide** via `GET /admin/stacks-management/definitions`. En parallèle (B9) : les bornes numériques `minimum`/`maximum` du schéma sont servies mais le formulaire lit `min`/`max` — transversal ([`stack_definitions_loader.py:22`](../../backend/app/services/stack_definitions_loader.py:22) + schemas).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Source de vérité** : le schéma Pydantic [`schemas/stack_definition.py`](../../backend/app/schemas/stack_definition.py) (« le schéma Pydantic fait foi pour la rédaction des YAML » — STACK-DEFINITIONS) ; le moteur unique = ce schéma + ses validateurs (`validate_target_type`, `enum_labels`, variables récursives `type: group`…) ;
- **Refacto** : [`stack_loader_service.py:18`](../../backend/app/services/stack_loader_service.py:18) est allégé pour consommer le moteur (parsing YAML → validation stricte partagée) ; les endpoints admin `definitions`/`validate`/`import` ([`admin/stacks_management.py:16`](../../backend/app/api/v1/admin/stacks_management.py:16)) rendent le même verdict que le seed ; [`database_seed.py`](../../backend/app/database_seed.py) inchangé fonctionnellement (il consomme déjà le loader strict) ;
- **Bornes numériques (B9)** : harmoniser le contrat servi au formulaire — `minimum`/`maximum` partout (schéma → sérialisation → DYNAMIC-FORMS/frontend) ; un `min:`/`max:` mal orthographié en YAML reste ignoré (comportement Pydantic) mais le formulaire reçoit bien les bornes quand elles existent ;
- **Ne pas régresser** (garde-fou §2.G stack definitions + Jinja2) : 16 fonctions Jinja2, macros dans les défauts, groupes récursifs, `enum_labels`, stratégies `update_if_newer`… — ne toucher qu'à la validation et aux bornes ; les fichiers YAML du dépôt doivent continuer de passer ;
- **Hors périmètre noté** : la validation Compose 20 règles avec confrontation à l'état réel du Host suit l'entité Apps/Host consolidée (Phase 2 — plan §6) — « les règles communes sont dès P2-6 » concerne le moteur de règles, pas les 20 règles Compose runtime ;
- Contrôle : l'inventaire admin `definitions` (validité par fichier) et `validate` (superadmin) doivent être cohérents avec le chargement réel.

## Critères d'acceptation (AC)

- [ ] AC 1 : **Un seul moteur de validation** : `postgresql.yaml` passe la validation API admin (`POST /admin/stacks-management/validate` → valide, inventaire `definitions` → valide) **ET** le seed de démarrage avec **les mêmes règles** — test de parité : chaque YAML du dépôt (`stacks_definitions/*.yaml`) donne le même verdict par les deux chemins.
- [ ] AC 2 : `stack_loader_service` est allégé : il ne porte plus de règles de validation propres, il délègue au schéma/moteur partagé — vérifié par revue (plus de double maintenance) et par tests de non-régression sur `import` admin (fichier invalide → rejet avec erreurs Pydantic détaillées, fichier valide → import).
- [ ] AC 3 : **Bornes numériques corrigées (B9)** : le formulaire reçoit `minimum`/`maximum` pour les variables `number`/`integer` — test : `GET /stacks/{id}` (variables sérialisées) expose les bornes attendues ; le frontend de formulaire les applique (contrôle bloquant ou avertissement selon DYNAMIC-FORMS) ; `min`/`max` ne sont plus lus nulle part.
- [ ] AC 4 : Non-régression du chargement : stratégies (`skip_existing`/`update_if_newer`/`force_update`), comparaison semver, macros Jinja2 des défauts, `regenerate-variable`, groupes récursifs et `enum_labels` fonctionnent comme avant (tests existants + nouveaux sur la parité) ; un YAML invalide reste **journalisé et sauté** sans interrompre les autres au seed.
- [ ] AC 5 : Couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [STACK-DEFINITIONS.md](../../docs/technical_specs/STACK-DEFINITIONS.md) — § **Deux chargeurs, deux validations ⚠️** (tableau comparatif, conséquence postgresql.yaml, « le schéma Pydantic fait foi »), § Variables (`minimum`/`maximum` — « écrire min/max est silencieusement ignoré »), § Validation Pydantic (comportement réel), § Workflow de développement, § Bonnes pratiques ;
- [DYNAMIC-FORMS.md](../../docs/technical_specs/DYNAMIC-FORMS.md) — mécanique des formulaires générés (consommateur des bornes — à consulter) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Validation Compose `POST /compute/stacks/{id}/validate` (renvoi : moteur auto-déclaré — les 20 règles restent Phase 2, seul le socle est concerné) ;
- [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md) — § Stack WindFlow managed (catalogue interne vs marketplace) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-6, §2.B B8/B9, §6 (« les règles communes sont dès P2-6 ») ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (`stack_loader_service` parsing, `stack_definitions_loader` chargement auto), §3.13 (admin stacks_management, 15 endpoints).

## Dépendances

- **Aucune dépendance marquée par le plan** (P2-6 « dépend de : — ») — indépendance maximale, peut avancer tôt dans la vague.
- Coordonnée avec STORY-166 (le champ `target_type` YAML et sa correspondance profils canoniques restent inchangés à ce stade) ; toucher aux schemas touche le contrat des formulaires (frontend à synchroniser si besoin).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
