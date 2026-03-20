# Contexte Projet

WindFlow est un outil web intelligent de déploiement de conteneurs Docker vers des machines cibles, avec support multi-cibles (Docker, K8s, VMs, physiques), UI moderne et intégration IA (LiteLLM).

Objectif du dépôt : construire/faire évoluer le nouveau logiciel en réutilisant du code existant, en gardant un niveau de qualité élevé (tests, sécurité, observabilité).

Priorités (ordre) :
1) API-first : toute fonctionnalité doit être disponible via API REST avant UI/CLI.
2) Sécurité by design (OWASP, least privilege, secrets, RBAC).
3) Observabilité native (logs structurés, métriques, corrélation).
4) Réutilisation intelligente du code legacy (pas de copier-coller aveugle).
5) Maintenabilité : modular monolith d’abord ; hexagonale si complexité augmente.
