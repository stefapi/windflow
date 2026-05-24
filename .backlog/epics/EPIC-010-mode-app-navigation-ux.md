# EPIC-010 : Mode App — Navigation & UX Simplifiée

**Statut :** TODO
**Priorité :** Haute

## Vision

Le Mode App est l'expérience par défaut d'WindFlow, de style Umbrel, où le vocabulaire technique (container, compose, helm, VM, namespace, pod) est masqué. L'utilisateur manipule des "Apps" au lieu de containers. C'est une **couche frontend uniquement** qui réutilise les APIs backend existantes (`/containers`, `/stacks`, `/targets`, etc.) — aucune nouvelle route backend n'est nécessaire à ce stade.

Le Mode Infra (toggle, onglets techniques, Vue Compute) sera traité dans une epic séparée en Phase 4.

---

## Description

### Contexte et Décision Produit

WindFlow propose aujourd'hui une interface orientée opérateur infrastructure (Docker). Le Mode App transforme cette expérience en une interface grand public, où l'utilisateur gère des "Applications" sans jamais voir de terme technique. Cette couche est purement frontend — les APIs backend existantes sont réutilisées telles quelles.

### Spécification de Référence

- [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md) — Document directeur : 3 familles, grammaire UI, sidebars Mode App/Infra
- [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écrans 1 (Dashboard), 2 (Liste Apps), 3 (Détail App), 4 (Marketplace), 8 (Console)
- [`docs/DESIGN-SYSTEM.md`](docs/DESIGN-SYSTEM.md) — Design system à respecter

### Périmètre (Scope)

**Famille Apps uniquement** en Mode App. Les familles Machines et Hosts seront ajoutées ultérieurement quand leurs epics respectives (EPIC-002 VMs, EPIC-003 Multi-Target) seront traitées.

---

## Analyse de l'état actuel du code

### Frontend

| Composant | Statut | Lien avec cette epic |
|---|---|---|
| [`SidebarNav.vue`](frontend/src/components/SidebarNav.vue) | ✅ Fonctionnel | À rendre conditionnel au mode (App/Infra) |
| [`Compute.vue`](frontend/src/views/Compute.vue) | ✅ Fonctionnel | À transformer en vue "Apps" avec vocabulaire non-technique |
| [`ContainerDetail.vue`](frontend/src/views/ContainerDetail.vue) | ✅ Fonctionnel | À adapter pour le Mode App (onglets, vocabulaire) |
| [`Dashboard.vue`](frontend/src/views/Dashboard.vue) | ✅ Fonctionnel | À enrichir avec la grille d'icônes Apps |
| [`ManagedStacksSection.vue`](frontend/src/components/compute/ManagedStacksSection.vue) | ✅ Fonctionnel | Vocabulaire à adapter via props ou composable |
| [`DiscoveredSection.vue`](frontend/src/components/compute/DiscoveredSection.vue) | ✅ Fonctionnel | Vocabulaire à adapter via props ou composable |
| [`StandaloneSection.vue`](frontend/src/components/compute/StandaloneSection.vue) | ✅ Fonctionnel | Vocabulaire à adapter via props ou composable |
| [`ContainerOverviewTab.vue`](frontend/src/components/ContainerOverviewTab.vue) | ✅ Fonctionnel | Vocabulaire "App" au lieu de "Container" |

### Backend

Aucune modification backend nécessaire — toutes les APIs existantes (`/containers`, `/stacks`, `/targets`, etc.) sont réutilisées en l'état.

---

## Liste des Stories liées

### STORY-A : Refonte Sidebar — Navigation Mode App

**Description :** Transformer la sidebar actuelle (Infrastructure, Stockage & Réseau, Marketplace, Administration) en sidebar Mode App documentée dans 11b.

**Contenu :**
- Nouvelle structure sidebar Mode App :
  ```
  🏠  Dashboard
  ── Workloads ──
  📱  Apps                    ← remplace "Compute" avec vocabulaire non-technique
  🏪  Marketplace             ← reste stub, mais positionné correctement
  🔌  Plugins                 ← reste stub, mais positionné correctement
  ── Plugins ──
  (zone dynamique pour plugins futurs)
  ⚙️  Settings
  ```
- Suppression des entrées "Infrastructure", "Stockage & Réseau" de la sidebar en Mode App
- Les entrées Volumes, Networks, Images, Compute, Targets, Stacks, Deployments, Workflows, Schedules deviennent accessibles uniquement via le menu contextuel `[⋯ Plus]` ou via un lien "Vue avancée" discret
- Le toggle `[🔧 Mode Infra]` en bas de sidebar est **présent mais désactivé** (grisé) avec tooltip "Bientôt disponible"
- Conserver le composant [`SidebarNav.vue`](frontend/src/components/SidebarNav.vue) existant et le rendre conditionnel au mode
- Ajouter un store Pinia `modeStore` (ou `uiModeStore`) pour gérer l'état du mode (App/Infra)

### STORY-B : Vue Liste Apps (refonte Compute.vue)

**Description :** Transformer [`Compute.vue`](frontend/src/views/Compute.vue) en vue "Apps" avec vocabulaire non-technique.

**Contenu :**
- Renommer le concept : "Managed Stacks" → "Mes Apps", "Standalone" → "Apps autonomes", "Discovered" → "Apps détectées"
- Cards par app avec : icône (du stack), nom, version, domaine (si disponible), statut, RAM
- Actions inline : Ouvrir (lien domaine), Logs, Terminal, Stop, menu contextuel `[⋯ Plus]`
- Badge de mise à jour disponible `[⬆]`
- Recherche et filtre par nom/statut
- Supprimer le vocabulaire "container", "compose", "stack" de l'UI visible
- Les sections ComputeStatsBanner et filtres avancés (type, technologie, target) sont masquées en Mode App
- Conserver les composants existants ([`ManagedStacksSection`](frontend/src/components/compute/ManagedStacksSection.vue), [`DiscoveredSection`](frontend/src/components/compute/DiscoveredSection.vue), [`StandaloneSection`](frontend/src/components/compute/StandaloneSection.vue)) mais adapter leur vocabulaire via des props ou un composable de traduction

### STORY-C : Détail App — Vocabulaire Mode App

**Description :** Adapter [`ContainerDetail.vue`](frontend/src/views/ContainerDetail.vue) pour le Mode App.

**Contenu :**
- Header : nom de l'app (pas le nom du container), version, statut, domaine, métriques inline (CPU, RAM)
- Action bar simplifiée : Ouvrir, Stop/Start, Redémarrer, Logs, Console, Config
- Onglets Mode App : Aperçu, Logs, Console, Métriques, Config
- Masquer les onglets techniques : Info (inspect Docker), Processes, Stats détaillées
- Le menu `[⋯ Plus]` contient les actions avancées : Supprimer, Renommer, Voir les détails techniques (ouvre en Mode Infra ciblé — désactivé pour l'instant)
- Adapter [`ContainerOverviewTab`](frontend/src/components/ContainerOverviewTab.vue) : vocabulaire "App" au lieu de "Container"

### STORY-D : Dashboard Mode App — Grille Apps

**Description :** Enrichir [`Dashboard.vue`](frontend/src/views/Dashboard.vue) avec la grille d'icônes Apps documentée dans l'Écran 1.

**Contenu :**
- Ajouter une section "Mes Apps" avec grille d'icônes cliquables (type Umbrel) : icône, nom, statut (dot coloré), domaine
- Clic sur app → navigue vers le Détail App
- Conserver les widgets existants (métriques, activité, alertes) mais les repositionner sous la grille Apps
- Salutation personnalisée ("Bonjour, {username}") en haut du dashboard

### STORY-E : Menu Contextuel `[⋯ Plus]` Canonique

**Description :** Créer un composant réutilisable `AppContextMenu` pour le menu contextuel documenté dans 11b.

**Contenu :**
- Menu déroulant standardisé avec sections :
  - Actions principales : Ouvrir, Start/Stop, Redémarrer
  - Outils : Logs, Console, Config
  - Avancé (séparateur) : Détails techniques, Supprimer
- Le contenu "Avancé" est la seule zone où le vocabulaire technique fuit en Mode App
- Utilisable depuis la liste Apps, le dashboard, et le détail App
- Remplace les boutons d'action actuels dispersés

### STORY-F : Composable de Vocabulaire Mode App

**Description :** Créer un composable `useAppVocabulary` qui centralise la traduction des termes techniques en termes Mode App.

**Contenu :**
- Mapping de termes : container → app, stack → app, image → (masqué), volume → (masqué), network → (masqué), target → serveur, compose → (masqué)
- Fonctions de formatage : `getAppStatus()`, `getAppActions()`, `getAppDisplayName()`
- Utilisable par tous les composants pour rester cohérent sans duplication
- Facilitera le futur Mode Infra (il suffira de ne pas appliquer le vocabulaire)

---

## Critères de succès (Definition of Done)

- [ ] La sidebar affiche la navigation Mode App (Dashboard, Apps, Marketplace, Plugins, Settings)
- [ ] Aucun terme technique (container, compose, stack, volume, network, image) n'apparaît dans l'UI en Mode App
- [ ] La vue "Apps" affiche les apps avec cards, actions simplifiées, et recherche
- [ ] Le détail App montre les onglets Mode App (Aperçu, Logs, Console, Métriques, Config)
- [ ] Le dashboard inclut une grille d'icônes Apps cliquables
- [ ] Le menu contextuel `[⋯ Plus]` est standardisé et réutilisable
- [ ] Les vues techniques (Compute, Volumes, Networks, Images, Targets, Stacks, Deployments) restent accessibles via URL directe mais ne sont pas dans la sidebar
- [ ] Le toggle Mode Infra est visible mais désactivé dans la sidebar
- [ ] Toutes les fonctionnalités existantes continuent de fonctionner (rien n'est supprimé, seulement masqué/restructuré)
- [ ] Le design system existant est respecté

---

## Notes de conception

### Architecture Mode App/Infra

Le Mode App est une **couche de présentation** qui se superpose aux composants existants sans les modifier structurellement :

1. **Store Pinia `modeStore`** : gère l'état global du mode (App/Infra), persisté dans `localStorage`
2. **Composable `useAppVocabulary`** : centralise la traduction des termes techniques, utilisé par tous les composants
3. **Composant `AppContextMenu`** : menu contextuel canonique réutilisable dans toutes les vues
4. **Conditionnement sidebar** : [`SidebarNav.vue`](frontend/src/components/SidebarNav.vue) lit le mode et affiche la navigation appropriée

### Stratégie de masquage du vocabulaire technique

Aucun terme technique n'est supprimé du code — il est masqué par la couche de vocabulaire :

| Terme technique | Terme Mode App | Visibilité |
|-----------------|----------------|------------|
| container | app | Remplacé |
| stack | app | Remplacé |
| compose | (masqué) | Non affiché |
| image | (masqué) | Non affiché |
| volume | (masqué) | Non affiché |
| network | (masqué) | Non affiché |
| target | serveur | Remplacé |
| deployment | (masqué) | Non affiché |

### Navigation Mode App

```
Sidebar Mode App :
┌─────────────────────┐
│ 🏠  Dashboard       │
│ ── Workloads ──     │
│ 📱  Apps            │
│ 🏪  Marketplace     │
│ 🔌  Plugins         │
│ ── Plugins ──       │
│ (zone dynamique)    │
│                     │
│                     │
│ ──────────────────  │
│ [🔧 Mode Infra]  🔒 │  ← désactivé, tooltip "Bientôt disponible"
│ ⚙️  Settings        │
└─────────────────────┘
```

### Grille Dashboard (Écran 1)

```
┌──────────────────────────────────────────────────┐
│ Bonjour, {username}                              │
│                                                  │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│ │ 🌐   │ │ 📊   │ │ 💬   │ │ 📁   │ │ 🔒   │   │
│ │Nginx │ │Grafana│ │Chat  │ │Nextcl│ │Vault │   │
│ │ ●    │ │ ●    │ │ ○    │ │ ●    │ │ ○    │   │
│ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘   │
│                                                  │
│ ┌─────────────┐ ┌─────────────┐ ┌────────────┐  │
│ │ Métriques   │ │ Activité    │ │ Alertes    │  │
│ │ CPU: 23%    │ │ Deploy #42  │ │ ⚠️ 2 warn │  │
│ │ RAM: 4.2Go  │ │ il y a 5min │ │            │  │
│ └─────────────┘ └─────────────┘ └────────────┘  │
└──────────────────────────────────────────────────┘
```

### Menu Contextuel `[⋯ Plus]` Canonique

```
┌─────────────────────────┐
│ ▶ Ouvrir                │
│ ⏹ Stop                  │
│ 🔄 Redémarrer           │
│ ─────────────────────── │
│ 📋 Logs                 │
│ 💻 Console              │
│ ⚙️  Config               │
│ ─────────────────────── │
│ 🔧 Détails techniques   │
│ 🗑️ Supprimer             │
└─────────────────────────┘
```

### Dépendances inter-stories

```
STORY-F (Composable useAppVocabulary)
    └── STORY-A (Sidebar Mode App)
    └── STORY-B (Vue Liste Apps)
    └── STORY-C (Détail App)
    └── STORY-D (Dashboard)

STORY-E (Menu Contextuel)
    └── STORY-B (Vue Liste Apps — utilise le menu)
    └── STORY-C (Détail App — utilise le menu)
    └── STORY-D (Dashboard — utilise le menu)

Ordre recommandé : F → A → E → B → C → D
```

---

## Risques et dépendances

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Régression sur les vues techniques existantes | Moyen | Faible | Les vues restent accessibles via URL directe, tests de non-régression |
| Incohérence de vocabulaire résiduelle | Moyen | Moyen | Composable centralisé `useAppVocabulary` + revue systématique |
| Performance de la grille Dashboard avec beaucoup d'apps | Faible | Faible | Virtualisation si > 50 apps, pagination sinon |
| Complexité du mode conditionnel dans SidebarNav | Faible | Moyen | Store Pinia dédié, tests unitaires du mode |

### Dépendances

- **Aucune dépendance backend** — couche frontend uniquement
- **Aucune dépendance envers d'autres epics** — peut être traitée en parallèle
- Les epics EPIC-001 (Marketplace) et EPIC-002 (VMs) pourront s'appuyer sur cette structure Mode App quand elles seront traitées

---

## Historique

| Date | Modification | Auteur |
|------|--------------|--------|
| 2026-05-23 | Création de l'epic | Claude |
