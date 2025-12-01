## Workflow de développement

### Démarrage
1. Lire le Memory Bank complet (`memory-bank/*.md`)
2. Vérifier l'état actuel dans `activeContext.md`
3. Examiner les tâches en cours dans `progress.md`

### Développement
1. Créer une branche feature (`git checkout -b feat/nouvelle-fonctionnalite`)
2. Implémenter avec tests
3. Mettre à jour la documentation si nécessaire
4. Commit avec convention (`git commit -m "feat(scope): description"`)

### Revue et fusion
1. Tests passent localement
2. Code review si applicable
3. Mise à jour Memory Bank si changements significatifs
4. Merge dans main
