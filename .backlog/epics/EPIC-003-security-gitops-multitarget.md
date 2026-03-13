# EPIC-003 : Sécurité, GitOps & Multi-Machines

**Statut :** TODO
**Priorité :** Haute
**Phase Roadmap :** 3 & 4 — Q3–Q4 2026 (Juillet–Décembre)
**Version cible :** 1.2 → 1.3

## Vision

Cette epic transforme WindFlow d'un outil de homelab en une **plateforme de confiance pour gérer une infrastructure en production**. Elle adresse les trois piliers qui manquent après les phases 1 et 2 :

1. **Multi-Target** : piloter plusieurs machines (physiques, VMs, cloud) depuis une seule instance WindFlow via SSH.
2. **GitOps** : déployer des stacks depuis un dépôt Git, avec auto-deploy on push et rollback sur commit.
3. **Sécurité renforcée** : secrets chiffrés, audit trail, scanning de vulnérabilités, backup automatisé.

C'est l'epic qui fait passer WindFlow du « sympa pour tester » au « fiable pour la prod ».

### Valeur Business
- Débloquer le multi-machines : un self-hoster avec 2-3 serveurs ne veut qu'un seul dashboard
- GitOps répond aux attentes des développeurs (infrastructure as code, reproductibilité)
- Sécurité et audit sont des prérequis pour tout usage sérieux (et pour la confiance communautaire)
- Backup automatisé réduit le risque #1 du self-hosting : la perte de données
- Pré-requis pour la Phase 5 (IA, workflows, SDK communautaire)

### Utilisateurs cibles
- **Self-hoster multi-machines** : a 2-5 serveurs (RPi, NUC, dédié) et veut un seul point de contrôle
- **Développeur DevOps** : pousse du code → déploiement automatique, rollback si problème
- **Admin sécurité** : veut savoir qui a fait quoi, quand, et s'assurer que les images sont saines
- **Petit team/PME** : besoin d'audit trail et de backup pour conformité minimale

## Liste des Stories liées

### Multi-Target SSH (Phase 3)
- [ ] STORY-301 : API REST ajout/suppression machines cibles via SSH (clés, credentials)
- [ ] STORY-302 : Déploiement de containers Docker sur machines distantes via SSH
- [ ] STORY-303 : Gestion VMs sur hyperviseurs distants (libvirt, Proxmox via SSH/API)
- [ ] STORY-304 : Vue consolidée de toutes les machines et services (dashboard multi-target)
- [ ] STORY-305 : Monitoring basique par machine cible (CPU, RAM, disque, réseau)
- [ ] STORY-306 : Agent léger optionnel (binaire statique ARM/x86, collecte métriques, auto-discovery)

### Git Integration & GitOps (Phase 4)
- [ ] STORY-311 : Stacks depuis dépôt Git (git_url, branch, path) — API + UI
- [ ] STORY-312 : Sync automatique (pull périodique configurable)
- [ ] STORY-313 : Webhook auto-deploy on push (GitHub, GitLab, Gitea)
- [ ] STORY-314 : Rollback vers un commit précédent
- [ ] STORY-315 : Auth dépôts Git (SSH keys et tokens)

### Sécurité — Secrets (Phase 4)
- [ ] STORY-321 : Chiffrement des secrets stockés en base (AES-256-GCM)
- [ ] STORY-322 : Rotation de secrets (manuelle + programmée)
- [ ] STORY-323 : Variables d'environnement sécurisées par stack
- [ ] STORY-324 : Plugin Vault — HashiCorp Vault déployé et intégré (secrets dynamiques)

### Sécurité — Audit & Scanning (Phase 4)
- [ ] STORY-331 : Audit trail complet — qui a fait quoi, quand (modèle, API, UI)
- [ ] STORY-332 : Logs d'audit immuables + export
- [ ] STORY-333 : Plugin Trivy — scan vulnérabilités images Docker avant déploiement
- [ ] STORY-334 : Plugin Trivy — dashboard vulnérabilités + alertes severity high/critical
- [ ] STORY-335 : Plugin Trivy — scan planifié des images existantes

