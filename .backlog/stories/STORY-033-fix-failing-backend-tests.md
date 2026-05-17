# STORY-033 : Correction des tests backend défaillants

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Correction de bugs
**Priorité :** Haute (bloquant)

## Description
Corriger les 2 tests backend qui échouent ou génèrent des erreurs de collection.

## Contexte technique

### Problèmes identifiés
1. **`test_compute_service.py`** : `ImportError` pour `_classify_containers` — la fonction a probablement été renommée ou déplacée vers `container_classifier.py`
2. **`test_stacks_api_variables_rendering.py`** : le test `test_stack_summary_response_fields` échoue car le set `expected_fields` ne contient pas `archived_at` et `is_archived`

### Fichiers impactés
| Fichier | Modification |
|---------|-------------|
| `backend/tests/unit/test_services/test_compute_service.py` | Corriger l'import `_classify_containers` |
| `backend/tests/unit/test_stacks_api_variables_rendering.py` | Ajouter `archived_at` et `is_archived` au set attendu |

## Critères d'acceptation (AC)
- [ ] AC 1 : `test_compute_service.py` ne génère plus d'ImportError pour `_classify_containers`
- [ ] AC 2 : `test_stacks_api_variables_rendering.py` — le test `test_stack_summary_response_fields` passe (ajouter `archived_at` et `is_archived` au set attendu)
- [ ] AC 3 : Tous les tests backend passent (0 failed, 0 errors)

## Tâches d'implémentation
- [ ] Corriger l'import dans `backend/tests/unit/test_services/test_compute_service.py` — la fonction `_classify_containers` a probablement été renommée ou déplacée vers `container_classifier.py`. Mettre à jour l'import.
- [ ] Mettre à jour `backend/tests/unit/test_stacks_api_variables_rendering.py` — ajouter `archived_at` et `is_archived` au set `expected_fields` du test `test_stack_summary_response_fields`
- [ ] Exécuter `cd backend && python -m pytest tests/ -v --tb=short` et vérifier que tous les tests passent
