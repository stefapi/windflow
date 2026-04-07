# STORY-024 : Homogénéisation visuelle — onglet Infos au design d'Aperçu

**Statut :** TODO
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

- [ ] AC 1 : Chaque section de l'onglet Infos est encapsulée dans un `el-card` avec un slot `#header` coloré (même pattern que `ContainerOverviewTab.vue`)
- [ ] AC 2 : Chaque section de l'onglet Config est encapsulée dans un `el-card` avec slot `#header` coloré
- [ ] AC 3 : Les couleurs thématiques sont cohérentes entre Aperçu, Infos et Config (mêmes couleurs pour les mêmes types de données)
- [ ] AC 4 : Chaque header de card affiche une icône Element Plus pertinente + le titre en couleur thématique
- [ ] AC 5 : Les cards ont `shadow="hover"` (comportement identique à l'Aperçu)
- [ ] AC 6 : Le rendu responsive est maintenu (grille 1 colonne sur mobile)
- [ ] AC 7 : Aucune régression fonctionnelle sur les données affichées

## Dépendances

- Aucune (story purement frontend, indépendante)

## État d'avancement technique

- [ ] Migrer `ContainerInfoTab.vue` vers le pattern cards colorées
- [ ] Migrer `ContainerConfigTab.vue` vers le pattern cards colorées
- [ ] Vérifier la cohérence des couleurs avec `ContainerOverviewTab.vue`
- [ ] Tests de non-régression visuels

## Tâches d'implémentation détaillées

<!-- À remplir par analyse-story -->

## Tests à écrire

<!-- À remplir par analyse-story -->
