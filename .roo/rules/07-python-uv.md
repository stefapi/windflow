# 07 — Environnement Python et uv

## 1. Principes

- `uv` gère l'environnement virtuel et les dépendances du backend et du CLI (migration terminée, EPIC-016).
- Toute commande Python passe par `uv run` ou par une cible `make` qui l'appelle. **Interdit** : appeler le `python`, le `pytest` ou le `pip` du système, activer un environnement à la main dans un script.

## 2. Fichiers

- `pyproject.toml` (racine) : métadonnées PEP 621 ; dépendances d'exécution ; outils de développement ; configuration de black, isort, mypy, flake8 et pytest.
- `uv.lock` : commité, jamais édité à la main.
- Pas de `requirements.txt` commité ; un export temporaire est admis pour un outil d'audit.
- `libvirt-python` est hors graphe résolu (sdist sans wheel, exige libvirt-dev sur l'hôte) : install ciblée via `make install-vm`, import défensif dans le code (STORY-255).

## 3. Commandes

| Besoin | Commande |
| --- | --- |
| Installer en développement | `uv sync` (appelé par `make setup`) |
| Ajouter une dépendance | `uv add <paquet>` ; outil de développement : `uv add --dev <paquet>` |
| Retirer une dépendance | `uv remove <paquet>` |
| Mettre à jour une dépendance | `uv lock --upgrade-package <paquet>`, puis `uv sync` |
| Exécuter un outil | `uv run <commande>` |

**Interdit** : `pip install`, `uv pip install`, `poetry`, `pipenv`, `conda`, édition manuelle de `uv.lock`.

## 4. Contraintes de version

Contraintes larges dans `pyproject.toml` (`>=x.y,<x+1`) ; la version exacte est portée par `uv.lock`. Toute dépendance suit `05-tech-stack.md` §5.

## 5. Configuration de l'application

- Point d'entrée : `backend/app/config.py`, classe `Settings` (pydantic-settings), instance unique obtenue par `get_settings()`.
- **Interdit** : `os.environ` ou `os.getenv` ailleurs que dans `config.py`.
- Variable manquante ou invalide pour un secret ou une URL de service : échec explicite au démarrage, jamais de valeur par défaut silencieuse.
- Règle d'or : une variable ajoutée au code est ajoutée **dans le même commit** à `Settings`, à `env.example` (et `.env.prod.example` si elle concerne le déploiement), avec commentaire et valeur d'exemple non secrète (`50` §6).
