# EPIC-004 : Refonte UI, Navigation & Nettoyage Marketplace

**Statut :** IN_PROGRESS
**Priorité :** Haute
**Phase Roadmap :** 2 — Q2 2026 (Avril–Juin, sprint dédié front en début de phase)
**Version cible :** 1.1

## Vision

L'UI actuelle hérite de la Phase 1 avec des fonctionnalités **prématurées ou mal construites** (Marketplace, Reviews, Favorites) et des **vues manquantes** par rapport aux specs UX (`11-UI-mockups.md`). Avant de construire les fonctionnalités des EPIC-001/002/003, il faut un cadre UI **propre, cohérent et extensible**.

Cette epic a deux axes :
1. **Nettoyage** : supprimer la Marketplace actuelle (frontend + backend + modèles DB) qui sera reconstruite proprement dans l'EPIC-001.
2. **Refonte** : restructurer la navigation, enrichir le dashboard, créer les vues manquantes, et poser le design system.

### Valeur Business
- Supprime la dette technique avant qu'elle ne se propage
- Donne un cadre UI stable pour les EPIC-001/002/003 (les plugins, VMs et multi-target ont besoin d'un layout extensible)
- Aligne l'UI réelle sur les specs UX validées
- Améliore l'expérience dès le premier contact (dashboard actionnable, navigation en 2 clics)

### Utilisateurs cibles
- Tout utilisateur de WindFlow — c'est la fondation UI

## Nettoyage — Éléments à supprimer

### Frontend
| Fichier/Dossier | Raison |
|---|---|
| `frontend/src/views/Marketplace.vue` | Marketplace prématurée, sera reconstruite dans EPIC-001 |
| `frontend/src/components/marketplace/` (tout le dossier) | 6 composants + renderers liés à la marketplace actuelle |
| → `DeploymentProgress.vue` | Couplé à la marketplace actuelle |
| → `DeploymentWizard.vue` | Sera refait dans EPIC-001 (wizard plugin) |
| → `StackCard.vue` | Design non conforme aux specs |
| → `StackDetailsModal.vue` | Design non conforme aux specs |
| → `StackReviews.vue` | Fonctionnalité prématurée |
| → `TargetSelector.vue` | À refactorer dans un composant partagé |
| → `renderers/` | Dépendance de la marketplace actuelle |

### Backend API
| Fichier | Raison |
|---|---|
| `backend/app/api/v1/marketplace.py` | Sera reconstruit dans EPIC-001 |
| `backend/app/api/v1/reviews.py` | Fonctionnalité prématurée |
| `backend/app/api/v1/favorites.py` | Fonctionnalité prématurée |

### Backend Modèles & DB
| Fichier | Raison |
|---|---|
| `backend/app/models/stack_review.py` | Table reviews — prématurée |
| `backend/app/models/user_favorite.py` | Table favorites — prématurée |

### Éléments CONSERVÉS (valeur réutilisable)
| Fichier | Raison |
|---|---|
| `frontend/src/components/DynamicFormField.vue` | Réutilisé pour config plugins (EPIC-001) |
| `frontend/src/components/DeploymentLogs.vue` | Fonctionnel et utile |
| `frontend/src/components/ContainerTerminal.vue` | Fonctionnel et utile |
| `frontend/src/components/SplashScreen.vue` | Conservé |
| `frontend/src/components/dashboard/` | À enrichir, pas supprimer |

## Liste des Stories liées

### Nettoyage Marketplace
- [x] STORY-401 : Audit & suppression Marketplace frontend (vue + composants + routes + stores + services liés)
- [x] STORY-402 : Suppression API backend marketplace (endpoints + schemas + services liés)
- [x] STORY-403 : Migration Alembic pour supprimer tables `stack_review` et `user_favorite`
- [x] STORY-404 : Nettoyage des imports, routes, références orphelines (front + back)

### Navigation & Layout
- [x] STORY-411 : Restructuration Sidebar selon specs (Infrastructure / Stockage & Réseau / Marketplace / Plugins / Administration + section dynamique plugins)
- [x] STORY-412 : Règle des 2 clics — validation et ajustement de la navigation complète
- [x] STORY-413 : Responsive sidebar rétractable (tablette ≥768px)

### Design System
- [ ] STORY-421 : Palette de couleurs thème sombre (tokens UnoCSS, fond `#0f1117`, accent `#3b82f6`, etc.)
- [ ] STORY-422 : Typographie (Inter/IBM Plex Sans pour UI, JetBrains Mono pour code/logs)
- [ ] STORY-423 : Composants de base harmonisés (badges statut, barres de progression, icônes actions)
- [ ] STORY-471 : Refonte Page Login avec design unifié et nouveau logo WindFlow

### Dashboard
- [ ] STORY-431 : Barre métriques système (CPU, RAM, disque, uptime du target actif)
- [ ] STORY-432 : Tuiles compteurs Containers / VMs / Stacks (cliquables)
- [ ] STORY-433 : Liste derniers déploiements avec statut + action directe
- [ ] STORY-434 : Zone widgets plugins (vide proprement si aucun plugin — peuplée par EPIC-001)

### Vue Containers (remplace Deployments)
- [ ] STORY-441 : Vue Containers — liste avec actions inline (start/stop/restart/logs/supprimer)
- [ ] STORY-442 : Vue Containers — filtres (statut, target) + recherche + sélection multiple
- [ ] STORY-443 : Vue ContainerDetail — onglets Infos (ports, volumes, env, réseau)
- [ ] STORY-444 : Vue ContainerDetail — onglet Logs (réutilise DeploymentLogs.vue)
- [ ] STORY-445 : Vue ContainerDetail — onglet Terminal (réutilise ContainerTerminal.vue)
- [ ] STORY-446 : Vue ContainerDetail — onglet Stats (CPU, RAM, network I/O temps réel)

### Vue Settings
- [ ] STORY-451 : Page Settings avec onglets : Organisations, Environnements, Utilisateurs
- [ ] STORY-452 : Gestion RBAC depuis la page Settings (rôles, permissions par user)

### Vues Stubs (prêtes pour EPIC-001/002/003)
- [ ] STORY-461 : Vue stub Volumes + Networks + Images (placeholder "Bientôt disponible" + lien vers EPIC-002)
- [ ] STORY-462 : Vue stub Plugins installés (placeholder "Aucun plugin installé" + lien marketplace futur)

## Notes de conception

- **Nettoyage** : supprimer en cascade propre — vue → composants → route → store → service → types. Vérifier qu'aucun import orphelin ne subsiste
- **Migration Alembic** : migration down réversible pour les tables supprimées (garder le schéma en commentaire)
- **Sidebar** : composant SidebarNav avec sections configurables. Les plugins injecteront des entrées via un store Pinia dédié (`usePluginNavStore`)
- **Design system** : tokens UnoCSS dans `uno.config.ts`, pas de CSS en dur dans les composants
- **Vue Containers vs Deployments** : les vues actuelles `Deployments.vue` et `DeploymentDetail.vue` sont renommées/refactorées en `Containers.vue` et `ContainerDetail.vue` — pas de coexistence
- **Tests** : chaque nouvelle vue couverte par Vitest (≥80%). Tests de suppression : vérifier que les routes supprimées retournent 404, que les modèles n'existent plus

## Critères de succès (Definition of Done)
- [ ] La Marketplace actuelle est complètement supprimée (0 référence front + back)
- [ ] Les tables stack_review et user_favorite sont supprimées via migration Alembic
- [ ] La sidebar correspond au wireframe des specs
- [ ] Le dashboard affiche métriques système + tuiles + derniers déploiements
- [ ] La vue Containers remplace Deployments avec actions inline fonctionnelles
- [ ] ContainerDetail a 4 onglets fonctionnels (Infos, Logs, Terminal, Stats)
- [ ] La page Settings gère Orgs/Users/RBAC
- [ ] Le thème sombre est appliqué (palette spec)
- [ ] Les vues stubs sont en place pour les futures epics
- [ ] Aucun import orphelin, aucune route cassée
- [ ] Couverture tests ≥ 80% sur les nouvelles vues
- [ ] `pnpm build` + `pnpm lint` passent sans erreur

## Risques
| Risque | Impact | Mitigation |
|--------|--------|------------|
| Suppression casse des fonctionnalités existantes | Élevé | Audit complet avant suppression, tests de non-régression |
| Refonte trop ambitieuse en un sprint | Moyen | Prioriser : nettoyage → sidebar → containers → dashboard → settings → stubs |
| Design system diverge des specs | Faible | Tokens UnoCSS extraits directement de 11-UI-mockups.md |
| Vues stubs inutilisées longtemps | Faible | Texte informatif + countdown vers la phase prévue |

## Dépendances
- Phase 1 Core Platform (✅ livré)
- `DeploymentLogs.vue`, `ContainerTerminal.vue` (✅ conservés et réutilisés)
- `DynamicFormField.vue` (✅ conservé — réutilisé par EPIC-001)

## Ordre d'exécution recommandé

```
Sprint 1 (début Q2)          Sprint 2 (mi Q2)
┌─────────────────────┐     ┌──────────────────────┐
│ STORY-401→404       │     │ STORY-431→434        │
│ (Nettoyage complet) │────>│ (Dashboard enrichi)  │
│                     │     │                      │
│ STORY-411→413       │     │ STORY-441→446        │
│ (Sidebar + layout)  │     │ (Vue Containers)     │
│                     │     │                      │
│ STORY-421→423       │     │ STORY-451→452        │
│ (Design system)     │     │ (Settings)           │
│                     │     │                      │
│                     │     │ STORY-461→462        │
│                     │     │ (Vues stubs)         │
└─────────────────────┘     └──────────────────────┘
```
