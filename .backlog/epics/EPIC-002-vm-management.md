# EPIC-002 : Gestion des Machines Virtuelles (KVM & Proxmox)

**Statut :** TODO
**Priorité :** Haute
**Phase Roadmap :** 2 — Q2 2026 (Avril–Juin)
**Version cible :** 1.1

## Vision

La gestion des VMs est la **différenciation principale** de WindFlow face à Portainer, Coolify ou CasaOS qui ne gèrent que Docker. WindFlow ambitionne d'être le **panneau de contrôle unifié** pour containers ET machines virtuelles, depuis une seule interface.

L'objectif est de livrer :
1. Le support **KVM/QEMU via libvirt** : CRUD VMs, snapshots, cloud-init, disques qcow2.
2. Le support **Proxmox VE via API** : VMs + LXC, backup/restore, vue nodes.
3. Une **console VNC/SPICE** intégrée dans l'UI web.
4. Un **Volume Browser** pour naviguer et éditer les fichiers dans les volumes Docker et disques VMs.
5. Un **mode léger ARM** pour tourner sur Raspberry Pi 4+ avec empreinte < 512 Mo.

### Valeur Business
- Positionne WindFlow sur un marché différent : homelab complet, pas juste Docker
- Adresse les utilisateurs Proxmox qui cherchent une UI plus simple
- Le mode léger ARM élargit massivement la base d'utilisateurs potentiels
- Répond à la core promise produit : « piloter conteneurs ET VMs depuis une interface unique »

### Utilisateurs cibles
- **Homelab avec Proxmox** : veut une interface unifiée pour containers Docker + VMs KVM/LXC
- **Développeur** : lance des VMs de test avec cloud-init rapidement
- **Self-hoster sur Raspberry Pi** : utilise WindFlow en mode léger pour gérer ses services
- **Petit infra avec serveur dédié** : KVM natif sans dépendre de Proxmox

## Liste des Stories liées

### KVM/QEMU via libvirt
- [ ] STORY-201 : Détection automatique de libvirt sur la machine cible
- [ ] STORY-202 : API REST CRUD machines virtuelles (create, read, update, delete, start, stop, reboot)
- [ ] STORY-203 : Gestion snapshots et clones de VMs
- [ ] STORY-204 : Gestion disques (qcow2, raw) — création, redimensionnement, conversion
- [ ] STORY-205 : Support images ISO et cloud-init (templating)
- [ ] STORY-206 : Console VNC/SPICE intégrée à l'UI web (WebSocket proxy)
- [ ] STORY-207 : UI — Page de gestion VMs (liste, détail, actions, métriques basiques)

### Proxmox VE
- [ ] STORY-211 : Connexion API Proxmox (auth token, configuration)
- [ ] STORY-212 : CRUD VMs Proxmox (create, read, start, stop, delete)
- [ ] STORY-213 : Gestion conteneurs LXC Proxmox
- [ ] STORY-214 : Snapshots, backup et restore via API Proxmox
- [ ] STORY-215 : Vue nodes et ressources Proxmox (CPU, RAM, stockage par node)

### Volume Browser & Stockage
- [ ] STORY-221 : API CRUD volumes Docker + cleanup automatique volumes orphelins
- [ ] STORY-222 : Volume Browser — navigation arborescente dans les volumes
- [ ] STORY-223 : Volume Browser — upload/download de fichiers
- [ ] STORY-224 : Volume Browser — preview fichiers (texte, images, logs) + éditeur basique
- [ ] STORY-225 : Gestion disques VM (qcow2/raw) — snapshots disques

### Réseau Docker (core)
- [ ] STORY-231 : API CRUD networks Docker (bridge, overlay, macvlan)
- [ ] STORY-232 : Isolation réseau par environnement

### Mode Léger ARM
- [ ] STORY-241 : Option SQLite au lieu de PostgreSQL pour le core
- [ ] STORY-242 : Option cache en-mémoire au lieu de Redis
- [ ] STORY-243 : Profil d'installation léger (`install.sh --light`)
- [ ] STORY-244 : Build multi-arch (arm64 + amd64) de toutes les images core
- [ ] STORY-245 : Tests CI sur architecture ARM (QEMU ou runner ARM)
- [ ] STORY-246 : Validation empreinte mémoire core < 512 Mo RAM

## Notes de conception

- **API-first** : toutes les opérations VM (CRUD, snapshots, console) sont exposées via API REST avant UI
- **Abstraction** : couche d'abstraction VM Engine (interface commune pour libvirt et Proxmox) — permet d'ajouter d'autres hyperviseurs plus tard (VirtualBox…)
- **WebSocket** : console VNC/SPICE via WebSocket proxy (réutiliser le pattern du terminal container existant)
- **SQLite mode** : utiliser le même ORM (SQLAlchemy 2.0) avec dialect SQLite — migrations Alembic compatibles
- **Sécurité** : credentials Proxmox stockés chiffrés, accès libvirt via socket Unix (least privilege)
- **Tests** : mock libvirt et API Proxmox pour les tests unitaires ; tests d'intégration avec QEMU minimal
- **Observabilité** : métriques VM (CPU, RAM, disk I/O) exposées via /metrics pour Prometheus

## Critères de succès (Definition of Done)
- [ ] CRUD VMs fonctionnel via libvirt (create, start, stop, delete, snapshot)
- [ ] Console VNC/SPICE accessible depuis le navigateur
- [ ] Cloud-init fonctionnel (créer une VM préconfigurée en un clic)
- [ ] Connexion Proxmox VE fonctionnelle (CRUD VMs + LXC)
- [ ] Volume Browser fonctionnel (navigation, upload/download, preview)
- [ ] WindFlow core tourne sur Raspberry Pi 4 (4 Go) en mode léger (SQLite, < 512 Mo RAM)
- [ ] Build multi-arch CI opérationnel
- [ ] API Networks Docker CRUD fonctionnelle
- [ ] Documentation API OpenAPI à jour
- [ ] Couverture tests ≥ 80%

## Risques
| Risque | Impact | Mitigation |
|--------|--------|------------|
| Complexité libvirt | Élevé | Commencer par les opérations CRUD basiques, ajouter snapshots/cloud-init ensuite |
| API Proxmox instable entre versions | Moyen | Tester sur Proxmox 7.x et 8.x, documenter les versions supportées |
| Performance SQLite sous charge | Moyen | Recommandé uniquement pour usage léger (<50 containers), PostgreSQL pour le reste |
| Console VNC latence réseau | Moyen | Compression, adaptative quality, fallback noVNC |
| RPi trop limité pour certains scénarios | Faible | Documenter clairement les limites du mode léger |

## Dépendances
- Phase 1 Core Platform (✅ livré)
- WebSocket infrastructure existante (✅ terminal container déjà implémenté)
- EPIC-001 Plugin System (souhaitable mais non bloquant — les VMs sont core, pas plugin)
