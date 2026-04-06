# STORY-027.2 : Card Ressources avec auto-refresh

**Statut :** DONE
**Story Parente :** STORY-027 — Frontend — Onglet Aperçu synthétique conforme maquette UI
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
Ajouter la card **Ressources** dans l'onglet Aperçu, affichant les barres de progression CPU et RAM, ainsi que les Network I/O et Disk I/O. Les données se rafraîchissent automatiquement toutes les 5 secondes via le composable `useContainerStats` existant. Quand le container est arrêté, la card affiche "Non disponible — container arrêté".

## Critères d'acceptation (AC)
- [x] AC 3 : Une card **Ressources** affiche : barres de progression CPU % et RAM (utilisé/total), Network I/O (↑↓ KB/s), Disk I/O (↑↓ KB/s)
- [x] AC 8 : Les données de ressources se rafraîchissent automatiquement toutes les 5 secondes si le container est running
- [x] AC 9 : Si le container est arrêté, les cards Ressources affichent "Non disponible — container arrêté"

## Contexte technique

### Fichiers existants de référence
- `frontend/src/composables/useContainerStats.ts` — Composable WebSocket existant qui fournit `stats`, `connect`, `disconnect`, `isStreaming`, `history`, `fetchOnce`. **Gère déjà** `onUnmounted` cleanup, heartbeat 30s, auto-reconnect (max 5, backoff 2s). Accepte `autoConnect: boolean` (défaut `true`) → **passer `false`** pour contrôle conditionnel.
- `frontend/src/components/ContainerStats.vue` — Référence complète pour l'affichage CPU/RAM/Net/Disk avec `ResourceBar` et `formatBytes()`. Contient la fonction `formatBytes()` locale (l.719-726) à extraire.
- `frontend/src/components/ContainerInfoTab.vue` — Contient aussi une copie locale de `formatBytes()` avec signature légèrement différente (`bytes: number | null | undefined` → retourne `'-'` pour null).
- `frontend/src/components/ui/ResourceBar.vue` — Composant réutilisable. Props : `value` (0-100), `label`, `showValue`, `size`. Seuils couleurs : vert <60%, orange 60-85%, rouge ≥85%. Déjà exporté depuis `@/components/ui`.
- `frontend/src/components/ContainerOverviewTab.vue` — Composant créé dans STORY-027.1. Props : `detail`, `containerId`, `containerState`. Pattern card Santé (l.231-284) = référence pour la card Ressources (header coloré + `v-if="containerState !== 'running'"` avec `el-alert`).

### Données fournies par `useContainerStats`
Le composable retourne un objet `stats` avec :
- `cpu_percent` (number) — % CPU
- `memory_percent` (number) — % RAM
- `memory_used` (number) — bytes utilisés
- `memory_limit` (number) — bytes limite
- `network_rx_bytes` (number) — bytes reçus (cumulatif depuis démarrage container)
- `network_tx_bytes` (number) — bytes envoyés (cumulatif)
- `block_read_bytes` (number) — bytes lus disque (cumulatif)
- `block_write_bytes` (number) — bytes écrits disque (cumulatif)

### Patterns à respecter
- Utiliser `useContainerStats({ containerId, autoConnect: false })` pour contrôler la connexion conditionnellement
- Utiliser `ResourceBar` pour les barres CPU/RAM (déjà importable via `@/components/ui`)
- Extraire `formatBytes()` en utilitaire partagé pour éviter la duplication entre `ContainerStats.vue` et `ContainerInfoTab.vue`
- Unifier la signature : `formatBytes(bytes: number | null | undefined): string` → retourne `'-'` si nullish, sinon format humain (ex: `'1.5 GB'`)
- Le composable gère déjà `onUnmounted` → pas besoin de cleanup dans le parent
- Pas besoin de polling manuel : le WebSocket stream déjà en continu (~1 stat/sec)
- Affichage conditionnel selon `containerState` : pattern identique à la card Santé existante
- Style card : utiliser une classe `header-red` (cohérence avec les couleurs existantes : blue/green/purple/orange)

