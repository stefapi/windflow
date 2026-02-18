# Background Processes

[← Volume Browser](12-VOLUME-BROWSER.md) | [Suivant : Deployment →](14-DEPLOYMENT.md)

## 🔄 Vue d'ensemble

Système de sous-processus séparés pour la collecte de métriques système et d'événements Docker en arrière-plan, sans bloquer le thread HTTP principal. Utilise **spawn** avec IPC pour communication bidirectionnelle, crash recovery automatique avec backoff exponentiel, et gestion graceful shutdown.

## 1. Architecture Subprocess Manager

### 1.1 Gestionnaire Principal

Le `SubprocessManager` orchestre deux sous-processus principaux:

```typescript
// src/lib/server/subprocess-manager.ts
class SubprocessManager {
  private metricsState: SubprocessState = {
    process: null,
    restartCount: 0,
    lastRestartTime: 0,
    isShuttingDown: false
  };

  private eventsState: SubprocessState = {
    process: null,
    restartCount: 0,
    lastRestartTime: 0,
    isShuttingDown: false
  };

  private readonly metricsConfig: SubprocessConfig = {
    name: 'metrics-subprocess',
    scriptPath: getSubprocessPath('metrics-subprocess'),
    restartDelayMs: 5000,
    maxRestarts: 10
  };

  private readonly eventsConfig: SubprocessConfig = {
    name: 'event-subprocess',
    scriptPath: getSubprocessPath('event-subprocess'),
    restartDelayMs: 5000,
    maxRestarts: 10
  };
}
```

### 1.2 Paths des Scripts

Détection automatique développement vs production:

```typescript
function getSubprocessPath(name: string): string {
  // Production: /app/subprocesses/*.js (bundled)
  const prodPath = `/app/subprocesses/${name}.js`;
  if (existsSync(prodPath)) {
    return prodPath;
  }
  
  // Développement: src/lib/server/subprocesses/*.ts (raw)
  return path.join(__dirname, 'subprocesses', `${name}.ts`);
}
```

### 1.3 Lancement Subprocess

```typescript
private async startMetricsSubprocess(): Promise<void> {
  if (this.metricsState.isShuttingDown) return;

  try {
    const proc = Poetry.spawn(['Poetry', 'run', this.metricsConfig.scriptPath], {
      stdio: ['inherit', 'inherit', 'inherit'],
      env: { ...process.env, SKIP_MIGRATIONS: '1' },
      
      // Handler IPC pour messages subprocess → main
      ipc: (message) => this.handleMetricsMessage(message as SubprocessMessage),
      
      // Handler exit pour crash recovery
      onExit: (proc, exitCode, signalCode) => {
        this.handleMetricsExit(exitCode, signalCode);
      }
    });

    this.metricsState.process = proc;
    this.metricsState.restartCount = 0;

    console.log(`Started ${this.metricsConfig.name} (PID: ${proc.pid})`);
  } catch (error) {
    console.error(`Failed to start ${this.metricsConfig.name}:`, error);
    this.scheduleMetricsRestart();
  }
}
```

## 2. Protocole IPC

### 2.1 Messages Subprocess → Main

```typescript
// Types de messages envoyés par les sous-processus
export type SubprocessMessage =
  | MetricMessage        // Métrique CPU/mémoire
  | DiskWarningMessage   // Alerte espace disque
  | ContainerEventMessage // Événement conteneur
  | EnvStatusMessage     // Statut environnement (online/offline)
  | ReadyMessage         // Subprocess prêt
  | ErrorMessage;        // Erreur subprocess

interface MetricMessage {
  type: 'metric';
  envId: number;
  cpu: number;
  memPercent: number;
  memUsed: number;
  memTotal: number;
}

interface ContainerEventMessage {
  type: 'container_event';
  event: {
    environmentId: number;
    containerId: string;
    containerName: string | null;
    image: string | null;
    action: ContainerEventAction;
    actorAttributes: Record<string, string> | null;
    timestamp: string;
  };
  notification?: {
    action: ContainerEventAction;
    title: string;
    message: string;
    notificationType: 'success' | 'error' | 'warning' | 'info';
    image?: string;
  };
}
```

### 2.2 Messages Main → Subprocess

