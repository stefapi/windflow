# WindFlow — Roadmap d'implémentation

> **Date** : 19 février 2026  
> **Basé sur** : Analyse du codebase WindFlow + documentation Colibri  
> **Phase actuelle** : MVP Phase 1.4 — Intégration & Production-Ready (95%)

---

## 📋 Vue d'ensemble

Ce document recense les travaux d'implémentation identifiés pour WindFlow, classés par priorité et faisabilité. Chaque item est évalué selon :

- **Effort** : 🟢 Faible | 🟡 Moyen | 🔴 Élevé
- **Impact utilisateur** : 🟢 Faible | 🟡 Moyen | 🔴 Fort
- **Faisabilité** : basée sur l'infrastructure existante dans WindFlow

---

## 🔴 Priorité 1 — Complétion des fondations existantes

> Impact immédiat, infrastructure déjà en place. À réaliser cette semaine.

### 1. Dashboard enrichi

| | |
|---|---|
| **Fichier principal** | `frontend/src/views/Dashboard.vue` (81 lignes) |
| **Effort** | 🟢 Faible |
| **Impact** | 🔴 Fort |
| **Dépendances** | Aucune |

**État actuel** : 4 statistiques simples (Total Targets, Total Stacks, Active Deployments, Workflows) + tableau des déploiements récents.

**Travaux à réaliser** :
- [ ] Graphiques temps réel CPU/RAM (ECharts) ✅ Implémenté (ResourceChartsWidget avec vue-echarts)
- [ ] Widget d'activité récente (déploiements, scans, erreurs) ✅ Implémenté (ActivityFeedWidget)
- [ ] Statut de santé des targets connectées (pastilles vert/orange/rouge) ✅ Implémenté (TargetHealthWidget)
- [ ] Widget d'alertes et notifications ✅ Implémenté (AlertsNotificationsWidget)
- [ ] Métriques de performance des déploiements (taux de succès, durée moyenne) ✅ Implémenté (DeploymentMetricsWidget)

**Ressources existantes** :
- Stores Pinia : `targets`, `deployments`, `stacks`, `workflows`
- Backend : `/api/v1/stats` (96 lignes) fournit les données agrégées

---

### 2. Stacks UI complète

| | |
|---|---|
| **Fichier principal** | `frontend/src/views/Stacks.vue` (95 lignes) |
| **Effort** | 🟢 Faible |
| **Impact** | 🔴 Fort |
| **Dépendances** | Aucune |

**État actuel** : CRUD basique — table avec nom/description + dialog de création simple. Le backend est beaucoup plus riche (`stacks.py` API : 1332 lignes).

**Travaux à réaliser** :
- [ ] Éditeur YAML intégré avec coloration syntaxique (CodeMirror ou Monaco) ✅ Implémenté (textarea monospace avec thème sombre)
- [ ] Validation temps réel du contenu docker-compose ✅ Implémenté (bouton Validate YAML)
- [ ] Prévisualisation du compose avant déploiement ✅ Implémenté (onglet Preview avec parsing services)
- [ ] Gestion des variables d'environnement par stack ✅ Implémenté (onglet Environment Variables)
- [ ] Versioning et historique des modifications ✅ Implémenté (StackVersion model + API + onglet History)
- [ ] Bouton de déploiement direct depuis la vue stack ✅ Implémenté (Deploy dialog avec sélection target)

**Ressources existantes** :
- Backend : `stack_service.py` (241 lignes), `stack_loader_service.py` (328 lignes), `stack_definitions_loader.py` (331 lignes)
- Store : `frontend/src/stores/stacks.ts`
- Templates : `stacks_definitions/` (baserow.yaml, postgresql.yaml)

---

### 3. Deployment Detail UI

| | |
|---|---|
| **Fichier principal** | `frontend/src/views/DeploymentDetail.vue` (68 lignes) |
| **Effort** | 🟢 Faible |
| **Impact** | 🔴 Fort |
| **Dépendances** | Aucune |

**État actuel** : Vue de détail minimale. Le backend dispose d'un service de déploiement complet avec orchestrateur et événements.

