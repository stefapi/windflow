# 03 — Glossaire : termes métier et noms de code

Règles d'usage :

- Code, base de données, API, événements et identifiants sont en anglais ; interface, documentation, messages et commentaires sont en français.
- Le glossaire canonique du produit est [`docs/general_specs/19-glossaire.md`](../../docs/general_specs/19-glossaire.md) : en cas de divergence entre un chapitre de spécification et ce glossaire, le glossaire prévaut. La présente règle n'en recopie pas le contenu ; elle fixe les noms de code ci-dessous et les pièges de traduction.
- Un terme métier a un seul nom de code dans tout le dépôt (backend, frontend, base, API, événements, CLI).
- Terme absent : l'ajouter au glossaire canonique et, si un nom de code est nécessaire, au tableau ci-dessous dans le même changement (validation du propriétaire, `02` §5).

Pièges à éviter :

- **tâche** planifiée (scheduler) → `task` ; **tâche** d'un plan d'implémentation → étape du contrat, sans objet de code ;
- **pile/stack générique** → réserver `stack` aux **Stacks WindFlow** (`03-modele-compute.md`) ; une pile Docker Compose brute non managée est un objet `discovered` ;
- `host` ≠ `machine` ≠ `cluster` : un Host est **adopté**, jamais déployé ; un cluster Kubernetes ou Proxmox multi-nœuds est un `cluster`, jamais un `host` ;
- **adoption** → `adoption`/`adopted` (origine), jamais `import` ;
- **découverte/réconciliation** → `discovery` / `reconciliation`, jamais `scan` dans les noms d'API (`scan` reste admis dans l'UI « Scan & Diagnostics »).

## Noms de code canoniques (noyau)

| Terme | Code | Précision |
| --- | --- | --- |
| Workload (générique) | `workload` | App, Machine ou Host |
| App (conteneur/service) | `app` | Profils `docker_container`, `docker_compose`, `helm_release`, `k8s_manifest`, `app_native_service` |
| Machine (VM) | `machine` | Profils `vm_kvm`, `vm_lxd`, `vm_incus`, `vm_virtualbox`, `vm_lxc` |
| Host (substrat adopté) | `host` | Profils `host_baremetal`, `host_proxmox`, `host_remote_docker` |
| Cluster | `cluster` | Types `kubernetes`, `proxmox`, `docker_swarm` ; membres via `cluster_members` |
| Relation d'hébergement | `host_id` XOR `machine_id` XOR `cluster_id` sur `apps` | Triple XOR — jamais plusieurs renseignés |
| Profil | `profile` | Sous-type technique d'un workload |
| Adaptateur de workload | `WorkloadAdapter` (`AppAdapter`, `MachineAdapter`, `HostAdapter`) | Traduit les verbes universels en opérations natives |
| Origine | `origin` (`managed` / `adopted` / `external`) | Énumération `WorkloadOrigin` |
| Stack WindFlow | `stack` | Environnement nommé, WindFlow source de truth |
| Objet découvert | `discovered` | Lecture seule jusqu'à adoption |
| Déploiement | `deployment` | Exécution d'un déploiement vers une cible |
| Définition de stack | `stack_definition` | YAML de `stacks_definitions/` |
| Plugin | `plugin` | Extension applicative (`docs/general_specs/11-plugins.md`) |
| Marketplace | `marketplace` | Catalogue de stacks/plugins (`12-marketplace.md`) |
| Verbe universel | Ouvrir, Démarrer/Arrêter/Redémarrer, Mettre à jour, Sauvegarder, Configurer, Logs, Console | Exposés par famille dans l'UI |
| Action contextuelle | `contextual_action` | Action spécifique au profil, menu `[⋯ Plus]` |
| Bus d'événements | `Bus` (`backend/app/core/events.py`) | `InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel, canal `windflow:events` |
| Websocket (temps réel) | `websocket` | Module `backend/app/websocket/` (`21`) |
| Utilisateur | `user` | Rôles `viewer < operator < admin < super_admin` (`40` §3) |
| Journal d'audit | `audit_log` | Modèle `AuditLog` + `GET /admin/audit` |
| Cache unifié | `get_cache()` | Redis si configuré, sinon mémoire locale bornée (`46`) |
| Disjoncteur | `circuit_breaker` | `backend/app/core/resilience.py`, séries `windflow_circuit_breaker_*` |
