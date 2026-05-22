# STORY-039.3 : Documentation utilisateur — Import/export et actions sur les stacks

**Statut :** TODO
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger le guide utilisateur pour les fonctionnalités de gestion avancée des stacks dans WindFlow : export d'une stack au format JSON (partage et sauvegarde), import d'une stack depuis un fichier JSON, et actions globales sur une stack (démarrer, arrêter, redéployer, dupliquer, archiver).

## Critères d'acceptation (AC)
- [ ] AC 6 : Documentation pour l'import/export de stacks
- [ ] AC 7 : Documentation pour les actions de stack (start/stop/redeploy, duplication, archivage)

## Contexte technique
### Import/Export Stacks
- Vue : `frontend/src/views/Stacks.vue` (actions d'export et d'import)
- API : `stacksApi.export`, `stacksApi.import`
- Types : `StackExportData`

### Actions de stack
- Composant : `frontend/src/components/StackActionsBar.vue`
- API : `stacksApi.start`, `stacksApi.stop`, `stacksApi.redeploy`, `stacksApi.duplicate`, `stacksApi.archive`
- Types : `StackActionResponse`, `StackRedeployRequest`, `StackDuplicateRequest`
- Stratégies de redeploy : `rolling` vs `stop-start`, option `pull_images`

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Rédiger la section export de stacks
**Objectif :** Documenter le flux d'export JSON : accès depuis la liste des stacks ou la vue Compute, contenu du fichier exporté (template, variables, tags, etc.), et cas d'usage (sauvegarde, partage entre environnements).
**Fichiers :**
- `docs/user-guide/stacks.md` — Créer — Section "Export de stacks"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Rédiger la section import de stacks
**Objectif :** Documenter le flux d'import JSON : sélection du fichier, validation du format, mapping des variables, et résultat (nouvelle stack créée).
**Fichiers :**
- `docs/user-guide/stacks.md` — Modifier — Section "Import de stacks"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Rédiger la section actions globales de stack
**Objectif :** Documenter chaque action disponible dans `StackActionsBar.vue` : Start (démarrer tous les services), Stop (arrêter tous les services), Redeploy (options rolling/stop-start + pull images), Duplicate (nom de la nouvelle stack, target optionnel), Archive (mise en archive).
**Fichiers :**
- `docs/user-guide/stacks.md` — Modifier — Section "Actions de stack"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 4 : Rédiger la section gestion du cycle de vie d'une stack
**Objectif :** Fournir un guide de référence rapide du cycle de vie complet : création → déploiement → actions (start/stop/redeploy) → duplication → archivage → suppression, avec les prérequis et impacts de chaque action.
**Fichiers :**
- `docs/user-guide/stacks.md` — Modifier — Section "Cycle de vie d'une stack"
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 3

## Tests à écrire

### Validation documentation
- Vérifier que tous les liens internes sont valides
- Vérifier la cohérence des termes avec l'UI (rolling, stop-start, pull_images)
- Vérifier que les noms de composants et endpoints sont corrects

### Commandes de validation
```bash
# Vérifier la syntaxe Markdown
npx markdownlint docs/user-guide/stacks.md || true
```

## État d'avancement technique
- [ ] Tâche 1 : Rédiger la section export de stacks
- [ ] Tâche 2 : Rédiger la section import de stacks
- [ ] Tâche 3 : Rédiger la section actions globales de stack
- [ ] Tâche 4 : Rédiger la section gestion du cycle de vie d'une stack

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
