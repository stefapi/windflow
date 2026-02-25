# Sécurité (obligatoire)

## Principes
- OWASP Top 10
- least privilege
- zero trust
- chiffrement en transit et au repos
- ne jamais logger de données sensibles

## AuthN/AuthZ
- JWT + refresh
- RBAC côté API (source de vérité)
- validation inputs côté client ET serveur (Pydantic côté backend)
- protection CSRF pour opérations critiques

## Secrets
- HashiCorp Vault obligatoire
- jamais de secrets en dur
- rotation + audit trail

## Scans
- bandit/semgrep côté backend
- npm audit côté frontend