```typescript
// Commandes envoyées aux sous-processus
export type MainProcessCommand =
  | RefreshEnvironmentsCommand  // Recharger liste environnements
  | ShutdownCommand             // Arrêt graceful
  | UpdateIntervalCommand;      // Changer intervalle collecte

interface RefreshEnvironmentsCommand {
  type: 'refresh_environments';
}

interface UpdateIntervalCommand {
  type: 'update_interval';
  intervalMs: number;
}
```

### 2.3 Envoi Messages

```typescript
// Subprocess → Main (via process.send)
function send(message: SubprocessMessage): void {
  if (process.send) {
    process.send(message);
  }
}

// Main → Subprocess (via poetry.spawn IPC)
private sendToMetrics(command: MainProcessCommand): void {
  if (this.metricsState.process) {
    try {
      this.metricsState.process.send(command);
    } catch (error) {
      console.error('Failed to send to metrics subprocess:', error);
    }
  }
}
```

## 3. Metrics Subprocess

### 3.1 Collecte Métriques par Environnement

```typescript
// src/lib/server/subprocesses/metrics-subprocess.ts
const COLLECT_INTERVAL = 30000; // 30s (configurable via DB)
const ENV_METRICS_TIMEOUT = 15000; // 15s timeout par environnement

async function collectEnvMetrics(env: Environment) {
  // Skip si désactivé ou Hawser Edge
  if (!env.collectMetrics || env.connectionType === 'hawser-edge') {
    return;
  }

  // Récupérer conteneurs running
  const containers = await listContainers(false, env.id);
  
  let totalCpuPercent = 0;
  let totalContainerMemUsed = 0;

  // Stats pour chaque conteneur
  const statsPromises = containers.map(async (container) => {
    const stats = await getContainerStats(container.id, env.id);
    
    // CPU: delta usage / delta system * nb cores * 100
    const cpuDelta = stats.cpu_stats.cpu_usage.total_usage - 
                     stats.precpu_stats.cpu_usage.total_usage;
    const systemDelta = stats.cpu_stats.system_cpu_usage - 
                        stats.precpu_stats.system_cpu_usage;
    const cpuCount = stats.cpu_stats.online_cpus || os.cpus().length;
    
    const cpuPercent = systemDelta > 0 && cpuDelta > 0
      ? (cpuDelta / systemDelta) * cpuCount * 100
      : 0;

    // Mémoire: usage - cache (inactive_file)
    const memUsage = stats.memory_stats?.usage || 0;
    const memStats = stats.memory_stats?.stats || {};
    const memCache = memStats.inactive_file ?? memStats.total_inactive_file ?? 0;
    const actualMemUsed = memCache > 0 && memCache < memUsage 
      ? memUsage - memCache 
      : memUsage;

    return { cpuPercent, memUsage: actualMemUsed };
  });

  const statsResults = await Promise.all(statsPromises);
  totalCpuPercent = statsResults.reduce((sum, r) => sum + r.cpuPercent, 0);
  totalContainerMemUsed = statsResults.reduce((sum, r) => sum + r.memUsage, 0);

  // Host info via Docker
  const info = await getDockerInfo(env.id);
  const memTotal = info?.MemTotal || os.totalmem();
  const cpuCount = info?.NCPU || os.cpus().length;

  // Normaliser CPU par nb cores
  const normalizedCpu = totalCpuPercent / cpuCount;
  const memPercent = memTotal > 0 ? (totalContainerMemUsed / memTotal) * 100 : 0;

  // Valider et envoyer
  if (Number.isFinite(normalizedCpu) && Number.isFinite(memPercent)) {
    send({
      type: 'metric',
      envId: env.id,
      cpu: normalizedCpu,
      memPercent: memPercent,
      memUsed: totalContainerMemUsed,
      memTotal: memTotal
    });
  }
}
```

### 3.2 Collecte Parallèle avec Timeout

```typescript
async function collectMetrics() {
  const environments = await getEnvironments();
  const enabledEnvs = environments.filter(e => e.collectMetrics !== false);

  // Traiter tous en parallèle avec timeout par environnement
  const results = await Promise.allSettled(
    enabledEnvs.map(env =>
      withTimeout(
        collectEnvMetrics(env).then(() => env.name),
        ENV_METRICS_TIMEOUT,
        null
      )
    )
  );

  // Logger timeouts
  results.forEach((result, index) => {
    if (result.status === 'fulfilled' && result.value === null) {
      console.warn(`Environment "${enabledEnvs[index].name}" timed out`);
    }
  });
}

// Helper timeout avec cleanup proper
function withTimeout<T>(
  promise: Promise<T>, 
  ms: number, 
  fallback: T
): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const timeoutPromise = new Promise<T>(resolve => {
    timeoutId = setTimeout(() => resolve(fallback), ms);
  });

  return Promise.race([promise, timeoutPromise]).finally(() => {
    if (timeoutId !== null) {
      clearTimeout(timeoutId); // Éviter memory leak
    }
  });
}
```

