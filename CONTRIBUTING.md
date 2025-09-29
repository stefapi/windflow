# Guide de Contribution - WindFlow

Merci de votre intérêt pour contribuer au projet WindFlow ! Ce guide détaille les processus et conventions pour contribuer efficacement à notre outil intelligent de déploiement de containers Docker.

## À Propos de WindFlow

WindFlow est un outil web intelligent qui combine une interface utilisateur moderne, un système d'échange de données flexible, et une intelligence artificielle pour automatiser et optimiser les déploiements de containers Docker sur des machines cibles.

### Principes du Projet
- **API-First** : Toute fonctionnalité doit d'abord être disponible via l'API REST
- **Security by Design** : Sécurité intégrée à tous les niveaux
- **Type Safety** : Usage obligatoire des type hints Python et TypeScript strict
- **Observabilité** : Monitoring et logging natifs obligatoires
- **Clean Code** : Code auto-documenté avec tests et documentation

## Code de Conduite

En participant à ce projet, vous acceptez de respecter notre [Code de Conduite](CODE_OF_CONDUCT.md) :
- Soyez respectueux et inclusif
- Soyez patient et accueillant
- Soyez collaboratif et constructif
- Acceptez les critiques constructives

## Types de Contributions

### 🆕 Nouvelles Fonctionnalités
- **Processus** : Issue → Discussion → Design → Implementation → Review
- **Validation** : Tests complets, documentation, compatibilité
- **Exemples** : Nouveaux types de déploiement, intégrations IA, optimisations

### 🐛 Corrections de Bugs
- **Processus** : Reproduction → Investigation → Fix → Validation
- **Validation** : Tests de régression, pas d'effet de bord
- **Priorité** : Bugs critiques traités en priorité

### 📚 Documentation
- **Processus** : Identification → Rédaction → Review → Publication
- **Types** : Documentation utilisateur, développeur, API, architecture
- **Validation** : Clarté, exactitude, complétude

### 🔧 Améliorations Techniques
- **Processus** : Analyse → Proposition → Implementation → Validation
- **Types** : Refactoring, optimisations, maintenance, mise à jour dépendances
- **Validation** : Pas de régression, amélioration mesurable

## Configuration de l'Environnement

### Prérequis
- **Python** 3.11+
- **Node.js** 20+ avec pnpm 9+
- **Docker** & Docker Compose
- **Git** avec configuration SSH
- **Poetry** pour la gestion des dépendances Python

### Installation Rapide
```bash
# 1. Fork et clone du projet
git clone git@github.com:VOTRE_USERNAME/windflow.git
cd windflow

# 2. Installation automatique
./install.sh

# 3. Configuration environnement
cp .env.example .env
# Éditer .env avec vos paramètres locaux

# 4. Setup complet
make setup

# 5. Démarrage des services de développement
make dev
```

### Configuration IDE

#### PyCharm (Backend)
- **Interpéteur** : Poetry Environment
- **Plugins requis** : Python Type Checker (mypy), Pre-commit Hook Plugin
- **Configuration** : Black formatter, pytest runner

#### VS Code (Frontend)
- **Extensions** : Vue Language Features (Volar), TypeScript strict mode, UnoCSS IntelliSense
- **Configuration** : Format on save, Prettier formatter

### Vérification de l'Installation
```bash
# Vérification des outils
make check-deps

# Tests rapides
make test-quick

# Lancement de l'interface
make dev
# L'application devrait être accessible sur http://localhost:3000
```

## Processus de Contribution

### 1. Préparation

#### Pour les Contributeurs Externes
```bash
# 1. Fork du repository sur GitHub
# 2. Clone du fork
git clone git@github.com:VOTRE_USERNAME/windflow.git
cd windflow

# 3. Configuration des remotes
git remote add upstream git@github.com:windflow/windflow.git

# 4. Synchronisation
git fetch upstream
git checkout main
git merge upstream/main
```

#### Pour les Contributeurs Internes
```bash
# Clone direct
git clone git@github.com:windflow/windflow.git
cd windflow
```

### 2. Identification du Travail

