# Contribution Guide — WindFlow

Thank you for your interest in contributing to the WindFlow project! This guide details the processes and conventions for contributing effectively to our intelligent Docker container deployment tool.

## About WindFlow

WindFlow is an intelligent web tool that combines a modern user interface, a flexible data exchange system, and artificial intelligence to automate and optimize Docker container deployments on target machines.

### Project Principles

* **API-First:** Every feature must first be available via the REST API
* **Security by Design:** Security integrated at every level
* **Type Safety:** Mandatory Python type hints and strict TypeScript
* **Observability:** Built-in monitoring and logging required
* **Clean Code:** Self-documenting code with tests and documentation

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md):

* Be respectful and inclusive
* Be patient and welcoming
* Be collaborative and constructive
* Embrace constructive feedback

## Types of Contributions

### 🆕 New Features

* **Process:** Issue → Discussion → Design → Implementation → Review
* **Validation:** Comprehensive tests, documentation, compatibility
* **Examples:** New deployment types, AI integrations, optimizations

### 🐛 Bug Fixes

* **Process:** Reproduction → Investigation → Fix → Validation
* **Validation:** Regression tests, no side effects
* **Priority:** Critical bugs handled first

### 📚 Documentation

* **Process:** Identify → Draft → Review → Publish
* **Types:** User, developer, API, architecture documentation
* **Validation:** Clarity, accuracy, completeness

### 🔧 Technical Improvements

* **Process:** Analysis → Proposal → Implementation → Validation
* **Types:** Refactoring, optimizations, maintenance, dependency updates
* **Validation:** No regressions, measurable improvement

## Environment Setup

### Prerequisites

* **Python** 3.11+
* **Node.js** 20+ with pnpm 9+
* **Docker** & Docker Compose
* **Git** with SSH configuration
* **Poetry** for Python dependency management

### Quick Setup

```bash
# 1. Fork and clone the project
git clone git@gitea.yourdomain.com:YOUR_USERNAME/windflow.git
cd windflow

# 2. Automatic installation
./install.sh

# 3. Environment configuration
cp .env.example .env
# Edit .env with your local settings

# 4. Full setup
make setup

# 5. Start development services
make dev
```

### IDE Configuration

#### PyCharm (Backend)

* **Interpreter:** Poetry environment
* **Required plugins:** Python Type Checker (mypy), Pre-commit Hook Plugin
* **Configuration:** Black formatter, pytest runner

#### VS Code (Frontend)

* **Extensions:** Vue Language Features (Volar), strict TypeScript mode, UnoCSS IntelliSense
* **Configuration:** Format on save, Prettier formatter

### Verify Installation

```bash
# Tool checks
make check-deps

# Quick tests
make test-quick

# Launch the UI
make dev
# The app should be available at http://localhost:3000
```

## Contribution Process

### 1. Preparation

#### For External Contributors

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone git@gitea.yourdomain.com:YOUR_USERNAME/windflow.git
cd windflow

# 3. Configure remotes
git remote add upstream git@gitea.yourdomain.com:windflow/windflow.git

# 4. Sync
git fetch upstream
git checkout main
git merge upstream/main
```

#### For Internal Contributors

```bash
# Direct clone
git clone git@gitea.yourdomain.com:windflow/windflow.git
cd windflow
```

### 2. Identify Work

#### Existing Issues

1. **Browse Issues:** [GitHub Issues](https://gitea.yourdomain.com/windflow/windflow/issues)
2. **“Good First Issue” labels:** Perfect for newcomers
3. **Assignment:** Comment to request assignment
4. **Clarification:** Ask questions if needed

#### New Issues

Use the appropriate templates:

* **Bug Report:** Detailed description, reproduction steps, environment
* **Feature Request:** Problem description, proposed solutions, use cases
* **Documentation:** Target section, proposed improvement

### 3. Development

#### Branch Creation

```bash
# Sync with main
git checkout main
git pull upstream main  # or origin main for internal contributors

# Create a branch by type
git checkout -b feature/short-description     # New feature
git checkout -b fix/issue-number-description  # Bug fix
git checkout -b docs/section-updated          # Documentation
git checkout -b refactor/component-name       # Refactor
```

#### Development Standards

**Mandatory Rules:**

1. **Follow Conventions:** Respect the [development rules](.clinerules/README.md)
2. **Type Safety:** Strict Python/TypeScript types are required
3. **Tests:** Add tests for all new code (≥ 85% coverage)
4. **Documentation:** Update docs as needed
5. **Commits:** Follow the [commit convention](COMMIT_CONVENTION.md)

**Development Cycle:**

```bash
# Iterative development
git add .
git commit -m "feat(scope): clear description"

# Push regularly as a backup
git push origin feature/short-description

# Sync with upstream if needed
git fetch upstream
git rebase upstream/main
```

#### Backend (FastAPI)

```bash
# Start in dev mode
make backend

