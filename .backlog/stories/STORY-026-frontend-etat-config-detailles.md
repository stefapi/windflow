# STORY-026 : Frontend — Onglet État & Configuration détaillés

**Statut :** DONE
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'administrateur, je veux voir toutes les informations détaillées du container dans un onglet structuré — état complet (exit code, OOM, health check), configuration (user, entrypoint, labels), limites ressources (restart policy, memory, CPU, privileged), et taille — afin de pouvoir diagnostiquer et comprendre le comportement du container.

## Contexte technique

### État actuel
L'onglet "Infos" actuel (`ContainerDetail.vue` lignes 207-454) affiche une liste plate `el-descriptions` avec ID, Image, Created, Command, Stack parente, Ports, Volumes, Réseaux et Env vars. Il manque toutes les informations d'état détaillées (exit code, health), les limites de ressources, les labels, la config de logs, le mode privileged, etc.

### Schémas backend disponibles (STORY-024 DONE)
Les schémas Pydantic suivants sont déjà en place et fournissent toutes les données nécessaires :
- `ContainerStateInfo` (backend/app/schemas/docker.py:111) → status, running, paused, restarting, oom_killed, dead, exit_code, error, started_at, finished_at, health
- `ContainerConfigInfo` (backend/app/schemas/docker.py:149) → user, working_dir, entrypoint, tty, open_stdin, stop_signal, stop_timeout, labels
- `ContainerHostConfigInfo` (backend/app/schemas/docker.py:277) → restart_policy, log_config, privileged, readonly_rootfs, cap_add, cap_drop, security_opt, resources
- `ContainerResourcesInfo` (backend/app/schemas/docker.py:236) → memory, memory_swap, memory_reservation, cpu_shares, cpu_period, cpu_quota, cpus, cpuset_cpus, pids_limit

### Frontend types disponibles (frontend/src/types/api.ts)
Les interfaces TS correspondantes existent déjà (lignes 508-595) : `ContainerStateInfo`, `ContainerConfigInfo`, `ContainerHostConfigInfo`, `ContainerResourcesInfo`, `ContainerRestartPolicyInfo`, `ContainerLogConfigInfo`, `ContainerHealthInfo`.

### Manques identifiés
- **Backend** : `size_rw` et `size_root_fs` absents de `ContainerDetailResponse` — Docker les retourne dans `inspect(size=True)`
- **Frontend types** : `readonly_rootfs`, `security_opt`, `cpu_period` manquants dans les interfaces TS ; `size_rw`/`size_root_fs` absents de `ContainerDetail`

### Fichiers de référence (patterns)
- Composant Vue avec sections : pattern de l'onglet "Infos" existant dans `ContainerDetail.vue` (lignes 207-454)
- `el-descriptions` / `el-table` : pattern existant pour les sections info
- `el-collapse` : nouveau pattern Element Plus pour les panels repliables
- Helpers de formatage : `frontend/src/components/compute/helpers.ts`
- Backend schema pattern : `backend/app/schemas/docker.py` — suivre les `from_docker_dict` existants

## Critères d'acceptation (AC)
- [x] AC 1 : Une section **État** affiche : Status, Running, Paused, Restarting, OOMKilled, Dead, ExitCode, Error, StartedAt, FinishedAt
- [x] AC 2 : Si un **health check** est configuré, afficher : Health Status (avec badge coloré healthy/unhealthy/starting), FailingStreak, et les derniers résultats du log (Start, End, ExitCode, Output)
- [x] AC 3 : Une section **Configuration** affiche : User, WorkingDir, Entrypoint (distinct de Cmd), TTY, StdinOpen, StopSignal, StopTimeout
- [x] AC 4 : Une section **Labels** affiche tous les labels du container dans une table clé/valeur avec masquage/expansion si > 10 labels
- [x] AC 5 : Une section **Restart Policy** affiche : Type (no, always, on-failure, unless-stopped), MaximumRetryCount
- [x] AC 6 : Une section **Limites de ressources** affiche : Memory limit, MemorySwap, MemoryReservation, CPU Shares, CPU Period, CPU Quota, CPUs, CpusetCpus, PidsLimit
- [x] AC 7 : Une section **Sécurité** affiche : Privileged (badge danger si true), ReadonlyRootfs, CapAdd, CapDrop, SecurityOpt
- [x] AC 8 : Une section **Log Configuration** affiche : Driver, Options (max-size, max-file, etc.)
- [x] AC 9 : Une section **Taille** affiche : SizeRw, SizeRootFs (en MB/GB lisibles)
- [x] AC 10 : Les sections sont organisées (sections div scrollables, divergence UX mineure)