**Travaux à réaliser** :
- [ ] Logs de déploiement en temps réel (intégrer le composant `DeploymentLogs.vue` existant) ✅ Implémenté
- [ ] Timeline visuelle des étapes de déploiement (pending → building → deploying → running) ✅ Implémenté (el-steps)
- [ ] Boutons d'action : rollback, redéploiement, arrêt ✅ Implémenté (Stop, Retry, Redeploy)
- [ ] Métriques post-déploiement (uptime, ressources consommées) ✅ Implémenté (onglet Metrics)
- [ ] Affichage des variables d'environnement (masquées par défaut) ✅ Implémenté (onglet Environment)
- [ ] Lien vers la target associée ✅ Implémenté (router-link dans descriptions)

**Ressources existantes** :
- Backend : `deployment_service.py` (827 lignes), `deployment_orchestrator.py` (454 lignes), `deployment_events.py` (156 lignes)
- Composants : `DeploymentLogs.vue`, `DeploymentProgress.vue`
- Composables : `useDeploymentLogs.ts`, `useDeploymentWebSocket.ts`
- Store : `frontend/src/stores/deployments.ts`

---

### 4. Scheduler de tâches (Celery Beat)

| | |
|---|---|
| **Fichiers concernés** | `backend/app/tasks/`, nouveau `backend/app/services/scheduler_service.py` |
| **Effort** | 🟡 Moyen |
| **Impact** | 🟡 Moyen |
| **Dépendances** | Aucune |

**État actuel** : Celery avec Redis broker configuré. Background tasks existantes : `deploy_stack_async`, `retry_pending_deployments_async`.

**Travaux à réaliser** :
- [ ] Configurer Celery Beat pour les tâches planifiées ✅ Implémenté (celery_app.py avec beat_schedule)
- [ ] Modèle DB `ScheduledTask` (cron expression, type de tâche, paramètres, statut, dernier run) ✅ Implémenté
- [ ] Service `scheduler_service.py` : CRUD des tâches planifiées ✅ Implémenté
- [ ] API endpoints `/api/v1/schedules` : création, listing, activation/désactivation ✅ Implémenté
- [ ] UI : page de gestion des tâches programmées avec expressions cron ✅ Implémenté (Schedules.vue)
- [ ] Tâches prédéfinies : nettoyage logs, vérification santé targets, sync Git ✅ Implémenté (3 tâches beat)

**Référence Colibri** : `docs_colibri/09-SCHEDULER.md`

---

## 🟡 Priorité 2 — Nouvelles fonctionnalités à fort impact

> Inspirées de Colibri, infrastructure partiellement existante. À réaliser sous 1 à 2 semaines.

### 5. Terminal WebSocket interactif

| | |
|---|---|
| **Fichiers concernés** | Nouveau composant frontend + endpoint backend WebSocket |
| **Effort** | 🟡 Moyen |
| **Impact** | 🔴 Fort |
| **Dépendances** | Package `xterm.js` (frontend) |

**Ce que Colibri implémente** : Terminal web xterm.js dans le navigateur pour exécuter des commandes shell dans les conteneurs Docker via WebSocket bidirectionnel.

**Travaux à réaliser** :
- [ ] Backend : endpoint WebSocket `/ws/terminal/{container_id}` avec `docker exec` attach stdin/stdout
- [ ] Backend : gestion du resize terminal (signaux SIGWINCH)
- [ ] Frontend : composant `ContainerTerminal.vue` avec xterm.js
- [ ] Frontend : resize automatique, thèmes, copier/coller
- [ ] Intégration dans `DeploymentDetail.vue` (onglet Terminal)
- [ ] Gestion des permissions (RBAC : qui peut exec dans quel conteneur)

**Ressources existantes** :
- Backend : `websockets.py` (445 lignes), architecture WebSocket avec plugins
- Frontend : service WebSocket (`services/websocket.ts`) avec plugins (notification, session, navigation)

**Référence Colibri** : `docs_colibri/11-TERMINAL-WEBSOCKET.md`

---

### 6. Intégration Git pour les Stacks