#### Issues Existantes
1. **Parcourir les Issues** : [GitHub Issues](https://github.com/windflow/windflow/issues)
2. **Labels "Good First Issue"** : Parfait pour débuter
3. **Assignation** : Commenter pour demander l'assignation
4. **Clarification** : Poser des questions si nécessaire

#### Nouvelles Issues
Utilisez les templates appropriés :
- **Bug Report** : Description détaillée, étapes de reproduction, environnement
- **Feature Request** : Description du besoin, solutions envisagées, cas d'usage
- **Documentation** : Section concernée, amélioration proposée

### 3. Développement

#### Création de la Branche
```bash
# Synchronisation avec la branche principale
git checkout main
git pull upstream main  # ou origin main pour contributeurs internes

# Création de la branche selon le type
git checkout -b feature/description-courte     # Nouvelle fonctionnalité
git checkout -b fix/issue-number-description   # Correction de bug
git checkout -b docs/section-updated          # Documentation
git checkout -b refactor/component-name       # Refactoring
```

#### Standards de Développement

**Règles Obligatoires :**
1. **Suivre les Conventions** : Respecter [les règles de développement](.clinerules/README.md)
2. **Type Safety** : Types Python/TypeScript stricts obligatoires
3. **Tests** : Ajouter des tests pour tout nouveau code (85% de couverture minimum)
4. **Documentation** : Mettre à jour la documentation si nécessaire
5. **Commits** : Suivre la [convention de commits](COMMIT_CONVENTION.md)

**Cycle de Développement :**
```bash
# Développement itératif
git add .
git commit -m "feat(scope): description claire"

# Push régulier pour sauvegarde
git push origin feature/description-courte

# Synchronisation avec upstream si nécessaire
git fetch upstream
git rebase upstream/main
```

#### Backend (FastAPI)
```bash
# Démarrage en mode développement
make backend

# Tests en continu
make backend-test-watch

# Validation qualité
make backend-lint
make backend-format
make backend-typecheck
```

**Structure recommandée :**
1. **Modèle** : `windflow/models/` (SQLAlchemy)
2. **Schema** : `windflow/schemas/` (Pydantic)
3. **Service** : `windflow/services/` (Logique métier)
4. **Router** : `windflow/api/` (Endpoints)
5. **Tests** : `tests/` (Unit, integration, E2E)

#### Frontend (Vue.js 3)
```bash
# Démarrage en mode développement
make frontend

# Tests en continu
cd frontend && pnpm test --watch

# Validation qualité
make frontend-lint
make frontend-format
make frontend-typecheck
```

**Structure recommandée :**
1. **Types** : `src/types/` (TypeScript)
2. **Services** : `src/services/` (API)
3. **Stores** : `src/stores/` (Pinia)
4. **Composants** : `src/components/` (Vue)
5. **Pages** : `src/views/` (Routes)
6. **Tests** : `tests/` (Vitest, Playwright)

### 4. Tests et Validation

#### Tests Obligatoires
```bash
# Tests unitaires
make backend-test        # Backend
make frontend-test       # Frontend

# Tests d'intégration
make test-integration    # API complète

# Tests end-to-end
make frontend-test-e2e   # Workflows utilisateur

# Couverture de code
make backend-coverage    # Doit être ≥ 85%
make frontend-coverage   # Doit être ≥ 80%
```

#### Validation Qualité
```bash
# Formatage automatique
make format

# Vérifications de qualité
make lint

# Type checking
make typecheck

# Tests de sécurité
make security-check

# Validation complète
make all
```

### 5. Pull Request

#### Préparation de la PR
```bash
# Tests complets avant soumission
make test-all

# Formatage final
make format

# Rebase pour historique propre
git rebase upstream/main

# Push final
git push origin feature/description-courte
```

#### Création de la PR
1. **Aller sur GitHub** : Votre fork → "Compare & pull request"
2. **Base Branch** : `main` (sauf indication contraire)
3. **Titre** : Descriptif et clair (suivre convention commits)
4. **Description** : Utiliser le template, être exhaustif
5. **Labels** : feature, bugfix, documentation, etc.
6. **Reviewers** : Demander 2+ reviews pour les changements importants

#### Template de Pull Request
```markdown
## Description
Description claire des changements apportés

## Type de Changement
- [ ] Correction de bug (changement non-breaking)
- [ ] Nouvelle fonctionnalité (changement non-breaking)
- [ ] Changement breaking (correction ou fonctionnalité qui casserait l'existant)
- [ ] Mise à jour de documentation

## Tests
- [ ] Tests unitaires ajoutés/mis à jour
- [ ] Tests d'intégration ajoutés/mis à jour
- [ ] Tests E2E ajoutés/mis à jour
- [ ] Tests manuels effectués

## Checklist
- [ ] Le code suit les guidelines du projet
- [ ] Auto-review effectué
- [ ] Documentation mise à jour
- [ ] Tests passent localement
- [ ] Aucun changement breaking introduit
- [ ] Couverture de tests maintenue

## Issues Liées
Fixes #(numéro d'issue)

## Captures d'Écran (si applicable)
[Ajouter des captures d'écran ici]
```

### 6. Code Review

#### Processus de Review
1. **Automated Checks** : Tests CI/CD, coverage, linting, security
2. **Human Review** : 
   - Fonctionnalité conforme aux specs
   - Respect des [règles de développement](.clinerules/)
   - Qualité et lisibilité du code
   - Tests appropriés et complets
   - Documentation mise à jour
   - Performance (pas de régression)

#### Répondre aux Commentaires
```bash
# Après feedback des reviewers
git checkout feature/description-courte

# Apporter les corrections
# ... modifications selon feedback ...

git add .
git commit -m "fix(review): address reviewer feedback"
git push origin feature/description-courte

# Re-demander une review si nécessaire
```

#### Types de Feedback
- **Changes Requested** : Modifications obligatoires avant merge
- **Suggestions** : Améliorations recommandées
- **Questions** : Clarifications nécessaires
- **Approved** : Review positive, prêt pour merge

### 7. Merge et Finalisation

#### Après Approbation
- **Squash et Merge** : Généralement utilisé pour garder un historique propre
- **Nettoyage** : Suppression automatique de la branche après merge
- **Sync Fork** : Mettre à jour le fork après merge

```bash
# Après merge, nettoyage local
git checkout main
git pull upstream main
git branch -d feature/description-courte
git push origin --delete feature/description-courte
```

## Standards de Qualité

### Critères d'Acceptance
1. **Fonctionnel** : La feature fonctionne comme spécifiée
2. **Technique** : Code respecte les standards WindFlow
3. **Testé** : Tests appropriés ajoutés et passants (85%+ couverture)
4. **Documenté** : Documentation mise à jour
5. **Sécurisé** : Audit sécurité pour code sensible
6. **Performant** : Pas de régression de performance

### Quality Gates
- **Coverage** : 85% minimum backend, 80% minimum frontend
- **Performance** : Pas de régression > 10%
- **Security** : Aucune vulnérabilité critique
- **Documentation** : README et API docs à jour
- **Linting** : Aucune erreur de linting

## Git et Conventions

### Convention de Commits
```
type(scope): description

[optional body]

[optional footer]
```

**Types :**
- `feat` : Nouvelle fonctionnalité
- `fix` : Correction de bug
- `docs` : Documentation
- `style` : Formatage code (sans changement logique)
- `refactor` : Refactoring sans changement fonctionnel
- `test` : Ajout/modification de tests
- `chore` : Tâches de maintenance

**Exemples :**
```bash
feat(api): add deployment optimization endpoint
fix(ui): correct responsive layout on mobile devices
docs(readme): update installation instructions
refactor(service): simplify deployment logic for better maintainability
test(backend): add integration tests for authentication
```

### Stratégie de Branches
```
main                 ← Production stable
├── develop          ← Intégration continue (si utilisée)
├── feature/xxx      ← Nouvelles fonctionnalités
├── fix/xxx          ← Corrections de bugs
├── docs/xxx         ← Documentation
└── refactor/xxx     ← Refactoring
```

## Rapporter des Bugs

### Informations Requises
1. **Titre** : Clair et descriptif
2. **Étapes de reproduction** : Détaillées et reproductibles
3. **Comportement attendu** : Ce qui devrait se passer
4. **Comportement actuel** : Ce qui se passe vraiment
5. **Captures d'écran** : Si applicable
6. **Environnement** :
   - OS et version
   - Navigateur et version
   - Version WindFlow
   - Configuration spécifique

### Template Bug Report
```markdown
**Description du Bug**
Description claire et concise du problème.

**Étapes de Reproduction**
1. Aller à '...'
2. Cliquer sur '...'
3. Faire défiler vers '...'
4. Voir l'erreur

**Comportement Attendu**
Description de ce qui devrait se passer.

**Captures d'Écran**
Si applicable, ajouter des captures d'écran.

**Environnement :**
- OS: [ex. Ubuntu 20.04]
- Navigateur: [ex. Chrome 91]
- Version WindFlow: [ex. 1.2.3]

**Contexte Additionnel**
Toute autre information pertinente.
```

## Suggérer des Fonctionnalités

### Template Feature Request
```markdown
**Le problème est-il lié à un problème existant ?**
Description claire du problème ou de la limitation.

**Décrivez la solution souhaitée**
Description claire de ce que vous voulez voir implémenté.

**Décrivez les alternatives considérées**
Autres solutions ou fonctionnalités envisagées.

**Contexte Additionnel**
Toute autre information, capture d'écran, ou exemple.
```

## Ressources de Développement

### Documentation Technique
- [Règles de Développement](.clinerules/README.md) - Standards obligatoires
- [Workflow de Développement](doc/workflows/development-workflow.md) - Processus quotidien
- [Workflow de Test](doc/workflows/testing-workflow.md) - Stratégie de test
- [Architecture](doc/spec/02-architecture.md) - Vue d'ensemble technique
- [Stack Technologique](doc/spec/03-technology-stack.md) - Technologies utilisées

### Outils Utiles
- [GitHub CLI](https://cli.github.com/) - Gestion GitHub en ligne de commande
- [GitHub Desktop](https://desktop.github.com/) - Interface graphique Git
- [VS Code GitHub Extension](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-pull-request-github)

### Commandes Make Utiles
```bash
# Développement
make dev                 # Démarrage complet (backend + frontend)
make backend            # Backend seul
make frontend           # Frontend seul

# Tests
make test-all           # Tous les tests
make test-quick         # Tests rapides seulement
make backend-test       # Tests backend
make frontend-test      # Tests frontend

# Qualité
make format             # Formatage automatique
make lint               # Vérifications de qualité
make typecheck          # Vérification des types

# Maintenance
make clean              # Nettoyage
make setup              # Configuration initiale
make outdated           # Vérification des mises à jour
```

## Communication et Support

### Channels de Communication
1. **GitHub Issues** : Discussion technique sur problèmes spécifiques
2. **GitHub Discussions** : Questions générales, idées, aide
3. **PR Comments** : Feedback technique sur le code
4. **Documentation** : Guides et références techniques

### Obtenir de l'Aide
- **Issues** : Créer une issue avec le label "help wanted"
- **Discussions** : Poser des questions dans GitHub Discussions
- **Code Review** : Demander des conseils lors du review
- **Mentoring** : Contacter un contributeur expérimenté

### Bonnes Pratiques Communication
1. **Respectueux** : Ton professionnel et constructif
2. **Clair** : Messages précis et détaillés avec contexte
3. **Patient** : Les réponses peuvent prendre du temps
4. **Recherche** : Vérifier les discussions existantes avant de créer

## Troubleshooting

### Problèmes Courants

#### 1. Fork Out of Sync
```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

#### 2. Conflits lors du Rebase
```bash
git rebase upstream/main
# Résoudre les conflits dans l'éditeur
git add .
git rebase --continue
```

#### 3. Tests Failing
```bash
# Reset environnement
make clean
make setup

# Tests isolés
make backend-test-unit
make frontend-test-unit
```

#### 4. Problèmes Docker
```bash
# Nettoyage complet
make docker-down
docker system prune -af
make docker-build
make docker-up
```

## Recognition

### Attribution des Contributions
- **Contributors** : Listés dans README et releases
- **Commit History** : Préservé dans l'historique Git
- **Release Notes** : Contributions importantes mentionnées
- **Badges** : Recognition pour contributeurs réguliers

## Liens Utiles

### Apprentissage
- [Git Tutorial](https://learngitbranching.js.org/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [Open Source Guide](https://opensource.guide/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue.js 3 Guide](https://vuejs.org/guide/)

### WindFlow Spécifique
- [Architecture Overview](doc/spec/02-architecture.md)
- [API Design](doc/spec/07-api-design.md)
- [Security Guidelines](doc/spec/13-security.md)
- [Deployment Guide](doc/spec/15-deployment-guide.md)

---

**Rappel Important** : Chaque contribution, même petite, est précieuse ! L'équipe WindFlow est là pour vous accompagner dans votre parcours de contribution. N'hésitez pas à poser des questions et à demander de l'aide.

**Version du guide :** 1.0  
**Dernière mise à jour :** 29/09/2025  
**Équipe :** WindFlow