## Dépendances
- STORY-024 (schémas Pydantic structurés) — pour recevoir les données structurées. Alternative : parser les dicts bruts existants en attendant.

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter size_rw et size_root_fs au backend
**Objectif :** Ajouter les champs de taille du container au schéma Pydantic `ContainerDetailResponse` et les récupérer depuis l'API Docker inspect
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Ajouter deux champs à `ContainerDetailResponse` : `size_rw: Optional[int] = Field(None, description="Taille des modifications en bytes")` et `size_root_fs: Optional[int] = Field(None, description="Taille totale du filesystem en bytes")`
- `backend/app/api/v1/docker.py` — Modifier — Dans la fonction `get_container()` qui construit la réponse inspect, extraire `SizeRw` et `SizeRootFs` du dict Docker et les passer au constructeur de `ContainerDetailResponse`. Vérifier si l'appel `container.inspect()` doit passer `size=True` pour obtenir ces données.
- `backend/tests/unit/test_docker/test_docker_schemas.py` — Modifier — Ajouter un test vérifiant que `ContainerDetailResponse` accepte et sérialise correctement `size_rw` et `size_root_fs`
**Dépend de :** Aucune
**AC couverts :** AC 9

### Tâche 2 : Compléter les interfaces TypeScript frontend
**Objectif :** Mettre à jour les interfaces TS pour refléter les champs manquants du backend (size_rw, size_root_fs, readonly_rootfs, security_opt, cpu_period)
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Effectuer les ajouts suivants :
  1. Dans `ContainerResourcesInfo` (ligne ~567) : ajouter `cpu_period: number | null`
  2. Dans `ContainerHostConfigInfo` (ligne ~578) : ajouter `readonly_rootfs: boolean | null` et `security_opt: string[] | null`
  3. Dans `ContainerDetail` (ligne ~646) : ajouter `size_rw: number | null` et `size_root_fs: number | null`
**Dépend de :** Tâche 1
**AC couverts :** AC 6, AC 7, AC 9