### 3.3 Vérification Espace Disque

```typescript
const DISK_CHECK_INTERVAL = 300000; // 5 minutes
const DISK_WARNING_COOLDOWN = 3600000; // 1h entre alertes
const lastDiskWarning: Map<number, number> = new Map();

async function checkEnvDiskSpace(env: Environment) {
  // Cooldown check
  const lastWarning = lastDiskWarning.get(env.id);
  if (lastWarning && Date.now() - lastWarning < DISK_WARNING_COOLDOWN) {
    return; // Skip, encore en cooldown
  }

  // Récupérer usage Docker
  const diskData = await getDiskUsage(env.id);
  
  let totalUsed = 0;
  if (diskData.Images) {
    totalUsed += diskData.Images.reduce((sum, img) => sum + (img.Size || 0), 0);
  }
  if (diskData.Containers) {
    totalUsed += diskData.Containers.reduce((sum, c) => sum + (c.SizeRw || 0), 0);
  }
  if (diskData.Volumes) {
    totalUsed += diskData.Volumes.reduce((sum, v) => sum + (v.UsageData?.Size || 0), 0);
  }
  if (diskData.BuildCache) {
    totalUsed += diskData.BuildCache.reduce((sum, bc) => sum + (bc.Size || 0), 0);
  }

  // Calculer pourcentage
  const info = await getDockerInfo(env.id);
  const driverStatus = info?.DriverStatus;
  
  let dataSpaceTotal = 0;
  if (driverStatus) {
    for (const [key, value] of driverStatus) {
      if (key === 'Data Space Total' && typeof value === 'string') {
        dataSpaceTotal = parseSize(value); // "107.4GB" → bytes
        break;
      }
    }
  }

  if (dataSpaceTotal > 0) {
    const diskPercent = (totalUsed / dataSpaceTotal) * 100;
    
    if (diskPercent > DEFAULT_DISK_THRESHOLD) {
      send({
        type: 'disk_warning',
        envId: env.id,
        envName: env.name,
        message: `Docker disk usage: ${diskPercent.toFixed(1)}% (${formatSize(totalUsed)} / ${formatSize(dataSpaceTotal)})`,
        diskPercent
      });
      
      lastDiskWarning.set(env.id, Date.now());
    }
  }
}
```

### 3.4 Diagnostics Mémoire

```typescript
const MEMORY_LOG_INTERVAL = 10; // Toutes les 10 cycles
let collectionCycleCount = 0;

async function collectMetrics() {
  // ... collecte ...

  // Logger mémoire périodiquement
  collectionCycleCount++;
  if (collectionCycleCount % MEMORY_LOG_INTERVAL === 0) {
    const memUsage = process.memoryUsage();
    const heapMB = Math.round(memUsage.heapUsed / 1024 / 1024);
    const rssMB = Math.round(memUsage.rss / 1024 / 1024);
    console.log(`Memory: heap=${heapMB}MB, rss=${rssMB}MB (cycle ${collectionCycleCount})`);
  }
}
```

## 4. Events Subprocess

### 4.1 Deux Modes de Collecte

```typescript
// src/lib/server/subprocesses/event-subprocess.ts
let currentMode: 'stream' | 'poll' = 'stream';
let currentPollInterval: number = 60000;

// Mode Streaming: connexion persistante temps réel
const collectors: Map<number, {
  controller: AbortController;
  reconnectTimeout: ReturnType<typeof setTimeout> | null;
}> = new Map();

// Mode Polling: vérification intervalle régulier
const pollIntervals: Map<number, ReturnType<typeof setInterval>> = new Map();
const lastPollTime: Map<number, number> = new Map();
```

### 4.2 Mode Streaming (Temps Réel)

