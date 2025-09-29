# Workflow de Contribution - WindFlow

## Vue d'Ensemble

Ce document décrit le processus de contribution pour WindFlow, destiné aux contributeurs externes et internes. Il s'appuie sur les bonnes pratiques observées dans la communauté open source.

## Types de Contributions

### 🆕 Nouvelles Fonctionnalités
- **Impact** : Ajout de nouvelles capacités à WindFlow
- **Processus** : Issue → Discussion → Design → Implementation → Review
- **Validation** : Tests complets, documentation, compatibilité

### 🐛 Corrections de Bugs
- **Impact** : Résolution de problèmes existants
- **Processus** : Reproduction → Investigation → Fix → Validation
- **Validation** : Tests de régression, pas d'effet de bord

### 📚 Documentation
- **Impact** : Amélioration de la documentation utilisateur/développeur
- **Processus** : Identification → Rédaction → Review → Publication
- **Validation** : Clarté, exactitude, complétude

### 🔧 Améliorations Techniques
- **Impact** : Refactoring, optimisations, maintenance
- **Processus** : Analyse → Proposition → Implementation → Validation
- **Validation** : Pas de régression, amélioration mesurable

## Process de Contribution

### 1. Préparation

#### Pour les Contributeurs Externes
```bash
# 1. Fork du repository
# Cliquer sur "Fork" sur GitHub

# 2. Clone du fork
git clone git@github.com:VOTRE_USERNAME/windflow.git
cd windflow

# 3. Configuration des remotes
git remote add upstream git@github.com:windflow/windflow.git

# 4. Setup environnement
./install.sh
make setup
```

#### Pour les Contributeurs Internes
```bash
# 1. Clone direct
git clone git@github.com:windflow/windflow.git
cd windflow

# 2. Setup environnement
./install.sh
make setup
```

### 2. Identification du Travail

#### Issues Existantes
1. **Parcourir les Issues** : https://github.com/windflow/windflow/issues
2. **Labels Good First Issue** : Parfait pour débuter
3. **Assignation** : Commenter pour demander l'assignation
4. **Clarification** : Poser des questions si nécessaire

#### Nouvelles Issues
1. **Recherche** : Vérifier qu'elle n'existe pas déjà
2. **Template** : Utiliser le template approprié
3. **Description** : Détailler le problème/besoin
4. **Labels** : bug, enhancement, documentation, etc.

### 3. Développement

#### Création de la Branche
```bash
# Synchronisation
git checkout main
git pull upstream main  # ou origin main pour contributeurs internes

# Branche feature
git checkout -b feature/description-courte

# Ou branche fix
git checkout -b fix/issue-number-description
```

#### Standards de Développement
1. **Suivre les Règles** : Respecter `.clinerules/`
2. **Tests** : Ajouter des tests pour tout nouveau code
3. **Documentation** : Mettre à jour si nécessaire
4. **Commits** : Suivre la convention de commits

#### Développement Continu
```bash
# Développement...
git add .
git commit -m "feat(scope): clear description"

# Push régulier
git push origin feature/description-courte

# Sync avec upstream si nécessaire
git fetch upstream
git rebase upstream/main
```

### 4. Pull Request

#### Préparation de la PR
```bash
# Tests complets
make test-all

# Formatage
make format

# Validation finale
make lint
```

#### Création de la PR
1. **Aller sur GitHub** : Votre fork → Compare & pull request
2. **Base Branch** : `main` (ou `develop` selon la politique)
3. **Titre** : Descriptif et clair
4. **Description** : Utiliser le template PR
5. **Labels** : Ajouter les labels appropriés
6. **Reviewers** : Demander des reviews

#### Template PR
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] E2E tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows the style guidelines
- [ ] Self-review performed
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] No breaking changes introduced

## Related Issues
Fixes #(issue number)

## Screenshots (if applicable)
Add screenshots here
```

### 5. Code Review

#### Attendre les Reviews
- **Patience** : Les reviews peuvent prendre du temps
- **Réactivité** : Répondre rapidement aux commentaires
- **Respect** : Accepter les critiques constructives

#### Répondre aux Commentaires
```bash
# Après feedback
git checkout feature/description-courte

# Corrections
# ... modifications ...