### Backup (Phase 3 — Plugin)
- [ ] STORY-341 : Plugin Restic — backup automatique volumes et configs
- [ ] STORY-342 : Plugin Restic — scheduling (cron-like depuis l'UI)
- [ ] STORY-343 : Plugin Restic — restore sélectif depuis l'UI

### Kubernetes basique (Phase 3 — optionnel)
- [ ] STORY-351 : Connexion clusters Kubernetes (kubeconfig)
- [ ] STORY-352 : Déploiement manifests YAML et Helm charts
- [ ] STORY-353 : Dashboard cluster — pods, deployments, services, logs
- [ ] STORY-354 : Terminal dans pods Kubernetes

## Notes de conception

- **API-first** : toutes les opérations (multi-target, git, audit, secrets) sont exposées via API REST avant UI/CLI
- **Multi-target** : le core orchestre via SSH — pas besoin d'agent obligatoire. L'agent est optionnel pour les métriques enrichies
- **SSH** : utiliser asyncssh pour la connexion asynchrone. Credentials SSH stockés chiffrés (STORY-321)
- **GitOps** : intégration Git via dulwich (pure Python) ou subprocess git — webhook endpoint dédié avec validation signature (HMAC)
- **Audit trail** : table dédiée append-only, indexée par user/action/timestamp. Corrélation avec les correlation IDs existants
- **Secrets** : chiffrement AES-256-GCM avec clé dérivée (PBKDF2). Jamais de secret en clair en base ni dans les logs
- **Plugin Trivy** : valide le plugin system de l'EPIC-001 avec un plugin de type extension (scan intégré au workflow de déploiement)
- **Plugin Restic** : valide le plugin system avec un plugin de type service (daemon de backup)
- **Observabilité** : métriques multi-target (latence SSH, status machines, déploiements ok/ko par target)
- **Sécurité RBAC** : les opérations multi-target et secrets doivent respecter le RBAC existant (admin-only pour certaines actions)

## Critères de succès (Definition of Done)

### Multi-Target
- [ ] Piloter 2+ machines distantes depuis une seule instance WindFlow
- [ ] Déployer des containers sur une machine distante via SSH
- [ ] Dashboard consolidé affichant toutes les machines et services

### GitOps
- [ ] Déployer une stack depuis un dépôt Git (git push → deploy automatique)
- [ ] Rollback fonctionnel vers un commit précédent
- [ ] Support GitHub, GitLab, Gitea webhooks

### Sécurité
- [ ] Secrets chiffrés en base (AES-256-GCM)
- [ ] Audit trail complet et consultable depuis l'UI
- [ ] Scan vulnérabilités fonctionnel via plugin Trivy
- [ ] Backup automatisé fonctionnel via plugin Restic

### Qualité
- [ ] Documentation API OpenAPI à jour
- [ ] Couverture tests ≥ 80%
- [ ] Tests d'intégration SSH (avec mock ou container SSH)
- [ ] Zero secret en clair dans les logs (validé par test)

## Risques
| Risque | Impact | Mitigation |
|--------|--------|------------|
| Complexité SSH multi-plateforme | Élevé | asyncssh + tests avec conteneur SSH ; commencer par Linux uniquement |
| Latence réseau multi-target | Moyen | Timeouts configurables, operations async, retry avec backoff |
| Sécurité des clés SSH stockées | Élevé | Chiffrement AES-256-GCM, accès restreint (RBAC admin), audit |
| Webhook flood (DoS) | Moyen | Rate limiting sur l'endpoint webhook, validation signature HMAC |
| Scope trop large (2 phases combinées) | Moyen | Prioriser : Multi-target → Secrets → Audit → Git → Trivy → Restic → K8s |
| Kubernetes trop complexe | Moyen | Marqué optionnel — livrer le basique uniquement (read-only + deploy YAML) |

## Dépendances
- Phase 1 Core Platform (✅ livré)
- EPIC-001 Plugin System (requis pour plugins Trivy, Restic, Vault)
- EPIC-002 VM Management (requis pour multi-target VMs distantes)
- RBAC existant (✅ livré en Phase 1 — à étendre pour multi-target)

## Séquençage recommandé

```
Phase 3 (Q3)                          Phase 4 (Q4)
┌──────────────────────┐              ┌──────────────────────┐
│ Multi-Target SSH     │──────────────│ Git Integration      │
│ Plugin Restic        │              │ Secrets chiffrés     │
│ K8s basique (opt.)   │              │ Audit trail          │
│ Monitoring machines  │              │ Plugin Trivy         │
│                      │              │ Plugin Vault         │
└──────────────────────┘              └──────────────────────┘
```