```typescript
async function startEnvironmentCollector(envId: number, envName: string) {
  const controller = new AbortController();
  collectors.set(envId, { controller, reconnectTimeout: null });

  let reconnectDelay = RECONNECT_DELAY; // 5s initial

  const connect = async () => {
    if (controller.signal.aborted || isShuttingDown) return;

    let reader: ReadableStreamDefaultReader | null = null;

    try {
      console.log(`Connecting to Docker events for ${envName}...`);

      const eventStream = await getDockerEvents({ type: ['container'] }, envId);
      if (!eventStream) {
        updateEnvironmentStatus(envId, envName, false, 'Failed to connect');
        scheduleReconnect();
        return;
      }

      // Reset délai sur succès
      reconnectDelay = RECONNECT_DELAY;
      updateEnvironmentStatus(envId, envName, true);

      reader = eventStream.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // Stream infini d'événements
      while (!controller.signal.aborted && !isShuttingDown) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim()) {
            try {
              const event = JSON.parse(line) as DockerEvent;
              processEvent(event, envId);
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error(`Stream error for ${envName}:`, error.message);
        updateEnvironmentStatus(envId, envName, false, error.message);
      }
    } finally {
      if (reader) {
        await reader.cancel();
        reader.releaseLock();
      }
    }

    // Reconnexion après déconnexion
    if (!controller.signal.aborted && !isShuttingDown) {
      scheduleReconnect();
    }
  };

  const scheduleReconnect = () => {
    console.log(`Reconnecting to ${envName} in ${reconnectDelay / 1000}s...`);
    
    setTimeout(() => {
      if (!controller.signal.aborted && !isShuttingDown) {
        connect();
      }
    }, reconnectDelay);

    // Backoff exponentiel (5s → 10s → 20s → 40s → 60s max)
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
  };

  connect();
}
```

### 4.3 Mode Polling (Intervalles)

```typescript
async function pollEnvironmentEvents(envId: number, envName: string) {
  const now = Math.floor(Date.now() / 1000); // Unix timestamp
  const since = lastPollTime.get(envId) || (now - 30); // 30s par défaut

  // Fetch événements entre 'since' et 'until'
  // IMPORTANT: 'until' requis pour polling, sinon stream reste ouvert
  const eventStream = await getDockerEvents(
    { type: ['container'] },
    envId,
    { since: since.toString(), until: now.toString() }
  );

  if (!eventStream) {
    updateEnvironmentStatus(envId, envName, false, 'Failed to fetch events');
    return;
  }

  updateEnvironmentStatus(envId, envName, true);

  // Lire tous événements
  const reader = eventStream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim()) {
          try {
            const event = JSON.parse(line) as DockerEvent;
            processEvent(event, envId);
          } catch {
            // Ignore
          }
        }
      }
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }

  lastPollTime.set(envId, now);
}

async function startEnvironmentPoller(envId: number, envName: string, interval: number) {
  console.log(`Starting poller for ${envName} (every ${interval / 1000}s)`);

  // Poll immédiat
  await pollEnvironmentEvents(envId, envName);

  // Puis intervalle régulier
  const intervalId = setInterval(async () => {
    if (!isShuttingDown) {
      await pollEnvironmentEvents(envId, envName);
    }
  }, interval);

  pollIntervals.set(envId, intervalId);
}
```

### 4.4 Déduplication Événements

```typescript
// Cache LRU avec fenêtre temporelle
const recentEvents: Map<string, number> = new Map();
const DEDUP_WINDOW_MS = 5000; // 5s
const MAX_DEDUP_CACHE_SIZE = 500;

function processEvent(event: DockerEvent, envId: number) {
  if (event.Type !== 'container') return;

  const containerId = event.Actor?.ID;
  const action = event.Action;

  // Clé unique: envId-timeNano-containerId-action
  const dedupKey = `${envId}-${event.timeNano}-${containerId}-${action}`;
  
  if (recentEvents.has(dedupKey)) {
    return; // Déjà traité
  }

  recentEvents.set(dedupKey, Date.now());

  // Cleanup si cache trop gros
  if (recentEvents.size > 200) {
    cleanupRecentEvents();
  }

  // ... traiter événement ...
}

function cleanupRecentEvents() {
  const now = Date.now();
  
  // Supprimer événements expirés
  for (const [key, timestamp] of recentEvents.entries()) {
    if (now - timestamp > DEDUP_WINDOW_MS) {
      recentEvents.delete(key);
    }
  }

  // LRU eviction si encore trop gros
  if (recentEvents.size > MAX_DEDUP_CACHE_SIZE) {
    const entries = Array.from(recentEvents.entries())
      .sort((a, b) => a[1] - b[1]); // Plus vieux d'abord
    
    const toRemove = entries.slice(0, entries.length - MAX_DEDUP_CACHE_SIZE);
    for (const [key] of toRemove) {
      recentEvents.delete(key);
    }
  }
}

// Cleanup périodique (toutes les 5s)
setInterval(cleanupRecentEvents, 5000);
```

