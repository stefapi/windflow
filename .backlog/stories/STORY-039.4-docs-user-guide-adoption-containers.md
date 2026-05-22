# STORY-039.4 : Documentation utilisateur — Adoption, création et édition de containers

**Statut :** TODO
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger les guides utilisateur pour les fonctionnalités avancées de gestion des containers dans WindFlow : le wizard d'adoption d'objets découverts (container, composition Docker, release Helm), la création manuelle de containers via formulaire avancé, et l'édition à chaud des paramètres de configuration (restart policy, limites de ressources CPU/mémoire).

## Critères d'acceptation (AC)
- [ ] AC 8 : Documentation pour l'adoption d'objets découverts
- [ ] AC 9 : Documentation pour la création manuelle de containers
- [ ] AC 10 : Documentation pour l'édition à chaud (restart policy, ressources)

## Contexte technique
### Adoption d'objets découverts
- Composant : `frontend/src/components/AdoptionWizard.vue`
- API : `discoveryApi.getItems`, `discoveryApi.getAdoptionData`, `discoveryApi.adopt`
- Types : `DiscoveredItem`, `AdoptionWizardData`, `AdoptionRequest`
- Support : container, composition, helm_release

### Création manuelle de containers
- Composant : `frontend/src/components/ContainerCreateDialog.vue`
- API : `POST /docker/containers`

### Édition à chaud
- Onglet : `frontend/src/components/ContainerConfigTab.vue`
- API : `PUT /deployments/{id}` (mise à jour deployment), modifications avec recréation dans EPIC-009
- Paramètres : restart policy (no, always, on-failure, unless-stopped), limites CPU, limites mémoire

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Rédiger le guide d'adoption d'objets découverts
**Objectif :** Créer `docs/user-guide/adoption.md` décrivant le wizard en 3 étapes : (1) Inventaire des composants détectés, (2) Mapping suggéré vers une stack (nouvelle ou existante) avec stratégies volumes/réseaux, (3) Preview du compose généré et confirmation. Documenter les 3 types supportés (container, composition, helm_release) et les options spécifiques Helm (namespace, values override).
**Fichiers :**
- `docs/user-guide/adoption.md` — Créer — Guide d'adoption d'objets découverts
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Rédiger le guide de création manuelle de containers
**Objectif :** Documenter le formulaire avancé de création de container : image, nom, ports, volumes, variables d'environnement, réseaux, labels, et options avancées. Expliquer la différence avec la création via stack.
**Fichiers :**
- `docs/user-guide/containers.md` — Créer — Section "Création manuelle de containers"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 3 : Rédiger le guide d'édition à chaud des containers
**Objectif :** Documenter l'édition des paramètres de configuration depuis l'onglet Config du détail d'un container : restart policy (description de chaque option), limites de ressources CPU (shares, quota, period), limites mémoire (hard limit, soft limit, swap). Préciser que ces modifications sont appliquées sans recréation du container, contrairement aux changements de ports/image/réseaux (EPIC-009).
**Fichiers :**
- `docs/user-guide/containers.md` — Modifier — Section "Édition à chaud"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

### Tâche 4 : Rédiger la section cycle de vie d'un container
**Objectif :** Fournir un guide de référence du cycle de vie : création (manuelle ou via stack) → supervision → édition à chaud → adoption (standalone → stack) → suppression.
**Fichiers :**
- `docs/user-guide/containers.md` — Modifier — Section "Cycle de vie d'un container"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 3

## Tests à écrire

### Validation documentation
- Vérifier que tous les liens internes sont valides
- Vérifier la cohérence des termes avec l'UI (adoption, discovered, standalone, promote)
- Vérifier que les noms de composants et endpoints sont corrects

### Commandes de validation
```bash
# Vérifier la syntaxe Markdown
npx markdownlint docs/user-guide/adoption.md docs/user-guide/containers.md || true
```

## État d'avancement technique
- [ ] Tâche 1 : Rédiger le guide d'adoption d'objets découverts
- [ ] Tâche 2 : Rédiger le guide de création manuelle de containers
- [ ] Tâche 3 : Rédiger le guide d'édition à chaud des containers
- [ ] Tâche 4 : Rédiger la section cycle de vie d'un container

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
