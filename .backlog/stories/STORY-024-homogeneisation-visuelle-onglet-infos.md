# STORY-024 : Homogénéisation visuelle — onglet Infos au design d'Aperçu

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux que tous les onglets de la page ContainerDetail aient un langage visuel cohérent afin de ne pas être désorienté par des styles contradictoires dans la même page.

## Contexte technique

L'onglet **Aperçu** (`ContainerOverviewTab.vue`) utilise un système de `el-card` avec un slot `#header` coloré et une bordure colorée de 3px thématique en bas du header (`border-bottom: 3px solid <couleur>`). C'est le design de référence.

L'onglet **Infos** (`ContainerInfoTab.vue`) utilise de simples `div.bg-[var(--color-bg-secondary)]` avec `el-descriptions` — design plat sans iconographie ni couleur.

L'onglet **Config** (`ContainerConfigTab.vue`) utilise des `div.config-section` — idem design plat.

**Palette de couleurs thématiques à respecter** (identique à l'Aperçu) :
- 🔵 Bleu (`--el-color-primary`) : Informations générales, Identité
- 🟢 Vert (`--el-color-success`) : Volumes, Réseau
- 🟣 Violet (`#9b59b6`) : Configuration container, Ports
- 🟠 Orange (`--el-color-warning`) : Santé, État
- 🔴 Rouge (`--el-color-danger`) : Ressources, Sécurité
- ⚫ Gris (`--el-color-info`) : Labels, Variables d'environnement

**Sections actuelles de ContainerInfoTab.vue à migrer** :
- Informations générales → card bleue
- État du container → card orange
- Configuration du container → card violette
- Labels → card grise
- Configuration hôte & Ressources → card rouge
- Sécurité & Capabilities → card rouge
- Occupation disque → card grise
- Ports → card violette
- Volumes → card verte
- Réseau → card verte
- Variables d'environnement → card grise

**Sections actuelles de ContainerConfigTab.vue à migrer** (même pattern) :
- Variables d'environnement → card grise
- Labels → card grise
- Restart Policy → card orange
- Resource Limits → card rouge

## Critères d'acceptation (AC)

- [x] AC 1 : Chaque section de l'onglet Infos est encapsulée dans un `el-card` avec un slot `#header` coloré (même pattern que `ContainerOverviewTab.vue`)
- [x] AC 2 : Chaque section de l'onglet Config est encapsulée dans un `el-card` avec slot `#header` coloré
- [x] AC 3 : Les couleurs thématiques sont cohérentes entre Aperçu, Infos et Config (mêmes couleurs pour les mêmes types de données)
- [x] AC 4 : Chaque header de card affiche une icône Element Plus pertinente + le titre en couleur thématique
- [x] AC 5 : Les cards ont `shadow="hover"` (comportement identique à l'Aperçu)
- [x] AC 6 : Le rendu responsive est maintenu (grille 1 colonne sur mobile)
- [x] AC 7 : Aucune régression fonctionnelle sur les données affichées

## Dépendances

- Aucune (story purement frontend, indépendante)

## État d'avancement technique

- [x] Migrer `ContainerInfoTab.vue` vers le pattern cards colorées
- [x] Migrer `ContainerConfigTab.vue` vers le pattern cards colorées
- [x] Vérifier la cohérence des couleurs avec `ContainerOverviewTab.vue`
- [x] Tests de non-régression visuels

## Tâches d'implémentation détaillées

### Tâche 1 : Migrer `ContainerInfoTab.vue` vers le pattern cards colorées
**Objectif :** Remplacer les `div` de section par des `el-card` avec header coloré + icône.
**Fichier :** `frontend/src/components/ContainerInfoTab.vue`
**Détails :**
- Remplacer chaque `div.info-section` par un `el-card` avec `shadow="hover"`
- Ajouter un slot `#header` avec `div.card-header` contenant une icône + titre
- Appliquer les classes de couleur thématique : `header-blue`, `header-orange`, `header-purple`, `header-green`, `header-grey`
- Ajouter les bordures colorées via classes CSS `.card-info-general :deep(.el-card__header)` etc.
- Importer les icônes Element Plus : `InfoFilled`, `Warning`, `Setting`, `PriceTag`, `Cpu`, `Lock`, `Coin`, `Connection`, `FolderOpened`, `Share`, `Document`

### Tâche 2 : Migrer `ContainerConfigTab.vue` vers le pattern cards colorées
**Objectif :** Remplacer les `div.config-section` par des `el-card` avec header coloré + icône.
**Fichier :** `frontend/src/components/ContainerConfigTab.vue`
**Détails :**
- Remplacer chaque `div.config-section` par un `el-card` avec `shadow="hover"`
- Ajouter un slot `#header` avec icône + titre
- Appliquer les couleurs : Env vars (gris), Labels (gris), Restart Policy (orange), Resources (rouge)
- Importer les icônes : `Document`, `PriceTag`, `RefreshRight`, `Cpu`

### Tâche 3 : Mettre à jour les tests unitaires
**Objectif :** Adapter les tests aux nouveaux composants stubés et aux nouvelles classes CSS.
**Fichiers :**
- `frontend/tests/unit/components/ContainerInfoTab.spec.ts`
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts`
**Détails :**
- Stubber `el-card` avec une div qui rend les slots
- Vérifier la présence des cards via `findAll('.el-card')` ou `findAll('.el-card-stub')`
- Tester les classes de couleur dans le HTML rendu
- Vérifier que les sections sont toujours fonctionnellement correctes

### Tâche 4 : Vérifier la cohérence et les tests
**Objectif :** S'assurer que tous les tests passent et qu'il n'y a pas de régression.
**Commande :** `pnpm test:unit -- --run`
**Détails :**
- Lancer les 3 tests impactés : ContainerInfoTab, ContainerConfigTab, ContainerDetail
- Vérifier que la suite complète passe (31 fichiers, 470+ tests)

## Tests à écrire

### Tests ContainerInfoTab
- Rendu de chaque section avec son titre (Informations générales, État du container, Configuration, etc.)
- Vérification de la présence des cards (`findAll('.el-card')` ≥ 8)
- Vérification des classes de couleur dans le HTML (`header-blue`, `header-orange`, `header-purple`, `header-green`)
- Formatage des valeurs (formatBytes pour l'occupation disque)
- Sections conditionnelles (Health Check, OOM Killed, Occupation disque)

### Tests ContainerConfigTab
- Rendu des 4 cards (Env vars, Labels, Restart Policy, Resources)
- Pré-remplissage des champs depuis le détail du container
- Ajout/suppression de lignes env vars et labels
- Appels API pour restart policy et resources
- Gestion des erreurs API
- États de chargement (loadingRestart, loadingResources)
- Cas limites (detail null, config null, env sans `=`, labels vides)

## Notes d'implémentation

**Fichiers modifiés :**
- `frontend/src/components/ContainerInfoTab.vue` — Migration complète vers `el-card` avec 11+ sections thématiques
- `frontend/src/components/ContainerConfigTab.vue` — Migration vers `el-card` avec 4 sections thématiques
- `frontend/tests/unit/components/ContainerInfoTab.spec.ts` — Tests adaptés aux nouveaux stubs et au pattern cards
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — Réécriture complète des tests (30 tests, couverture exhaustive)

**Décisions techniques :**
- Utilisation de `findAll('.el-card')` / `findAll('.el-card-stub')` au lieu de `findAllComponents({ name: 'el-card' })` car les stubs VTU n'ont pas de `name`
- Le style CSS utilise `:deep(.el-card__header)` pour les bordures colorées (identique à ContainerOverviewTab)
- Icônes Element Plus importées inline pour chaque section

**Tests :** 470 tests passants sur 31 fichiers — aucune régression.