### 4.5 Filtrage Événements

```typescript
// Actions importantes seulement
const CONTAINER_ACTIONS: ContainerEventAction[] = [
  'create', 'start', 'stop', 'die', 'kill', 'restart',
  'pause', 'unpause', 'destroy', 'rename', 'update',
  'oom', 'health_status'
];

// Exclure scanners
const SCANNER_IMAGE_PATTERNS = [
  'anchore/grype',
  'aquasec/trivy',
  'ghcr.io/anchore/grype',
  'ghcr.io/aquasecurity/trivy'
];

// Exclure conteneurs internes Windflow-sample
const EXCLUDED_CONTAINER_PREFIXES = ['Windflow-sample-browse-'];

function processEvent(event: DockerEvent, envId: number) {
  const image = event.Actor?.Attributes?.image;
  const containerName = event.Actor?.Attributes?.name;

  // Skip scanners
  if (isScannerContainer(image)) return;

  // Skip conteneurs internes
  if (isExcludedContainer(containerName)) return;

  // Skip actions non importantes
  const baseAction = event.Action.split(':')[0];
  if (!CONTAINER_ACTIONS.includes(baseAction)) return;

  // ... traiter ...
}
```

### 4.6 Notifications Statut Environnement

```typescript
// Suivre statut online pour notifications changement uniquement
const environmentOnlineStatus: Map<number, boolean> = new Map();

function updateEnvironmentStatus(
  envId: number,
  envName: string,
  isOnline: boolean,
  errorMessage?: string
) {
  const previousStatus = environmentOnlineStatus.get(envId);

  // Notifier SEULEMENT sur changement d'état
  if (previousStatus !== undefined && previousStatus !== isOnline) {
    send({
      type: 'env_status',
      envId,
      envName,
      online: isOnline,
      error: errorMessage
    });
  }

  environmentOnlineStatus.set(envId, isOnline);
}
```

## 5. Crash Recovery

### 5.1 Backoff Exponentiel

```typescript
private scheduleMetricsRestart(): void {
  if (this.metricsState.isShuttingDown) return;

  if (this.metricsState.restartCount >= this.metricsConfig.maxRestarts) {
    console.error(
      `${this.metricsConfig.name} exceeded max restarts (${this.metricsConfig.maxRestarts}), giving up`
    );
    return;
  }

  // Délai exponentiel: 5s → 10s → 20s → 40s → 80s → ...
  const delay = this.metricsConfig.restartDelayMs * Math.pow(2, this.metricsState.restartCount);
  this.metricsState.restartCount++;

  console.log(
    `Restarting ${this.metricsConfig.name} in ${delay}ms ` +
    `(attempt ${this.metricsState.restartCount}/${this.metricsConfig.maxRestarts})`
  );

  setTimeout(() => {
    this.startMetricsSubprocess();
  }, delay);
}
```

### 5.2 Exit Handler

```typescript
private handleMetricsExit(exitCode: number | null, signalCode: string | null): void {
  if (this.metricsState.isShuttingDown) {
    console.log(`${this.metricsConfig.name} stopped gracefully`);
    return;
  }

  console.error(
    `${this.metricsConfig.name} exited unexpectedly ` +
    `(code: ${exitCode}, signal: ${signalCode})`
  );

  this.metricsState.process = null;
  this.scheduleMetricsRestart();
}
```

## 6. Graceful Shutdown

### 6.1 Shutdown Main Process

