# STORY-039 : Documentation utilisateur — Nouvelles fonctionnalités

**Statut :** IN_PROGRESS
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Documentation
**Priorité :** Basse (mais critère epic)

## Description
Rédiger la documentation utilisateur pour toutes les nouvelles fonctionnalités introduites par l'EPIC-008.

## Contexte technique

### Fonctionnalités à documenter
1. **Vue Compute** : bandeau stats, 3 sections (managed/discovered/standalone), filtres
2. **Gestion des images** : liste, pull, remove, détail, import/export
3. **Volumes** : liste, création, suppression
4. **Réseaux** : visualisation
5. **Informations système Docker** : widget et page dédiée
6. **Import/export de stacks** : partage et sauvegarde
7. **Actions de stack** : start/stop/redeploy, duplication, archivage
8. **Adoption d'objets découverts** : wizard d'adoption
9. **Création manuelle de containers** : formulaire avancé
10. **Édition à chaud** : restart policy, ressources

### Fichiers à créer/mettre à jour
| Fichier | Contenu |
|---------|---------|
| `docs/user-guide/compute.md` | Vue Compute |
| `docs/user-guide/docker-images.md` | Gestion des images |
| `docs/user-guide/docker-volumes.md` | Gestion des volumes |
| `docs/user-guide/docker-networks.md` | Réseaux Docker |
| `docs/user-guide/system-info.md` | Informations système |
| `docs/user-guide/stacks.md` | Actions de stack, import/export |
| `docs/user-guide/adoption.md` | Adoption d'objets |
| `docs/user-guide/containers.md` | Création et édition |

## Critères d'acceptation (AC)
- [ ] AC 1 : Documentation pour la vue Compute (bandeau stats, 3 sections, filtres)
- [ ] AC 2 : Documentation pour la gestion des images (liste, pull, remove, détail, import/export)
- [ ] AC 3 : Documentation pour les volumes (liste, création, suppression)
- [ ] AC 4 : Documentation pour les réseaux (visualisation)
- [ ] AC 5 : Documentation pour les informations système Docker
- [ ] AC 6 : Documentation pour l'import/export de stacks
- [ ] AC 7 : Documentation pour les actions de stack (start/stop/redeploy, duplication, archivage)
- [ ] AC 8 : Documentation pour l'adoption d'objets découverts
- [ ] AC 9 : Documentation pour la création manuelle de containers
- [ ] AC 10 : Documentation pour l'édition à chaud (restart policy, ressources)

## Sous-stories
- [ ] [STORY-039.1](.backlog/stories/STORY-039.1-docs-user-guide-compute.md) : Documentation utilisateur — Vue Compute — Couvre AC 1
- [ ] [STORY-039.2](.backlog/stories/STORY-039.2-docs-user-guide-docker-assets.md) : Documentation utilisateur — Images, Volumes, Réseaux et Système Docker — Couvre AC 2–5
- [ ] [STORY-039.3](.backlog/stories/STORY-039.3-docs-user-guide-stacks.md) : Documentation utilisateur — Import/export et actions sur les stacks — Couvre AC 6–7
- [ ] [STORY-039.4](.backlog/stories/STORY-039.4-docs-user-guide-adoption-containers.md) : Documentation utilisateur — Adoption, création et édition de containers — Couvre AC 8–10

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 0/4 sous-stories terminées
- [ ] STORY-039.1 : Documentation utilisateur — Vue Compute
- [ ] STORY-039.2 : Documentation utilisateur — Images, Volumes, Réseaux et Système Docker
- [ ] STORY-039.3 : Documentation utilisateur — Import/export et actions sur les stacks
- [ ] STORY-039.4 : Documentation utilisateur — Adoption, création et édition de containers
