# STORY-036 : Tests manquants — STORY-004 StackActionsBar

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Tests
**Priorité :** Moyenne

## Description
Écrire les tests unitaires manquants pour la STORY-004 (StackActionsBar) : tests backend (`test_stack_actions.py`) et tests frontend (`StackActionsBar.spec.ts`).

## Contexte technique

### Comportement actuel
- La STORY-004 (Actions globales de stack) a été implémentée sans tests dédiés
- Le critère d'acceptation AC 5 (tests) n'est pas satisfait
- `backend/tests/unit/test_stack_actions.py` n'existe pas
- `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` n'existe pas

### Fichiers à créer
| Fichier | Contenu |
|---------|---------|
| `backend/tests/unit/test_stack_actions.py` | Tests backend pour les actions start/stop/redeploy |
| `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` | Tests frontend pour le composant StackActionsBar |

## Critères d'acceptation (AC)
- [ ] AC 1 : `backend/tests/unit/test_stack_actions.py` créé avec au moins 7 tests couvrant les actions start/stop/redeploy
- [ ] AC 2 : `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` créé avec au moins 6 tests
- [ ] AC 3 : Tous les nouveaux tests passent
- [ ] AC 4 : La STORY-004 AC 5 est satisfaite

## Tâches d'implémentation
- [ ] Créer `backend/tests/unit/test_stack_actions.py` avec des tests pour :
  - Stack start (succès, erreur, stack non trouvée)
  - Stack stop (succès, erreur)
  - Stack redeploy (succès, erreur, stratégie invalide)
- [ ] Créer `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` avec des tests pour :
  - Rendu des boutons Start/Stop/Redeploy
  - Émission des événements au clic
  - États désactivés (loading, pas de sélection)
  - Dialog de confirmation
- [ ] Exécuter les tests et vérifier qu'ils passent