```typescript
async stop(): Promise<void> {
  console.log('[SubprocessManager] Stopping subprocesses...');

  this.metricsState.isShuttingDown = true;
  this.eventsState.isShuttingDown = true;

  // Envoyer commande shutdown
  this.sendToMetrics({ type: 'shutdown' });
  this.sendToEvents({ type: 'shutdown' });

  // Attendre shutdown graceful (1s)
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Force kill si toujours actif
  if (this.metricsState.process) {
    this.metricsState.process.kill();
    this.metricsState.process = null;
  }
  if (this.eventsState.process) {
    this.eventsState.process.kill();
    this.eventsState.process = null;
  }

  console.log('[SubprocessManager] All subprocesses stopped');
}
```

### 6.2 Shutdown Subprocess

```typescript
// event-subprocess.ts
function shutdown(): void {
  isShuttingDown = true;

  // Stopper cleanup interval
  if (cacheCleanupInterval) {
    clearInterval(cacheCleanupInterval);
  }

  // Stopper tous collectors streaming
  for (const envId of collectors.keys()) {
    stopEnvironmentCollector(envId);
  }

  // Stopper tous pollers
  for (const envId of pollIntervals.keys()) {
    stopEnvironmentPoller(envId);
  }

  // Clear cache déduplication
  recentEvents.clear();

  console.log('[EventSubprocess] Stopped');
  process.exit(0);
}

// Listeners shutdown
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

// Listener commandes main
process.on('message', (command: MainProcessCommand) => {
  if (command.type === 'shutdown') {
    shutdown();
  }
});
```

## 7. HMR Cleanup (Dev Mode)

### 7.1 Tracking PIDs Global

```typescript
// Persister PIDs entre HMR reloads
const GLOBAL_KEY = '__windflow_subprocess_pids__';

interface SubprocessPids {
  metrics: number | null;
  events: number | null;
}

function getStoredPids(): SubprocessPids {
  return (globalThis as any)[GLOBAL_KEY] || { metrics: null, events: null };
}

function setStoredPids(pids: SubprocessPids): void {
  (globalThis as any)[GLOBAL_KEY] = pids;
}
```

### 7.2 Kill Orphelins au Démarrage

```typescript
function killOrphanedProcesses(): void {
  const pids = getStoredPids();

  if (pids.metrics) {
    try {
      process.kill(pids.metrics, 'SIGTERM');
      console.log(`Killed orphaned metrics process (PID: ${pids.metrics})`);
    } catch {
      // Process déjà mort
    }
  }

  if (pids.events) {
    try {
      process.kill(pids.events, 'SIGTERM');
      console.log(`Killed orphaned events process (PID: ${pids.events})`);
    } catch {
      // Process déjà mort
    }
  }

  setStoredPids({ metrics: null, events: null });
}

export async function startSubprocesses(): Promise<void> {
  // Tuer orphelins avant démarrer nouveaux
  killOrphanedProcesses();

  manager = new SubprocessManager();
  await manager.start();

  // Stocker nouveaux PIDs
  setStoredPids({
    metrics: manager.getMetricsPid(),
    events: manager.getEventsPid()
  });
}
```

## 8. Gestion Handlers IPC

### 8.1 Handler Messages Metrics

```typescript
private async handleMetricsMessage(message: SubprocessMessage): Promise<void> {
  try {
    switch (message.type) {
      case 'ready':
        console.log(`${this.metricsConfig.name} is ready`);
        break;

      case 'metric':
        // Sauvegarder en DB
        await saveHostMetric(
          message.cpu,
          message.memPercent,
          message.memUsed,
          message.memTotal,
          message.envId
        );
        break;

      case 'disk_warning':
        // Envoyer notification
        await sendEventNotification(
          'disk_space_warning',
          {
            title: message.diskPercent ? 'Disk space warning' : 'High Docker disk usage',
            message: message.message,
            type: 'warning'
          },
          message.envId
        );
        break;

      case 'error':
        console.error(`${this.metricsConfig.name} error:`, message.message);
        break;
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error(`Error handling metrics message: ${msg}`);
  }
}
```

### 8.2 Handler Messages Events