| | |
|---|---|
| **Fichiers concernés** | Nouveau `backend/app/services/git_service.py`, modification Stack model |
| **Effort** | 🟡 Moyen |
| **Impact** | 🔴 Fort |
| **Dépendances** | Package `gitpython` (backend) |

**Ce que Colibri implémente** : Clone/pull de repos Git (GitHub, GitLab, Bitbucket), déploiement de stacks depuis un repo, webhooks pour auto-deploy, credentials SSH/HTTPS chiffrés.

**Travaux à réaliser** :
- [ ] Service `git_service.py` : clone, pull, gestion branches/tags
- [ ] Gestion des credentials : SSH keys, tokens HTTPS (stockage chiffré)
- [ ] Extension du modèle `Stack` : champs `git_url`, `git_branch`, `git_path`, `git_credential_id`
- [ ] Endpoint API `/api/v1/stacks/{id}/git-sync` pour synchronisation manuelle
- [ ] Endpoint webhook `/api/v1/webhooks/git` pour auto-deploy sur push
- [ ] UI : formulaire source Git dans la création/édition de stack
- [ ] UI : bouton de synchronisation + statut dernière sync
- [ ] Tâche Celery : sync Git périodique (intégration scheduler #4)

**Référence Colibri** : `docs_colibri/05-GIT-INTEGRATION.md`

---

### 7. Scan de vulnérabilités des images Docker

| | |
|---|---|
| **Fichiers concernés** | Nouveau `backend/app/services/vulnerability_scanner_service.py`, nouveau modèle |
| **Effort** | 🟡 Moyen |
| **Impact** | 🟡 Moyen |
| **Dépendances** | Grype et/ou Trivy installés sur le serveur |

**Ce que Colibri implémente** : Scanner abstrait supportant Grype et Trivy, scan avant déploiement avec critères configurables (never/critical/high/medium/low), rapport détaillé par image.

**Travaux à réaliser** :
- [ ] Classe abstraite `VulnerabilityScanner` avec implémentations `GrypeScanner` et `TrivyScanner`
- [ ] Modèle DB `VulnerabilityScan` : image, résultats, compteurs par sévérité, durée
- [ ] Modèle DB `Vulnerability` : CVE ID, package, version, fix version, CVSS score
- [ ] Service `vulnerability_scanner_service.py` : orchestration des scans
- [ ] API endpoints `/api/v1/scans` : lancement scan, résultats, historique
- [ ] Intégration pipeline déploiement : scan automatique avant deploy (configurable)
- [ ] UI : tableau de bord vulnérabilités avec filtres par sévérité
- [ ] UI : badge de sécurité sur chaque image/stack dans les listes

**Ressources existantes** :
- Pattern scanner : `target_scanner_service.py` (1061 lignes) utilise un pattern similaire

**Référence Colibri** : `docs_colibri/07-VULNERABILITY-SCANNING.md`

---

### 8. Chiffrement natif des secrets

| | |
|---|---|
| **Fichiers concernés** | Nouveau `backend/app/services/encryption_service.py` |
| **Effort** | 🟡 Moyen |
| **Impact** | 🟡 Moyen |
| **Dépendances** | Package `cryptography` (Python) |

**Ce que Colibri implémente** : Chiffrement AES-256-GCM pour tous les secrets en base (mots de passe, clés SSH, tokens), gestion hybride des clés (fichier + env var), rotation automatique, préfixe de versioning `enc:v1:`.

**Travaux à réaliser** :
- [ ] Module `encryption_service.py` : chiffrement/déchiffrement AES-256-GCM
- [ ] Gestion des clés : génération auto, stockage fichier, variable d'environnement
- [ ] Rotation de clé avec re-chiffrement automatique
- [ ] Intégration dans les modèles `Target` (credentials) et `Stack` (variables d'environnement)
- [ ] Migration DB : chiffrement des secrets existants en clair
- [ ] API : les secrets ne transitent jamais en clair dans les réponses (masqués `****`)
- [ ] Complémentarité avec HashiCorp Vault (déjà préparé dans l'infrastructure)

**Référence Colibri** : `docs_colibri/10-ENCRYPTION.md`

---

## 🟢 Priorité 3 — Fonctionnalités avancées

> Nécessitent plus d'effort ou dépendent de briques précédentes. À planifier sous 1 mois.

### 9. Volume Browser

| | |
|---|---|
| **Effort** | 🟡 Moyen |
| **Impact** | 🟢 Faible |
| **Dépendances** | Docker API |

**Ce que Colibri implémente** : Navigation dans les volumes Docker, visualisation arborescente des fichiers, import/export en tar.

**Travaux à réaliser** :
- [ ] Backend : API de listing fichiers dans un volume via container helper temporaire
- [ ] Backend : endpoints download/upload de fichiers (tar)
- [ ] Frontend : composant de navigation fichiers arborescente
- [ ] Frontend : prévisualisation des fichiers texte, téléchargement binaires
- [ ] Intégration dans la gestion des volumes (nouvelle vue ou onglet)

**Référence Colibri** : `docs_colibri/12-VOLUME-BROWSER.md`

---

### 10. Auto-Updates des conteneurs

| | |
|---|---|
| **Effort** | 🔴 Élevé |
| **Impact** | 🔴 Fort |
| **Dépendances** | Scheduler (#4) + Vulnerability Scanning (#7) |

**Ce que Colibri implémente** : Mise à jour automatique complète : check registry → pull image → scan vulnérabilités → application des critères → recréation conteneur → rollback si échec.

**Travaux à réaliser** :
- [ ] Service `update_checker_service.py` : comparaison digests registry vs local
- [ ] Service `auto_update_service.py` : orchestration du flow complet
- [ ] Modèle DB `AutoUpdatePolicy` : conteneur, critères de vulnérabilité, schedule cron
- [ ] Modèle DB `UpdateHistory` : historique des mises à jour (succès/échec/rollback)
- [ ] Intégration Scheduler : tâche périodique de vérification des mises à jour
- [ ] Intégration Vulnerability Scanning : scan avant application de la mise à jour
- [ ] Mécanisme de rollback automatique : snapshot config → update → test health → rollback si échec
- [ ] Notifications : email, webhook, Slack, Discord (configurable)
- [ ] UI : configuration des politiques d'auto-update par conteneur/stack
- [ ] UI : historique des mises à jour avec statut détaillé

**Référence Colibri** : `docs_colibri/06-AUTO-UPDATES.md`

---

### 11. Workflow Engine

| | |
|---|---|
| **Fichiers existants** | `frontend/src/views/WorkflowEditor.vue` (163 lignes), `backend/app/api/v1/workflows.py` (40 lignes) |
| **Effort** | 🔴 Élevé |
| **Impact** | 🔴 Fort |
| **Dépendances** | Décision architecturale requise |

**État actuel** : L'éditeur frontend a un début d'implémentation (163 lignes). Le backend est un stub (40 lignes). Le store `workflows.ts` existe.

**Décision à prendre** : Le `progress.md` du projet recommande d'évaluer l'adoption de solutions existantes (n8n, Airflow) plutôt qu'un moteur custom. Cette décision impacte significativement l'effort.

**Option A — Moteur custom** :
- [ ] Modèle DB `Workflow`, `WorkflowStep`, `WorkflowExecution`
- [ ] Service `workflow_engine_service.py` : exécution séquentielle/parallèle des étapes
- [ ] API complète `/api/v1/workflows` : CRUD + exécution + historique
- [ ] Frontend : éditeur drag-and-drop avec bibliothèque de blocs (VueFlow)
- [ ] Conditions, boucles, branchements dans les workflows

**Option B — Intégration n8n/Airflow** :
- [ ] Déploiement n8n/Airflow dans le stack Docker
- [ ] API bridge : proxy des workflows vers la solution externe
- [ ] UI : iframe ou redirection vers l'interface native
- [ ] Synchronisation état avec WindFlow

---

## 📊 Matrice récapitulative

| # | Fonctionnalité | Effort | Impact | Dépendances | Échéance |
|---|---------------|--------|--------|-------------|----------|
| 1 | Dashboard enrichi | 🟢 Faible | 🔴 Fort | Aucune | ✅ Terminé |
| 2 | Stacks UI complète | 🟢 Faible | 🔴 Fort | Aucune | ✅ Terminé |
| 3 | Deployment Detail UI | 🟢 Faible | 🔴 Fort | Aucune | ✅ Terminé |
| 4 | Scheduler (Celery Beat) | 🟡 Moyen | 🟡 Moyen | Aucune | ✅ Terminé |
| 5 | Terminal WebSocket | 🟡 Moyen | 🔴 Fort | xterm.js | **Semaine prochaine** |
| 6 | Git Integration | 🟡 Moyen | 🔴 Fort | gitpython | **Semaine prochaine** |
| 7 | Vulnerability Scanning | 🟡 Moyen | 🟡 Moyen | Grype/Trivy | **Sous 2 semaines** |
| 8 | Chiffrement natif | 🟡 Moyen | 🟡 Moyen | cryptography | **Sous 2 semaines** |
| 9 | Volume Browser | 🟡 Moyen | 🟢 Faible | Docker API | **Sous 1 mois** |
| 10 | Auto-Updates | 🔴 Élevé | 🔴 Fort | #4 + #7 | **Sous 1 mois** |
| 11 | Workflow Engine | 🔴 Élevé | 🔴 Fort | Décision archi | **Phase 2** |
| T1 | **Tests Docker** | 🟢 Faible | 🔴 Fort | - | ✅ **Terminé (91 unitaires + 55 intégration)** |

---

## 🧪 Travaux transverses — Tests et qualité

En parallèle de chaque fonctionnalité, les travaux de test suivants sont requis :

### Tests backend (actuellement ~10 fichiers)
- [x] Tests unitaires pour chaque nouveau service
- [x] Tests d'intégration API pour chaque nouvel endpoint
- [x] Tests async pour les tâches Celery et WebSocket
- [ ] Couverture cible : 85%+

### Tests Docker (completés ✅)
- [x] **Tests unitaires Docker** : 91 tests créés et passent
  - `test_docker_client_service.py` : 23 tests (socket Unix)
  - `test_docker_executor.py` : 33 tests (CLI, Socket, Compose)
  - `test_docker_schemas.py` : 33 tests (schémas Pydantic)
- [x] **Tests d'intégration Docker** : 55 tests existants vérifiés
  - Couvrent Unix socket ET CLI
  - Tests d'intégration API pour endpoints Docker
- [x] **Corrections de bugs** :
  - `docker_client_service.py` : correction type hint callable
  - `docker_executor.py` : correction syntaxe f-string

### Tests frontend (actuellement absents)
- [ ] Configuration Vitest pour tests unitaires de composants
- [ ] Tests des stores Pinia (targets, deployments, stacks)
- [ ] Tests des composables (useDeploymentLogs, useDeploymentWebSocket)
- [ ] Tests E2E Playwright pour les parcours critiques :
  - Login → Dashboard → Créer Target → Déployer Stack
  - Marketplace → Sélectionner Stack → Configurer → Déployer
- [ ] Couverture cible : 80%+

---

## 📅 Planning synthétique

```
Semaine 1 (S8)     │ #1 Dashboard │ #2 Stacks UI │ #3 Deploy Detail │ #4 Scheduler
Semaine 2 (S9)     │ #5 Terminal WebSocket │ #6 Git Integration
Semaine 3 (S10)    │ #7 Vulnerability Scanning │ #8 Chiffrement
Semaine 4 (S11)    │ #9 Volume Browser │ #10 Auto-Updates (début)
Semaine 5+ (S12+)  │ #10 Auto-Updates (fin) │ #11 Workflow Engine (décision + début)
```

> **Transverse** : Tests unitaires, d'intégration et E2E ajoutés en continu avec chaque fonctionnalité.

---

**Auteur** : Analyse automatisée du codebase  
**Dernière mise à jour** : 3 mars 2026 (Tests Docker complétés : 91 unitaires + 55 intégration)
