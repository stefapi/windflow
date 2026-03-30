# EPIC-014 : Gestion des Registries Docker

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Gestion des credentials pour les registries Docker. Les utilisateurs peuvent configurer des identifiants pour différents registries (Docker Hub, GHCR, registries privées) qui sont utilisés automatiquement pour les opérations pull/push.

## Liste des Stories liées
- [ ] STORY-001 : Ajouter un registry avec URL, username et password
- [ ] STORY-002 : Définir un registry par défaut
- [ ] STORY-003 : Les credentials sont utilisés automatiquement pour les pulls/pushs
- [ ] STORY-004 : Gérer plusieurs registries (Docker Hub, GHCR, registries privées)
- [ ] STORY-005 : Le système supporte l'authentification Basic et Bearer token

## Notes de conception
- Table registries avec URL, username, password, is_default
- Support de l'authentification Basic (username/password)
- Support du flux OAuth2 Bearer token pour les registries privés
- Matching des registries par hostname et chemin d'organisation
- Alias Docker Hub (docker.io, hub.docker.com, index.docker.io, etc.)
- Header X-Registry-Auth pour les opérations Docker API
- Credentials utilisés automatiquement lors des pulls/pushs
- Support des registries avec sous-chemins (ex: registry.example.com/org)