```typescript
private async handleEventsMessage(message: SubprocessMessage): Promise<void> {
  try {
    switch (message.type) {
      case 'ready':
        console.log(`${this.eventsConfig.name} is ready`);
        break;

      case 'container_event':
        // Sauvegarder en DB
        const savedEvent = await logContainerEvent(message.event);

        // Broadcast SSE
        containerEventEmitter.emit('event', savedEvent);

        // Envoyer notification si fournie
        if (message.notification) {
          const { action, title, message: notifMsg, notificationType, image } = message.notification;
          sendEnvironmentNotification(
            message.event.environmentId,
            action,
            { title, message: notifMsg, type: notificationType },
            image
          ).catch(err => {
            console.error('Failed to send notification:', err);
          });
        }
        break;

      case 'env_status':
        // Broadcast statut environnement
        containerEventEmitter.emit('env_status', {
          envId: message.envId,
          envName: message.envName,
          online: message.online,
          error: message.error
        });

        // Notification changement statut
        if (message.online) {
          await sendEventNotification(
            'environment_online',
            {
              title: 'Environment online',
              message: `Environment "${message.envName}" is now reachable`,
              type: 'success'
            },
            message.envId
          );
        } else {
          await sendEventNotification(
            'environment_offline',
            {
              title: 'Environment offline',
              message: `Environment "${message.envName}" is unreachable${message.error ? `: ${message.error}` : ''}`,
              type: 'error'
            },
            message.envId
          );
        }
        break;

      case 'error':
        console.error(`${this.eventsConfig.name} error:`, message.message);
        break;
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error(`Error handling events message: ${msg}`);
  }
}
```

## 9. API Publique

### 9.1 Démarrage

```typescript
// Appelé depuis hooks.server.ts au démarrage app
export async function startSubprocesses(): Promise<void> {
  killOrphanedProcesses();

  if (manager) {
    console.warn('Subprocesses already started');
    return;
  }

  manager = new SubprocessManager();
  await manager.start();

  setStoredPids({
    metrics: manager.getMetricsPid(),
    events: manager.getEventsPid()
  });
}
```

### 9.2 Arrêt

```typescript
export async function stopSubprocesses(): Promise<void> {
  if (manager) {
    await manager.stop();
    manager = null;
  }
  setStoredPids({ metrics: null, events: null });
}
```

### 9.3 Refresh Environnements

```typescript
// Appelé quand environnements sont créés/modifiés/supprimés
export function refreshSubprocessEnvironments(): void {
  if (manager) {
    manager.refreshEnvironments();
  }
}
```

### 9.4 Envoyer Commandes

```typescript
export function sendToMetricsSubprocess(message: MainProcessCommand): void {
  if (manager) {
    manager.sendToMetricsSubprocess(message);
  }
}

export function sendToEventSubprocess(message: MainProcessCommand): void {
  if (manager) {
    manager.sendToEventsSubprocess(message);
  }
}
```

## 10. Configuration Dynamique

### 10.1 Intervalle Collecte Métriques

Configurable via DB (10s à 5min):

```typescript
// Défaut: 30s
const metricsInterval = await getMetricsCollectionInterval();

// Changer intervalle
await setMetricsCollectionInterval(60000); // 60s

// Notifier subprocess
sendToMetricsSubprocess({ type: 'update_interval', intervalMs: 60000 });
```

### 10.2 Mode Collecte Événements

Switch entre streaming et polling:

```typescript
// Mode actuel
const mode = await getEventCollectionMode(); // 'stream' | 'poll'

// Changer mode
await setEventCollectionMode('poll');

// Notifier subprocess (il recharge depuis DB)
sendToEventSubprocess({ type: 'refresh_environments' });
```

### 10.3 Intervalle Poll Événements

```typescript
// Défaut: 60s
const pollInterval = await getEventPollInterval();

// Changer intervalle
await setEventPollInterval(30000); // 30s

// Notifier subprocess
sendToEventSubprocess({ type: 'refresh_environments' });
```

---

**Résumé Architecture:**
- **2 subprocesses** séparés (metrics, events) via poetry.spawn
- **IPC bidirectionnel** pour communication main ↔ subprocess
- **Crash recovery** automatique avec backoff exponentiel (max 10 tentatives)
- **Graceful shutdown** avec force kill après timeout
- **HMR cleanup** pour dev mode (kill orphelins)
- **Metrics**: Collecte CPU/mémoire/disque toutes les 30s (configurable)
- **Events**: 2 modes (streaming temps réel ou polling intervalle)
- **Déduplication** événements avec cache LRU
- **Filtrage** scanners et conteneurs internes
- **Notifications** changements statut environnement

[← Volume Browser](12-VOLUME-BROWSER.md) | [Suivant : Deployment →](14-DEPLOYMENT.md)
