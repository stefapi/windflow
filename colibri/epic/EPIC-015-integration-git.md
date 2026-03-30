# EPIC-015 : Intégration Git

**Statut :** TODO
**Priorité :** Haute

## Vision
Intégration complète avec Git pour le déploiement de stacks. Les utilisateurs peuvent configurer des dépôts Git avec credentials (SSH, HTTPS), synchroniser manuellement ou automatiquement, et recevoir des webhooks pour le déploiement automatique.

## Liste des Stories liées
- [ ] STORY-001 : Configurer des credentials Git (SSH key, username/password)
- [ ] STORY-002 : Ajouter un dépôt Git avec URL, branche et chemin du compose
- [ ] STORY-003 : Synchroniser manuellement un dépôt
- [ ] STORY-004 : Configurer des webhooks pour déploiement automatique
- [ ] STORY-005 : Voir le statut de synchronisation (pending, syncing, synced, error)
- [ ] STORY-006 : Voir le dernier commit synchronisé
- [ ] STORY-007 : Prévisualiser les variables d'environnement d'un dépôt avant déploiement
- [ ] STORY-008 : Le système supporte les clés SSH avec passphrase
- [ ] STORY-009 : Le système gère les re-clones pour les force pushes et changements de branche

## Notes de conception
- Tables git_credentials, git_repositories, git_stacks
- Support SSH avec clé privée et passphrase (décryptage via ssh-keygen)
- Support HTTPS avec username/password (credentials embedded dans l'URL)
- Clone blobless pour la performance (fetch commits, blobs on-demand)
- Re-clone systématique pour garantir un état propre (force push, changement branche)
- Détection des changements via git diff entre commits
- Webhook avec secret pour la sécurité
- Prévisualisation des variables d'environnement via clone temporaire
- Gestion des erreurs Git avec messages utilisateur-friendly
- Support de libnss_wrapper pour les UID manquants dans /etc/passwd