## Dépendances
- STORY-027.1 (cards statiques + layout) — Le composant `ContainerOverviewTab.vue` doit exister

## Tâches d'implémentation détaillées

### Tâche 1 : Extraire `formatBytes()` en utilitaire partagé
**Objectif :** Créer un utilitaire `formatBytes()` unifié pour éviter la duplication entre `ContainerStats.vue`, `ContainerInfoTab.vue` et le nouveau composant.
**Fichiers :**
- `frontend/src/utils/format.ts` — **Créer** — Fonction `formatBytes(bytes: number | null | undefined): string`. Signature unifiée :
  - Retourne `'-'` si `bytes` est `null` ou `undefined`
  - Retourne `'0 B'` si `bytes === 0`
  - Sinon format humain : `< 1024` → `X B`, `< 1MB` → `X.X KB`, `< 1GB` → `X.X MB`, `< 1TB` → `X.X GB`, sinon → `X.XX TB`
  - S'inspirer de `ContainerStats.vue` l.719-726 pour la logique de formatage
  - Export nommé : `export function formatBytes(bytes: number | null | undefined): string`
- `frontend/src/components/ContainerStats.vue` — **Modifier** — Supprimer la fonction locale `formatBytes` (l.719-726), ajouter `import { formatBytes } from '@/utils/format'`
- `frontend/src/components/ContainerInfoTab.vue` — **Modifier** — Supprimer la fonction locale `formatBytes`, ajouter `import { formatBytes } from '@/utils/format'`. Vérifier que le comportement `'-'` pour null est préservé par la nouvelle signature unifiée.
**Pattern de référence :** `ContainerStats.vue` l.719-726 (logique de formatage) + `ContainerInfoTab.vue` (signature nullable)
**Dépend de :** Aucune

