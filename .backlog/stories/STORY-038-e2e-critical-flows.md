# STORY-038 : Tests E2E — Flux critiques EPIC-008

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Tests E2E
**Priorité :** Basse (mais critère epic)

## Description
Créer des tests E2E (Playwright) pour les flux utilisateur critiques introduits par l'EPIC-008.

## Contexte technique

### Flux critiques à tester
1. **Adoption (wizard)** : détection d'objets orphelins → wizard d'adoption → stack créée
2. **Actions de stack** : start/stop/redeploy sur une stack
3. **Gestion des images** : pull d'une image, suppression
4. **Import/export de stacks** : export JSON, import depuis fichier
5. **Vue Compute** : navigation, filtres, 3 sections

### Fichiers à créer
| Fichier | Contenu |
|---------|---------|
| `frontend/tests/e2e/compute.spec.ts` | Navigation et filtres Compute |
| `frontend/tests/e2e/stacks.spec.ts` | Actions stack, import/export |
| `frontend/tests/e2e/images.spec.ts` | Pull et remove d'images |
| `frontend/tests/e2e/adoption.spec.ts` | Wizard d'adoption |

## Critères d'acceptation (AC)
- [ ] AC 1 : Au moins 1 test E2E pour le flux d'adoption (wizard)
- [ ] AC 2 : Au moins 1 test E2E pour les actions de stack (start/stop/redeploy)
- [ ] AC 3 : Au moins 1 test E2E pour la gestion des images (pull, remove)
- [ ] AC 4 : Au moins 1 test E2E pour l'import/export de stacks
- [ ] AC 5 : Au moins 1 test E2E pour la vue Compute (navigation, filtres)
- [ ] AC 6 : Tous les tests E2E passent

## Tâches d'implémentation
- [ ] Vérifier la configuration Playwright existante (`frontend/playwright.config.ts`)
- [ ] Créer `frontend/tests/e2e/compute.spec.ts` — navigation et filtres Compute
- [ ] Créer `frontend/tests/e2e/stacks.spec.ts` — actions stack, import/export
- [ ] Créer `frontend/tests/e2e/images.spec.ts` — pull et remove d'images
- [ ] Créer `frontend/tests/e2e/adoption.spec.ts` — wizard d'adoption
- [ ] Exécuter les tests E2E et vérifier qu'ils passent