git add .
git commit -m "fix(review): address reviewer feedback"
git push origin feature/description-courte
```

#### Types de Feedback
1. **Changements Requis** : Doivent être adressés
2. **Suggestions** : Amélioration recommandée
3. **Questions** : Clarifications nécessaires
4. **Approbation** : Review positive

### 6. Merge et Finalisation

#### Après Approbation
- **Squash et Merge** : Généralement utilisé
- **Nettoyage** : Suppression de la branche après merge
- **Sync Fork** : Mettre à jour le fork après merge

```bash
# Après merge, nettoyage local
git checkout main
git pull upstream main
git branch -d feature/description-courte
git push origin --delete feature/description-courte
```

## Standards de Qualité

### Code Quality
1. **Linting** : Aucune erreur de linting
2. **Type Safety** : Types Python/TypeScript stricts
3. **Tests** : Couverture maintenue (85%+)
4. **Performance** : Pas de régression
5. **Sécurité** : Audit pour code sensible

### Documentation
1. **Code** : Docstrings pour fonctions publiques
2. **API** : Documentation OpenAPI à jour
3. **User Docs** : README et guides mis à jour
4. **Changelog** : Entrée ajoutée si nécessaire

### Tests
1. **Unitaires** : Pour toute nouvelle logique
2. **Intégration** : Pour nouvelles APIs
3. **E2E** : Pour nouveaux workflows utilisateur
4. **Régression** : Pour corrections de bugs

## Communication

### Channels de Communication
1. **GitHub Issues** : Discussion technique sur problèmes spécifiques
2. **GitHub Discussions** : Questions générales, idées, aide
3. **PR Comments** : Feedback technique sur le code
4. **Discord** : Chat en temps réel (si disponible)

### Bonnes Pratiques
1. **Respectueux** : Ton professionnel et constructif
2. **Clair** : Messages précis et détaillés
3. **Patient** : Réponses peuvent prendre du temps
4. **Recherche** : Vérifier les discussions existantes

### Templates d'Issues

#### Bug Report
```markdown
**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment:**
 - OS: [e.g. Ubuntu 20.04]
 - Browser [e.g. chrome, safari]
 - Version [e.g. 22]

**Additional context**
Add any other context about the problem here.
```

#### Feature Request
```markdown
**Is your feature request related to a problem? Please describe.**
A clear and concise description of what the problem is.

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions.

**Additional context**
Add any other context or screenshots about the feature request here.
```

## Validation et Acceptance

### Critères d'Acceptance
1. **Fonctionnel** : La feature fonctionne comme spécifiée
2. **Technique** : Code respecte les standards WindFlow
3. **Testé** : Tests appropriés ajoutés et passants
4. **Documenté** : Documentation mise à jour
5. **Approuvé** : Au moins 2 reviews positives (projets importants)

### Process de Validation
1. **Auto-validation** : Tests CI/CD passent
2. **Review Technique** : Code review par l'équipe
3. **Test Manual** : Si nécessaire pour UI/UX
4. **Approbation** : Maintainer approuve et merge

### Feedback Loop
- **Itératif** : Corrections → Review → Corrections
- **Constructif** : Feedback explicatif et actionnable
- **Apprentissage** : Opportunité d'amélioration

## Recognition et Remerciements

### Attribution
- **Contributors** : Listés dans README et releases
- **Commit History** : Préservé dans l'historique Git
- **Release Notes** : Contributions mentionnées

### Badges et Statuts
- **First Contributor** : Badge spécial pour première contribution
- **Regular Contributor** : Reconnaissance pour contributions régulières
- **Core Team** : Invitation possible pour contributeurs actifs

## Ressources pour Contributeurs

### Documentation Technique
- [Development Workflow](development-workflow.md)
- [Testing Guidelines](testing-workflow.md)
- [Architecture Overview](../spec/02-architecture.md)
- [Coding Rules](../../.clinerules/README.md)

### Outils Utiles
- [GitHub CLI](https://cli.github.com/) : Gestion GitHub en ligne de commande
- [GitHub Desktop](https://desktop.github.com/) : Interface graphique Git
- [VS Code GitHub Extension](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-pull-request-github)

### Apprentissage
- [Git Tutorial](https://learngitbranching.js.org/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [Open Source Guide](https://opensource.guide/)

## Troubleshooting Contributions

### Problèmes Courants

#### 1. Fork Out of Sync
```bash
# Sync avec upstream
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

#### 2. Conflicts lors du Rebase
```bash
# Résolution interactive
git rebase upstream/main
# Résoudre les conflits dans l'éditeur
git add .
git rebase --continue
```

#### 3. Tests Failing
```bash
# Tests locaux
make test-all

# Reset environnement si nécessaire
make clean
make setup
```

#### 4. PR Trop Grosse
- **Split** : Diviser en plusieurs PRs plus petites
- **Staging** : Créer des PRs intermédiaires
- **Discussion** : Discuter avec l'équipe de l'approche

### Support
- **Issues** : Créer une issue "help wanted"
- **Discussions** : Poser des questions dans GitHub Discussions
- **Mentoring** : Demander l'aide d'un contributeur expérimenté

---

**Rappel** : Chaque contribution, même petite, est précieuse ! L'équipe WindFlow est là pour vous aider dans votre parcours de contribution.
