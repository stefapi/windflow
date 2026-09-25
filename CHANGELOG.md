# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **STORY-124 — Clés API `wf_ak_`** (P1-3, partie clés API — EPIC-012) : authentification par clé API coexistant avec JWT.
  - Table `api_keys` + modèle `APIKey` et migration Alembic `1241_api_keys` (STORY-124.1) — hash uniquement en base, FK CASCADE, expiration optionnelle, révocation distincte de l'expiration.
  - `ApiKeyService` : génération `wf_ak_` + 48 caractères (`secrets.token_urlsafe`), hash déterministe Argon2 (sel dérivé HMAC-SHA256, lookup par hash — arbitrage F2/STORY-123, divergence « bcrypt » des specs consignée pour STORY-252), création/liste/révocation idempotente/vérification ; schemas Pydantic n'exposant jamais `key_hash` ni la clé brute (affichage unique à la création) (STORY-124.2).
  - Endpoints `POST/GET/DELETE /auth/api-keys` (201 + clé affichée une seule fois, liste sans secrets, révocation scoped 404 sur clé étrangère, rate limiting) et auth par clé dans `get_current_user` via `X-API-Key` ou `Authorization: Bearer wf_ak_…` — résolue avant la voie JWT, RBAC du propriétaire appliqué à l'identique, `last_used_at` throttlé (1 écriture/min/clé) (STORY-124.3).
  - Tests transverses de sécurité : 401/403/422/404, RBAC viewer par clé, isolation multi-users, aucune clé ni hash dans réponses/logs/base, révocation immédiate de bout en bout — 78 tests auth/API keys verts (STORY-124.4).

## Template for Future Releases

## [x.y.z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Vulnerabilities fixed
