# Commit Message Convention

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification for standardizing commit messages.

## Format

Each commit message consists of a **header**, a **body**, and a **footer**. The header has a special format that includes a **type**, an optional **scope**, and a **subject**:

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

### Type

The type must be one of the following:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (white-space, formatting, etc.)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies
- **ci**: Changes to our CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

### Scope

The scope is optional and should be a noun describing a section of the codebase:

- **backend**: Changes to the backend code
- **frontend**: Changes to the frontend code
- **api**: Changes to the API
- **db**: Changes to the database
- **auth**: Changes to authentication
- etc.

### Subject

The subject contains a succinct description of the change:

- Use the imperative, present tense: "change" not "changed" nor "changes"
- Don't capitalize the first letter
- No period (.) at the end

### Body

The body should include the motivation for the change and contrast this with previous behavior.

### Footer

The footer should contain any information about **Breaking Changes** and is also the place to reference Gitea issues that this commit closes.

## Examples

```
feat(api): add endpoint for retrieving user profile

Add a new GET /api/users/profile endpoint that returns the authenticated user's profile information.

Closes #123
```

```
fix(frontend): resolve issue with login form submission

The form was not properly handling the submit event, causing the page to reload instead of making an API call.

Fixes #456
```

```
docs: update README with setup instructions

Add detailed instructions for setting up the development environment and running the application locally.
```

```
refactor(backend): simplify error handling middleware

Consolidate error handling logic into a single middleware function to improve code maintainability.
```

## Enforcement

This project uses a custom Python script to enforce the Conventional Commits format. If your commit message does not follow the convention, the commit will be rejected.

To enable the validation, you need to run the setup script:

```bash
./scripts/setup_git_hooks.sh
```

This script configures Git to use our hooks directory, which contains the commit-msg hook that validates commit messages. The validation script is located at `scripts/validate_commit_msg.py` and is called by the Git commit-msg hook.