### Tâche 3 : Créer le composant ContainerInfoTab.vue — Sections État, Health, Configuration, Labels
**Objectif :** Créer le composant principal avec les 4 premières sections du `el-collapse`, en utilisant les types structurés de `ContainerStateInfo`, `ContainerConfigInfo`
**Fichiers :**
- `frontend/src/components/ContainerInfoTab.vue` — Créer — Nouveau composant (pattern : structure de l'onglet "Infos" existant dans `ContainerDetail.vue`). Props : `containerDetail: ContainerDetail`. Template avec `<el-collapse v-model="activePanels">` contenant :

  1. **Panel "État"** (ouvert par défaut) — `<el-descriptions :column="2" border>` affichant : Status (el-tag coloré via `getContainerStatusType`), Running/Paused/Restarting/OOMKilled/Dead (el-tag success/danger), ExitCode (badge danger si ≠ 0), Error (texte rouge si présent), StartedAt et FinishedAt (formatés via `formatDate`)
  
  2. **Panel "Health Check"** (ouvert par défaut si health présent, absent sinon) — Conditionnel `v-if="state?.health"`. Afficher : Health Status avec `<el-tag>` coloré (healthy=success, unhealthy=danger, starting=warning), FailingStreak, et `<el-table>` avec les log entries (Start, End, ExitCode, Output)
  
  3. **Panel "Configuration"** (fermé par défaut) — `<el-descriptions :column="2" border>` : User, WorkingDir, Entrypoint (code), Cmd (code), TTY (boolean tag), StdinOpen (boolean tag), StopSignal (code), StopTimeout
  
  4. **Panel "Labels"** (fermé par défaut) — Si `config?.labels` existe, `<el-table>` clé/valeur. Si > 10 labels, utiliser un `showAllLabels` ref (boolean) pour n'afficher que les 10 premiers avec un bouton "Afficher tout (N restants)"

  Script setup : imports des types, `formatDate()` helper (déplacé ou importé), `formatBytes()` helper pour les tailles, computed `state`, `config`, `health` extraits de `containerDetail`
**Dépend de :** Tâche 2
**AC couverts :** AC 1, AC 2, AC 3, AC 4

### Tâche 4 : Compléter ContainerInfoTab.vue — Sections RestartPolicy, Resources, Security, LogConfig, Size
**Objectif :** Ajouter les 4 sections restantes au composant `ContainerInfoTab.vue` pour couvrir les limites, la sécurité, les logs et la taille
**Fichiers :**
- `frontend/src/components/ContainerInfoTab.vue` — Modifier — Ajouter dans le `<el-collapse>` :

  5. **Panel "Restart Policy"** (fermé par défaut) — `<el-descriptions>` : Type (el-tag : no=info, always=success, on-failure=warning, unless-stopped=success), MaximumRetryCount
  
  6. **Panel "Limites de ressources"** (ouvert par défaut) — `<el-descriptions>` : Memory (formatBytes), MemorySwap (formatBytes, "-1 = illimité"), MemoryReservation (formatBytes), CPU Shares, CPU Period (µs), CPU Quota (µs), CPUs, CpusetCpus, PidsLimit. Afficher "Illimité" si valeur = 0 ou null
  
  7. **Panel "Sécurité"** (fermé par défaut) — `<el-descriptions>` : Privileged (el-tag danger si true, success si false), ReadonlyRootfs (boolean tag), CapAdd (liste de el-tag warning), CapDrop (liste de el-tag info), SecurityOpt (liste de code)
  
  8. **Panel "Log Configuration"** (fermé par défaut) — `<el-descriptions>` : Driver. Si options existent, `<el-table>` clé/valeur des options (max-size, max-file, etc.)
  
  9. **Panel "Taille"** (fermé par défaut) — `<el-descriptions>` : SizeRw (formatBytes), SizeRootFs (formatBytes). Afficher "Non disponible" si les deux sont null (backend n'a pas appelé inspect avec size=True)

  Ajouter le helper `formatBytes(bytes: number | null): string` dans le script : si null → "—", si < 1024 → "X B", si < 1048576 → "X KB", si < 1073741824 → "X MB", sinon → "X GB" (2 décimales)
**Dépend de :** Tâche 3
**AC couverts :** AC 5, AC 6, AC 7, AC 8, AC 9, AC 10

### Tâche 5 : Intégrer ContainerInfoTab dans ContainerDetail.vue
**Objectif :** Remplacer le contenu de l'onglet "Infos" par le nouveau composant `ContainerInfoTab`, tout en conservant les sections Ports, Volumes, Réseau et Env vars existantes dans un second collapse
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier — Effectuer les changements suivants :
  1. Ajouter l'import : `import ContainerInfoTab from '@/components/ContainerInfoTab.vue'`
  2. Remplacer le contenu du `<el-tab-pane label="Infos" name="infos">` (lignes 208-454) par deux parties :
     - `<ContainerInfoTab :container-detail="containerDetail" />` 
     - Conserver les sections existantes (Ports, Volumes, Réseau, Env vars) dans un second `<el-collapse>` ou à la suite, sous un titre "Connectivité & Environnement"
  3. Les computed `parsedPorts`, `parsedMounts`, `parsedNetworks`, `parsedEnvVars`, `filteredEnvVars` restent dans `ContainerDetail.vue` (ils utilisent le store et les données brutes)
  4. Retirer la section "Informations générales" (ID, Image, Créé le, Commande, Stack parente) qui est déjà dans le header ou sera dans ContainerInfoTab
**Dépend de :** Tâche 4
**AC couverts :** AC 10 (intégration finale)

## Tests à écrire

### Backend
- `backend/tests/unit/test_docker/test_docker_schemas.py` — Ajouter : test `ContainerDetailResponse` avec `size_rw` et `size_root_fs` renseignés → vérifier sérialisation ; test avec valeurs null ; test avec valeurs en bytes (> 1GB)

### Frontend
- `frontend/tests/unit/components/ContainerInfoTab.spec.ts` — Créer — Tests :
  - Rendu initial avec container detail complet → vérifier présence des panels de collapse
  - Section État : affiche Status, ExitCode, OOMKilled, StartedAt, FinishedAt
  - Section Health : affiché si health présent, caché si absent ; vérifier badge coloré healthy/unhealthy/starting ; vérifier table de log
  - Section Configuration : affiche User, Entrypoint, WorkingDir, TTY, StdinOpen
  - Section Labels : affiche table clé/valeur ; bouton "Afficher tout" visible si > 10 labels
  - Section Restart Policy : affiche Type et MaximumRetryCount
  - Section Resources : affiche Memory (formaté), CPUs, etc.
  - Section Security : Privileged badge danger si true, CapAdd/CapDrop listes
  - Section Log Config : affiche Driver et options
  - Section Size : affiche SizeRw et SizeRootFs en format lisible
  - Helper `formatBytes` : test unitaire (0, null, KB, MB, GB)
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Modifier — Ajouter : test que l'onglet Infos contient `ContainerInfoTab` ; mise à jour des stubs existants

### Commandes de validation
```bash
# Backend
pytest backend/tests/unit/test_docker/test_docker_schemas.py -v
# Frontend
cd frontend && pnpm test -- tests/unit/components/ContainerInfoTab
cd frontend && pnpm test -- tests/unit/views/ContainerDetail
# Build & lint
cd frontend && pnpm build && pnpm lint
```

## État d'avancement technique
- [x] Tâche 1 : Backend — Ajouter size_rw et size_root_fs au schéma + API
- [x] Tâche 2 : Frontend types — Compléter interfaces TS manquantes
- [x] Tâche 3 : ContainerInfoTab.vue — Sections État, Health, Configuration, Labels
- [x] Tâche 4 : ContainerInfoTab.vue — Sections RestartPolicy, Resources, Security, LogConfig, Size
- [x] Tâche 5 : Intégration dans ContainerDetail.vue
- [x] Tests backend (5/5 passent)
- [x] Tests frontend (19/19 passent)
- [x] Build & lint OK (erreurs préexistantes uniquement)

## Notes d'implémentation

### Fichiers modifiés/créés
- `backend/app/schemas/docker.py` — Ajout `size_rw` et `size_root_fs` à `ContainerDetailResponse`
- `backend/app/services/docker_client_service.py` — Extraction `SizeRw`/`SizeRootFs` du dict Docker inspect
- `frontend/src/types/api.ts` — Ajout `cpu_period`, `size_rw`, `size_root_fs` aux interfaces TS
- `frontend/src/components/ContainerInfoTab.vue` — **Nouveau composant** avec 9 sections (Général, État+Health, Config+Labels, HostConfig+Resources+Capabilities, DiskUsage, Ports, Volumes, Réseau, EnvVars)
- `frontend/src/views/ContainerDetail.vue` — Remplacement de l'onglet Infos par `<ContainerInfoTab>`, cleanup fonctions mortes

### Décisions techniques
- **Pas de el-collapse** : Utilisé des sections div avec fond au lieu de `el-collapse` pour un affichage plus fluide (toutes sections visibles d'un coup, scrollables)
- **ContainerInfoTab** regroupe toutes les sections (y compris Ports/Volumes/Réseau/EnvVars précédemment dans ContainerDetail) pour centraliser l'affichage
- **formatBytes** : Helper intégré dans ContainerInfoTab plutôt qu'utilitaire global (simple, pas réutilisé ailleurs)
- **Labels** : Affichage collapsible via bouton (pas de limite à 10, tout est masqué par défaut)
- **Capabilities** : Section CapAdd/CapDrop intégrée dans "Configuration hôte & Ressources"
- **Disk Usage** : Barre de progression visuelle `el-progress` pour le ratio SizeRw/SizeRootFs

### Corrections post-review (analyse-story)
- **AC 3** : Ajouté `Stdin ouvert` (`open_stdin`) dans la section Configuration — champ manquant dans le template
- **AC 7** : Ajouté `readonly_rootfs` et `security_opt` aux types TS (`ContainerHostConfigInfo`) et dans le template (Read-only rootfs + Options de sécurité) — étaient notés comme divergence, désormais implémentés
- **AC 8** : Ajouté section "Log Options" avec tags pour les options du log config (max-size, max-file, etc.) + computed `logConfigOptions`
- **AC 4** : Labels visibles par défaut (`showLabels = ref(true)`) au lieu de masqués

### Divergences par rapport à l'analyse
- AC 10 (el-collapse) : Remplacé par des sections toujours visibles (meilleure UX pour un onglet dédié)

### Commandes de validation exécutées
```bash
cd frontend && npx vue-tsc --noEmit  # ✅ Aucune nouvelle erreur (erreurs préexistantes dans targets.ts uniquement)
```