# Continuous tests
make backend-test-watch

# Quality checks
make backend-lint
make backend-format
make backend-typecheck
```

**Recommended structure:**

1. **Model:** `windflow/models/` (SQLAlchemy)
2. **Schema:** `windflow/schemas/` (Pydantic)
3. **Service:** `windflow/services/` (Business logic)
4. **Router:** `windflow/api/` (Endpoints)
5. **Tests:** `tests/` (Unit, integration, E2E)

#### Frontend (Vue.js 3)

```bash
# Start in dev mode
make frontend

# Continuous tests
cd frontend && pnpm test --watch

# Quality checks
make frontend-lint
make frontend-format
make frontend-typecheck
```

**Recommended structure:**

1. **Types:** `src/types/` (TypeScript)
2. **Services:** `src/services/` (API)
3. **Stores:** `src/stores/` (Pinia)
4. **Components:** `src/components/` (Vue)
5. **Pages:** `src/views/` (Routes)
6. **Tests:** `tests/` (Vitest, Playwright)

### 4. Testing & Validation

#### Required Tests

```bash
# Unit tests
make backend-test        # Backend
make frontend-test       # Frontend

# Integration tests
make test-integration    # Full API

# End-to-end tests
make frontend-test-e2e   # User workflows

# Code coverage
make backend-coverage    # Must be ≥ 85%
make frontend-coverage   # Must be ≥ 80%
```

#### Quality Validation

```bash
# Auto-format
make format

# Quality checks
make lint

# Type checking
make typecheck

# Security checks
make security-check

# Full validation
make all
```

### 5. Pull Request

#### PR Preparation

```bash
# Full test suite before submission
make test-all

# Final formatting
make format

# Rebase for a clean history
git rebase upstream/main

# Final push
git push origin feature/short-description
```

#### Creating the PR

1. **Go to GitHub:** Your fork → “Compare & pull request”
2. **Base branch:** `main` (unless otherwise specified)
3. **Title:** Descriptive and clear (follow commit convention)
4. **Description:** Use the template, be thorough
5. **Labels:** feature, bugfix, documentation, etc.
6. **Reviewers:** Request 2+ reviews for substantial changes

#### Pull Request Template

```markdown
## Description
Clear description of the changes made

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Tests
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] E2E tests added/updated
- [ ] Manual tests performed

## Checklist
- [ ] Code follows project guidelines
- [ ] Self-review performed
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] No breaking changes introduced
- [ ] Test coverage maintained

## Related Issues
Fixes #(issue number)

## Screenshots (if applicable)
[Add screenshots here]
```

### 6. Code Review

#### Review Process

1. **Automated Checks:** CI/CD tests, coverage, linting, security
2. **Human Review:**

   * Feature matches specs
   * Compliance with [development rules](.clinerules/)
   * Code quality and readability
   * Appropriate and complete tests
   * Documentation updated
   * Performance (no regression)

#### Responding to Comments

```bash
# After reviewer feedback
git checkout feature/short-description

# Apply changes
# ... modifications per feedback ...

git add .
git commit -m "fix(review): address reviewer feedback"
git push origin feature/short-description

# Re-request review if needed
```

#### Types of Feedback

* **Changes Requested:** Mandatory changes before merge
* **Suggestions:** Recommended improvements
* **Questions:** Clarifications needed
* **Approved:** Positive review, ready to merge

### 7. Merge & Finalization

#### After Approval

* **Squash & Merge:** Typically used to keep a clean history
* **Cleanup:** Automatically delete the branch after merge
* **Sync Fork:** Update your fork after merge

```bash
# After merge, local cleanup
git checkout main
git pull upstream main
git branch -d feature/short-description
git push origin --delete feature/short-description
```

## Quality Standards

### Acceptance Criteria

1. **Functional:** The feature works as specified
2. **Technical:** Code follows WindFlow standards
3. **Tested:** Appropriate tests added and passing (≥ 85% coverage)
4. **Documented:** Documentation updated
5. **Secure:** Security review for sensitive code
6. **Performant:** No performance regression

### Quality Gates

* **Coverage:** Minimum 85% backend, 80% frontend
* **Performance:** No regression > 10%
* **Security:** No critical vulnerabilities
* **Documentation:** README and API docs up to date
* **Linting:** No linting errors

## Git & Conventions

### Commit Convention

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**

* `feat`: New feature
* `fix`: Bug fix
* `docs`: Documentation
* `style`: Code formatting (no logic changes)
* `refactor`: Refactoring without functional change
* `test`: Add/modify tests
* `chore`: Maintenance tasks

**Examples:**

```bash
feat(api): add deployment optimization endpoint
fix(ui): correct responsive layout on mobile devices
docs(readme): update installation instructions
refactor(service): simplify deployment logic for better maintainability
test(backend): add integration tests for authentication
```

### Branching Strategy

```
main                 ← Stable production
├── develop          ← Continuous integration (if used)
├── feature/xxx      ← New features
├── fix/xxx          ← Bug fixes
├── docs/xxx         ← Documentation
└── refactor/xxx     ← Refactoring
```

## Report Bugs

### Required Information

1. **Title:** Clear and descriptive
2. **Reproduction steps:** Detailed and repeatable
3. **Expected behavior:** What should happen
4. **Actual behavior:** What actually happens
5. **Screenshots:** If applicable
6. **Environment:**

   * OS and version
   * Browser and version
   * WindFlow version
   * Specific configuration

### Bug Report Template

```markdown
**Bug Description**
Clear and concise description of the issue.

