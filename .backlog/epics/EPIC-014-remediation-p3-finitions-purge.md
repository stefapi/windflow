# EPIC-014 : P3 — Finitions & purge (remédiation backend)

**Statut :** TODO
**Priorité :** Basse

## Vision

Nettoyer et clôturer la remédiation : purger le code mort (permissions legacy, croniter vendored non consommé, abstractions inutiles, stub workflows, print debug, duplication `/users/me` vs `/auth/me`), statuer sur le `CircuitBreaker` décoratif (câbler ou supprimer), consolider les corrections de specs décidées par les arbitrages F1-F8 (JWT 15 min, suppression Celery, Argon2, incorporation HORS SPEC, phasage modèle, nomenclature événements), mettre à jour la documentation projet (`backend_status.md`, rules `.roo`, CHANGELOG) pour refléter l'état post-remédiation, et clore le cycle par une **revue finale de conformité** specs ↔ code. Cette vague P3 du plan de remédiation ([`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4) garantit qu'il ne reste aucun écart « annoncé vs réel ».

Spécifications de référence : corrections consolidées sur [`07-authentification.md`](../../docs/general_specs/07-authentification.md), [`09-api.md`](../../docs/general_specs/09-api.md), [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) (selon arbitrages F2/F3/F5/F6), complétées par [`04-architecture.md`](../../docs/general_specs/04-architecture.md) et [`05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) (arbitrage F1), plus les rules `.roo/rules`.

## Description

Chaque item P3 du plan de remédiation devient une story — le découpage final (phase 5) fusionne P3-1 et P3-3 dans STORY-250 et ajoute la revue finale de conformité en STORY-254 :

| Story | Item plan | Objectif | Ampleur |
|-------|-----------|----------|---------|
| STORY-250 | P3-1 + P3-3 (E1, E3, E4, E6, E7, E8, E2 partiel, E9) | Purge du code mort : `permissions.py`, `croniter.py` (conditionnel à STORY-160), `DatabaseManager` si non consommé, stub `workflows.py`, `litellm_service.py`, print debug `main.py:12`, `HealthCheck` de `resilience.py` + **dépréciation `/auth/me`** au profit de `/users/me` (headers `Deprecation`/`Sunset` + note OpenAPI) | M |
| STORY-251 | P3-2 (E2) | CircuitBreaker — câbler sur les appels externes (Docker via `WorkloadAdapter`, SSH, registre plugins) avec seuils configurés, ou supprimer le module ; métrique exposée | M |
| STORY-252 | P3-4 (F1, F2, F5, F3, F4, P2-2) | Corrections de specs consolidées : JWT 15 min, suppression Celery, Argon2, incorporation HORS SPEC, annotation phasage modèle, nomenclature événements — specs 04/05/06/07/09/15/16 | M |
| STORY-253 | P3-5 | Rangement documentaire : mise à jour `backend_status.md` + rules `.roo` (40-sécurité, 20-architecture, 35-tests, 05-stack si Celery retiré) + CHANGELOG | S/M |
| STORY-254 | Clôture du plan | Revue finale de conformité : re-passe d'analyse d'écart specs ↔ code (même méthode que le rapport initial), tableau de conformité final (CONFORME/REPORTÉ/ÉCART RÉSIDUEL), zéro écart bloquant non tracé | M |

**Dépendances internes** (plan §4-§5) :
- STORY-250 dépend de STORY-160 (croniter consommé par le scheduler, EPIC-013), STORY-168 (`CacheManager`/abstractions consommés par le cache fallback, EPIC-013) et de l'arbitrage F1 validé (STORY-130, purge Celery effective).
- STORY-251 dépend de STORY-174 (`WorkloadAdapter` = point d'accroche naturel, EPIC-013) et expose sa métrique via STORY-172 (`/metrics`, EPIC-013).
- STORY-252 dépend des vagues précédentes (les specs reflètent le code livré) et de la **validation utilisateur des arbitrages §7.4** (F3/F4/F5/F6 — F1/F2 déjà acquis).
- STORY-253 dépend des vagues P0-P2 (et idéalement 250/251) ; il prépare STORY-254.
- STORY-254 clôt le plan : dépend de STORY-252 (specs corrigées) et STORY-253 (`backend_status.md` à jour).
- Chaîne critique du plan : scheduler engine (P2-1) → purge croniter (P3-1).

**Critères de done (reprends fidèlement le plan)** :
- P3-1 : `grep`/import-check → aucun symbole orphelin ; OpenAPI ne référence plus `/workflows` ; CI et tests verts.
- P3-2 : cible Docker défaillante → circuit ouvert après N échecs, demi-ouvert après délai ; métrique exposée.
- P3-3 : `/auth/me` répond avec headers `Deprecation` + `Sunset` et note OpenAPI `deprecated: true` ; removal planifié documenté.
- P3-4 : les specs reflètent le code livré ; revue croisée specs ↔ `backend_status.md` actualisé.
- P3-5 : relecture → plus d'écart « annoncé vs réel » sur les points traités.
- Clôture (STORY-254) : tableau de conformité final produit ; zéro écart bloquant non tracé.

**Garde-fous** : la purge ne touche aucun des points forts §2.G ; le croniter vendored n'est supprimé que s'il n'a pas été ressuscité par le scheduler (STORY-160).

## Liste des Stories liées

- [ ] STORY-250 : Purge du code mort et résidus + dépréciation `/auth/me` — permissions legacy, croniter conditionnel, abstractions, stub workflows, litellm orphelin, print debug, HealthCheck, `/auth/me` déprécié (P3-1 + P3-3)
- [ ] STORY-251 : CircuitBreaker — câbler sur les appels externes ou supprimer le module (P3-2)
- [ ] STORY-252 : Corrections consolidées des spécifications — arbitrages F1-F6 appliqués aux specs (P3-4)
- [ ] STORY-253 : Mise à jour documentaire post-remédiation — `backend_status.md`, rules `.roo`, CHANGELOG (P3-5)
- [ ] STORY-254 : Revue finale de conformité — audit specs ↔ code et tableau de conformité final (clôture du plan)

## Notes de conception

- **Plage de numéros réservée** : STORY-250 à STORY-269 (seules 250-254 sont affectées ; 255-269 disponibles pour d'éventuelles sous-découpes). La plage 210-249 a été écartée car déjà réservée par EPIC-002 (STORY-201 à 246).
- Source principale : [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 « Vague P3 », axes E1-E9, F1/F2/F5 (docs), P3-5.
- Décisions « purger OU ressusciter » déjà tranchées dans le plan §2.E : E1 purger, E2 ressusciter partiellement (CircuitBreaker câblé, HealthCheck purgé), E3 ressusciter via scheduler (sinon purger), E4 `CacheManager` ressuscité en P2 / `DatabaseManager` purger si non consommé, E6/E7/E8 purger, E9 déprécier.
- **Découpage final (phase 5)** : la mission de création des stories a réordonné le mapping initial — P3-3 (dépréciation `/auth/me`) est fusionné dans STORY-250 (même zone : purge de résidus de contrat), les corrections de specs deviennent STORY-252 (les références croisées antérieures « STORY-253 » dans EPIC-012/EPIC-013 et STORY-130 ont été corrigées vers STORY-252 lors de l'audit de cohérence), le rangement documentaire devient STORY-253, et une story de clôture STORY-254 (revue finale de conformité) matérialise l'écran de contrôle final du plan.
- Corrections de références appliquées à cette édition : « STORY-167 (abstractions) » → **STORY-168** (cache fallback mémoire consomme `CacheManager`) ; « STORY-171 (WorkloadAdapter) » → **STORY-174** ; « STORY-168 (/metrics) » → **STORY-172** (observabilité).
- Cette epic clôt le cycle de remédiation : les stories ne peuvent être finalisées qu'une fois les vagues P0-P2 terminées.
- Écrans de contrôle : le grep/import-check de STORY-250, la revue croisée de STORY-252/253 et l'audit de STORY-254 servent de validation finale du plan complet.

## Critères de succès (Definition of Done)

- [ ] Les 5 stories P3 sont DONE avec leurs critères de done vérifiables validés.
- [ ] Aucun symbole orphelin ni référence Celery dans le code/CI/docs ; OpenAPI sans `/workflows` ; `/auth/me` déprécié avec `Sunset` documenté.
- [ ] `CircuitBreaker` opérationnel sur les appels externes et exposé dans `/metrics` — ou supprimé avec décision argumentée.
- [ ] Les specs (04/05/06/07/09/15/16) sont alignées sur le code livré selon les arbitrages F1-F8.
- [ ] `backend_status.md`, les rules `.roo` et le CHANGELOG reflètent l'état réel post-remédiation (plus d'écart annoncé vs réel).
- [ ] Le tableau de conformité final est produit : zéro écart bloquant non tracé (clos ou explicitement reportés Roadmap).
- [ ] CI complète verte (lint, typecheck, tests, sécurité).