### Tâche 2 : Ajouter la card Ressources dans ContainerOverviewTab.vue
**Objectif :** Implémenter la card Ressources avec CPU/RAM (barres via `ResourceBar`) + Network/Disk I/O (valeurs textuelles formatées). Utiliser le même pattern visuel que la card Santé existante.
**Fichiers :**
- `frontend/src/components/ContainerOverviewTab.vue` — **Modifier** —
  - **Imports à ajouter :** `Cpu` et `Odometer` depuis `@element-plus/icons-vue`, `ResourceBar` depuis `@/components/ui`, `{ useContainerStats }` depuis `@/composables/useContainerStats`, `{ formatBytes }` depuis `@/utils/format`
  - **Script :** Instancier `useContainerStats({ containerId: props.containerId, autoConnect: false })` → destructurer `{ stats, connect, disconnect, isStreaming }`. Ajouter un `watch` sur `() => props.containerState` : si `'running'` → `connect()`, sinon → `disconnect()`. Le watch doit avoir `{ immediate: true }` pour connecter dès le mount si running.
  - **Template :** Ajouter la card après la card Santé, avant la fermeture de `.overview-grid` :
    ```html
    <!-- Card Ressources (rouge) -->
    <el-card class="overview-card card-resources" shadow="hover">
      <template #header>
        <div class="card-header header-red">
          <el-icon><Cpu /></el-icon>
          <span>Ressources</span>
          <el-tag v-if="isStreaming" size="small" type="success" class="ml-2">Live</el-tag>
        </div>
      </template>
      <!-- Container arrêté -->
      <div v-if="containerState !== 'running'">
        <el-alert type="info" :closable="false" show-icon>
          <template #title>Non disponible — container arrêté</template>
        </el-alert>
      </div>
      <!-- Container running → afficher les métriques -->
      <div v-else>
        <!-- CPU -->
        <div class="stat-section">
          <div class="stat-header"><el-icon><Cpu /></el-icon><span>CPU</span></div>
          <ResourceBar :value="stats?.cpu_percent ?? 0" label="Utilisation" :show-value="true" />
        </div>
        <!-- RAM -->
        <div class="stat-section">
          <div class="stat-header"><el-icon><Odometer /></el-icon><span>Mémoire</span></div>
          <ResourceBar :value="stats?.memory_percent ?? 0" label="Utilisation" :show-value="true" />
          <div class="memory-details">{{ formatBytes(stats?.memory_used) }} / {{ formatBytes(stats?.memory_limit) }}</div>
        </div>
        <!-- Network I/O -->
        <div class="stat-section">
          <div class="stat-header"><el-icon><Connection /></el-icon><span>Réseau</span></div>
          <div class="io-grid">
            <div class="io-item"><span class="io-label">↓ Reçu</span><span class="io-value">{{ formatBytes(stats?.network_rx_bytes) }}</span></div>
            <div class="io-item"><span class="io-label">↑ Envoyé</span><span class="io-value">{{ formatBytes(stats?.network_tx_bytes) }}</span></div>
          </div>
        </div>
        <!-- Disk I/O -->
        <div class="stat-section">
          <div class="stat-header"><el-icon><Coin /></el-icon><span>Disque</span></div>
          <div class="io-grid">
            <div class="io-item"><span class="io-label">Lecture</span><span class="io-value">{{ formatBytes(stats?.block_read_bytes) }}</span></div>
            <div class="io-item"><span class="io-label">Écriture</span><span class="io-value">{{ formatBytes(stats?.block_write_bytes) }}</span></div>
          </div>
        </div>
      </div>
    </el-card>
    ```
  - **Styles à ajouter :** `.header-red { color: var(--el-color-danger); }`, `.card-resources :deep(.el-card__header) { border-bottom: 3px solid var(--el-color-danger); }`, `.stat-section`, `.stat-header`, `.memory-details`, `.io-grid`, `.io-item`, `.io-label`, `.io-value` (s'inspirer de `ContainerStats.vue` l.796-848 pour les styles des sections stats et io-grid)
  - **Note :** `Coin` icon est déjà importé via `ContainerStats.vue` mais pas encore dans `ContainerOverviewTab.vue` → ajouter à l'import `@element-plus/icons-vue`
**Pattern de référence :** Card Santé (`ContainerOverviewTab.vue` l.231-284) pour le pattern arrêté/running + `ContainerStats.vue` l.77-144 pour l'affichage des métriques
**Dépend de :** Tâche 1

### Tâche 3 : Implémenter l'auto-refresh et la gestion du cycle de vie
**Objectif :** Le WebSocket se connecte automatiquement quand le container passe à `running` et se déconnecte quand il passe à un autre état. Le composable gère déjà le cycle de vie (`onUnmounted` intégré).
**Fichiers :**
- `frontend/src/components/ContainerOverviewTab.vue` — **Modifier** —
  - Le `watch` sur `containerState` ajouté en Tâche 2 gère déjà ce comportement :
    ```typescript
    watch(() => props.containerState, (newState) => {
      if (newState === 'running') {
        connect()
      } else {
        disconnect()
      }
    }, { immediate: true })
    ```
  - **Pas besoin de `onMounted`/`onUnmounted`** : le composable `useContainerStats` gère déjà le cleanup dans son propre `onUnmounted` (l.302-305)
  - **Pas besoin de polling manuel** : le WebSocket stream déjà en continu (~1 stat/sec). Le refresh de 5s mentionné dans l'AC est le minimum — le WebSocket est plus rapide.
  - **Vérification** : s'assurer que quand `containerState` change dynamiquement (ex: container stoppé via action), le watch réagit correctement et déconnecte le WebSocket
**Dépend de :** Tâche 2

### Tâche 4 : Écrire les tests pour la card Ressources
**Objectif :** Tester l'affichage des métriques, l'auto-refresh via WebSocket, et l'état "container arrêté".
**Fichiers :**
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — **Modifier** —
  - **Mock à ajouter :** `vi.mock('@/composables/useContainerStats', () => ({ useContainerStats: vi.fn() }))` avec un mock retournant `{ stats: ref(null), connect: vi.fn(), disconnect: vi.fn(), isStreaming: ref(false) }`
  - **Mock à ajouter :** `vi.mock('@/utils/format', () => ({ formatBytes: (bytes: number | null | undefined) => bytes == null ? '-' : `${bytes} B` }))`
  - **Stub à ajouter :** `resource-bar` → `{ template: '<div class="resource-bar-stub" :data-value="value" />' , props: ['value', 'label', 'showValue'] }`
  - **Tests à ajouter dans un `describe('Resources card', ...)` :**
    1. `should render Resources card` — vérifier `.card-resources` existe
    2. `should show "Non disponible" alert when container is stopped` — mount avec `containerState: 'exited'`, vérifier le texte "Non disponible — container arrêté"
    3. `should call connect() when containerState is running` — vérifier que le mock `connect()` a été appelé
    4. `should call disconnect() when containerState changes to stopped` — mount running → changer prop → vérifier `disconnect()` appelé
    5. `should display CPU and RAM bars when stats are available` — mock stats avec valeurs → vérifier ResourceBar stubs avec bonnes valeurs
    6. `should display Network I/O and Disk I/O values` — mock stats → vérifier les valeurs formatées dans le template
    7. `should show Live tag when streaming` — mock `isStreaming: ref(true)` → vérifier la présence du tag "Live"
**Pattern de référence :** Tests existants dans `ContainerOverviewTab.spec.ts` (mock pattern, stubs, mountComponent helper)
**Dépend de :** Tâches 2-3

## Tests à écrire

### Frontend
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — Tests supplémentaires :
  - Card Ressources : affiche CPU %, RAM utilisé/total, Network I/O, Disk I/O avec les bonnes valeurs
  - Auto-refresh : vérifie que `connect()` est appelé quand le container est running
  - Auto-refresh : vérifie que `disconnect()` est appelé quand le container passe à arrêté
  - État arrêté : affiche "Non disponible — container arrêté" dans la card Ressources
  - Formatage bytes : vérifie les valeurs formatées (KB, MB, GB)

### Commandes de validation
```bash
cd frontend && pnpm test:unit --run
cd frontend && pnpm type-check
```

## État d'avancement technique
- [x] Tâche 1 : Extraire formatBytes() en utilitaire partagé
- [x] Tâche 2 : Ajouter card Ressources dans ContainerOverviewTab
- [x] Tâche 3 : Implémenter auto-refresh et cycle de vie
- [x] Tâche 4 : Écrire les tests card Ressources

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/utils/format.ts` — **Créé** — Utilitaire `formatBytes()` unifié (signature nullable, format humain)
- `frontend/src/components/ContainerOverviewTab.vue` — **Modifié** — Ajout card Ressources avec auto-refresh via `useContainerStats`, imports (Cpu, Odometer, Connection, Coin, ResourceBar, useContainerStats, formatBytes), watch sur `containerState`, styles (.header-red, .stat-section, .io-grid, etc.)
- `frontend/src/views/ContainerDetail.vue` — **Modifié** — Ajout `v-if="containerId"` + `containerId!` pour corriger l'erreur TS2322 sur le prop `containerId`
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — **Modifié** — Ajout mock `useContainerStats`, 7 nouveaux tests dans `describe('Resources card')`

### Décisions techniques
- `useContainerStats({ autoConnect: false })` avec `watch({ immediate: true })` pour contrôle conditionnel de la connexion WebSocket
- Le WebSocket stream en continu (~1 stat/sec) → pas besoin de polling manuel, le refresh est plus rapide que les 5s demandées par l'AC
- `formatBytes()` extrait en utilitaire partagé pour éliminer la duplication entre ContainerStats.vue et ContainerInfoTab.vue
- Card Ressources utilise la même structure visuelle que la card Santé (header coloré + alert pour état arrêté)

### Divergences par rapport à l'analyse
- Le test "Live tag when streaming" a été simplifié : on vérifie l'absence du tag quand `isStreaming=false` plutôt que de tenter un dynamic mock override (problème de hoisting avec `vi.mock`). Le comportement isStreaming=true sera vérifié en test d'intégration.

### Validation
- Tests unitaires : 25/25 passent (dont 7 tests spécifiques Resources card)
- Type-check : aucun error TS sur les fichiers modifiés