**Reproduction Steps**
1. Go to '...'
2. Click on '...'
3. Scroll to '...'
4. See the error

**Expected Behavior**
Describe what should happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., Ubuntu 20.04]
- Browser: [e.g., Chrome 91]
- WindFlow Version: [e.g., 1.2.3]

**Additional Context**
Any other relevant information.
```

## Suggest Features

### Feature Request Template

```markdown
**Is your request related to a problem?**
Clear description of the problem or limitation.

**Describe the desired solution**
Clear description of what you want implemented.

**Describe alternatives you’ve considered**
Other solutions or features considered.

**Additional context**
Any other information, screenshots, or examples.
```

## Developer Resources

### Technical Documentation

* [Development Rules](.clinerules/README.md) — Mandatory standards
* [Development Workflow](doc/workflows/development-workflow.md) — Day-to-day process
* [Testing Workflow](doc/workflows/testing-workflow.md) — Testing strategy
* [Architecture](doc/spec/02-architecture.md) — Technical overview
* [Technology Stack](doc/spec/03-technology-stack.md) — Technologies used

### Useful Tools

* [GitHub CLI](https://cli.gitea.yourdomain.com/) — Command-line GitHub management
* [GitHub Desktop](https://desktop.gitea.yourdomain.com/) — Git GUI
* [VS Code GitHub Extension](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-pull-request-github)

### Useful Make Commands

```bash
# Development
make dev                 # Full startup (backend + frontend)
make backend             # Backend only
make frontend            # Frontend only

# Tests
make test-all            # All tests
make test-quick          # Quick tests only
make backend-test        # Backend tests
make frontend-test       # Frontend tests

# Quality
make format              # Auto-formatting
make lint                # Quality checks
make typecheck           # Type checks

# Maintenance
make clean               # Cleanup
make setup               # Initial setup
make outdated            # Check for updates
```

## Communication & Support

### Communication Channels

1. **GitHub Issues:** Technical discussion on specific problems
2. **GitHub Discussions:** General questions, ideas, help
3. **PR Comments:** Technical code feedback
4. **Documentation:** Guides and technical references

### Getting Help

* **Issues:** Create an issue with the “help wanted” label
* **Discussions:** Ask questions in GitHub Discussions
* **Code Review:** Request guidance during review
* **Mentoring:** Contact an experienced contributor

### Communication Best Practices

1. **Respectful:** Professional, constructive tone
2. **Clear:** Precise, detailed messages with context
3. **Patient:** Responses may take time
4. **Do your homework:** Check existing discussions before creating new ones

## Troubleshooting

### Common Issues

#### 1. Fork Out of Sync

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

#### 2. Conflicts During Rebase

```bash
git rebase upstream/main
# Resolve conflicts in your editor
git add .
git rebase --continue
```

#### 3. Tests Failing

```bash
# Reset environment
make clean
make setup

# Isolated tests
make backend-test-unit
make frontend-test-unit
```

#### 4. Docker Issues

```bash
# Full cleanup
make docker-down
docker system prune -af
make docker-build
make docker-up
```

## Recognition

### Contribution Attribution

* **Contributors:** Listed in README and releases
* **Commit History:** Preserved in Git history
* **Release Notes:** Major contributions highlighted
* **Badges:** Recognition for regular contributors

## Useful Links

### Learning

* [Git Tutorial](https://learngitbranching.js.org/)
* [GitHub Flow](https://guides.gitea.yourdomain.com/introduction/flow/)
* [Open Source Guide](https://opensource.guide/)
* [FastAPI Documentation](https://fastapi.tiangolo.com/)
* [Vue.js 3 Guide](https://vuejs.org/guide/)

### WindFlow Specific

* [Architecture Overview](doc/spec/02-architecture.md)
* [API Design](doc/spec/07-api-design.md)
* [Security Guidelines](doc/spec/13-security.md)
* [Deployment Guide](doc/spec/15-deployment-guide.md)

---

**Important Reminder:** Every contribution, even small ones, is valuable! The WindFlow team is here to support you throughout your contribution journey. Don’t hesitate to ask questions and request help.

**Guide version:** 1.0
**Last updated:** 09/29/2025
**Team:** WindFlow
