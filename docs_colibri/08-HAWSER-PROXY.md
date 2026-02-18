# Hawser Proxy - Environnements distants

[← Vulnerability Scanning](07-VULNERABILITY-SCANNING.md) | [Suivant : Scheduler →](09-SCHEDULER.md)

## 🌐 Vue d'ensemble

Hawser est un système de proxy WebSocket bidirectionnel permettant de gérer des environnements Docker distants derrière NAT/Firewall. Les agents Hawser se connectent à Windflow-sample via WebSocket, éliminant le besoin d'ouvrir des ports ou d'exposer des API Docker.

## 🏗️ Architecture

```
┌─────────────────┐                    ┌──────────────────┐
│   Windflow-sample      │                    │  Hawser Agent    │
│                 │                    │                  │
│                 │                    │                  │
│  ┌───────────┐  │                    │  ┌────────────┐  │
│  │ hawser.ts │◄─┼──WebSocket (TLS)──┼─►│ WebSocket  │  │
│  └───────────┘  │                    │  │ Client     │  │
│       │         │                    │  └─────┬──────┘  │
│       │         │                    │        │         │
│  ┌────▼──────┐  │                    │  ┌─────▼──────┐  │
│  │ DB Tokens │  │                    │  │ Docker API │  │
│  └───────────┘  │                    │  └────────────┘  │
└─────────────────┘                    └──────────────────┘
```

**Flux de connexion Edge:**
1. Agent Hawser démarre avec un token
2. Connexion WebSocket à `wss://Windflow-sample/api/hawser/edge`
3. Envoi du message `hello` avec token, version, capabilities
4. Windflow-sample valide le token (Argon2id) et répond `welcome`
5. Connexion établie, heartbeat automatique toutes les 30s
6. Windflow-sample route les requêtes Docker via l'agent

## 1. Protocole WebSocket

### Messages de base

```typescript
// src/lib/server/hawser.ts
export const MessageType = {
    HELLO: 'hello',           // Agent → Windflow-sample (connexion)
    WELCOME: 'welcome',       // Windflow-sample → Agent (confirmation)
    REQUEST: 'request',       // Windflow-sample → Agent (requête Docker)
    RESPONSE: 'response',     // Agent → Windflow-sample (réponse)
    STREAM: 'stream',         // Agent → Windflow-sample (chunk streaming)
    STREAM_END: 'stream_end', // Bi-directionnel (fin stream)
    METRICS: 'metrics',       // Agent → Windflow-sample (métriques)
    PING: 'ping',             // Windflow-sample → Agent (heartbeat)
    PONG: 'pong',             // Agent → Windflow-sample (heartbeat)
    ERROR: 'error'            // Bi-directionnel (erreur)
} as const;

export const HAWSER_PROTOCOL_VERSION = '1.0';
```

### Message Hello (Agent → Windflow-sample)

```typescript
interface HelloMessage {
    type: 'hello';
    version: string;          // Version du protocole
    agentId: string;          // UUID unique de l'agent
    agentName: string;        // Nom de l'agent
    token: string;            // Token d'authentification
    dockerVersion: string;    // Version Docker
    hostname: string;         // Hostname du système
    capabilities: string[];   // ['exec', 'streaming', 'metrics']
}
```

### Message Request (Windflow-sample → Agent)

```typescript
interface RequestMessage {
    type: 'request';
    requestId: string;        // UUID pour corréler les réponses
    method: string;           // HTTP method (GET, POST, DELETE)
    path: string;             // Docker API path (/containers/json)
    headers?: Record<string, string>;
    body?: unknown;           // JSON-serializable object
    streaming?: boolean;      // true pour logs/exec streaming
}
```

### Message Response (Agent → Windflow-sample)

```typescript
interface ResponseMessage {
    type: 'response';
    requestId: string;        // UUID de la requête
    statusCode: number;       // HTTP status code
    headers?: Record<string, string>;
    body?: string;            // Response body (peut être base64)
    isBinary?: boolean;       // true si body est base64
}
```

### Message Stream (Agent → Windflow-sample)

```typescript
interface StreamMessage {
    type: 'stream';
    requestId: string;
    data: string;             // Base64-encoded chunk
    stream?: 'stdout' | 'stderr';
}

interface StreamEndMessage {
    type: 'stream_end';
    requestId: string;
    reason?: string;          // Raison de fin
}
```

## 2. Gestion des tokens

### Structure de la table

```sql
-- drizzle/0000_initial_schema.sql
CREATE TABLE hawser_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,              -- Hash Argon2id
    token_prefix TEXT NOT NULL,       -- 8 premiers chars (identification)
    name TEXT NOT NULL,               -- Nom descriptif
    environment_id INTEGER,           -- NULL = token global
    is_active INTEGER DEFAULT 1,
    expires_at TEXT,                  -- ISO 8601 timestamp
    last_used TEXT,                   -- Dernière utilisation
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);
```

### Génération de token

```typescript
// src/lib/server/hawser.ts
export async function generateHawserToken(
    name: string,
    environmentId: number,
    expiresAt?: string,
    rawToken?: string
): Promise<{ token: string; tokenId: number }> {
    // Générer token sécurisé (32 bytes = 256 bits)
    const tokenBytes = new Uint8Array(32);
    secureGetRandomValues(tokenBytes);
    const token = Buffer.from(tokenBytes).toString('base64url');

    // Hash avec Argon2id
    const hashedToken = await hashPassword(token);

    // Préfixe pour identification (8 chars)
    const tokenPrefix = token.substring(0, 8);

    // Stocker en DB
    const result = await db
        .insert(hawserTokens)
        .values({
            token: hashedToken,
            tokenPrefix,
            name,
            environmentId,
            isActive: true,
            expiresAt
        })
        .returning({ id: hawserTokens.id });

    return { token, tokenId: result[0].id };
}
```

### Validation de token

```typescript
export async function validateHawserToken(
    token: string
): Promise<{ valid: boolean; environmentId?: number; tokenId?: number }> {
    // Récupérer tous les tokens actifs
    const tokens = await db
        .select()
        .from(hawserTokens)
        .where(eq(hawserTokens.isActive, true));

    // Vérifier avec Argon2id
    for (const t of tokens) {
        try {
            const isValid = await verifyPassword(token, t.token);
            if (isValid) {
                // Mettre à jour lastUsed
                await db
                    .update(hawserTokens)
                    .set({ lastUsed: new Date().toISOString() })
                    .where(eq(hawserTokens.id, t.id));

                return {
                    valid: true,
                    environmentId: t.environmentId ?? undefined,
                    tokenId: t.id
                };
            }
        } catch {
            // Hash invalide, continuer
        }
    }

    return { valid: false };
}
```

## 3. Gestion des connexions

### Structure EdgeConnection

```typescript
interface EdgeConnection {
    ws: WebSocket;
    environmentId: number;
    agentId: string;
    agentName: string;
    agentVersion: string;
    dockerVersion: string;
    hostname: string;
    capabilities: string[];
    connectedAt: Date;
    lastHeartbeat: Date;
    pendingRequests: Map<string, PendingRequest>;
    pendingStreamRequests: Map<string, PendingStreamRequest>;
    lastMetrics?: {
        uptime?: number;
        cpuUsage?: number;
        memoryTotal?: number;
        memoryUsed?: number;
    };
}

// Map globale des connexions actives
const edgeConnections: Map<number, EdgeConnection> = new Map();
```

### Connexion d'un agent

```typescript
export function handleEdgeConnection(
    ws: WebSocket,
    environmentId: number,
    hello: HelloMessage
): EdgeConnection {
    // Fermer connexion existante si présente
    const existing = edgeConnections.get(environmentId);
    if (existing) {
        console.log(`Replacing existing connection for env ${environmentId}`);
        
        // Rejeter toutes les requêtes en attente
        for (const [requestId, pending] of existing.pendingRequests) {
            pending.reject(new Error('Connection replaced'));
        }
        
        existing.ws.close(1000, 'Replaced by new connection');
    }

    const connection: EdgeConnection = {
        ws,
        environmentId,
        agentId: hello.agentId,
        agentName: hello.agentName,
        agentVersion: hello.version,
        dockerVersion: hello.dockerVersion,
        hostname: hello.hostname,
        capabilities: hello.capabilities,
        connectedAt: new Date(),
        lastHeartbeat: new Date(),
        pendingRequests: new Map(),
        pendingStreamRequests: new Map()
    };

    edgeConnections.set(environmentId, connection);

    // Mettre à jour la table environments
    updateEnvironmentStatus(environmentId, connection);

    return connection;
}
```

### Heartbeat et cleanup

```typescript
// Intervalle de cleanup : 30 secondes
// Timeout : 90 secondes (3 heartbeats manqués)
const CLEANUP_INTERVAL = 30000;
const CONNECTION_TIMEOUT = 90000;

export function initializeEdgeManager(): void {
    setInterval(() => {
        const now = Date.now();

        for (const [envId, conn] of edgeConnections) {
            if (now - conn.lastHeartbeat.getTime() > CONNECTION_TIMEOUT) {
                console.log(`Connection timeout for environment ${envId}`);

                // Rejeter toutes les requêtes en attente
                for (const [requestId, pending] of conn.pendingRequests) {
                    clearTimeout(pending.timeout);
                    pending.reject(new Error('Connection timeout'));
                }
                conn.pendingRequests.clear();

                // Terminer tous les streams en attente
                for (const [requestId, pending] of conn.pendingStreamRequests) {
                    pending.onEnd?.('Connection timeout');
                }
                conn.pendingStreamRequests.clear();

                conn.ws.close(1001, 'Connection timeout');
                edgeConnections.delete(envId);
            }
        }
    }, CLEANUP_INTERVAL);
}
```

## 4. Requêtes Docker

### Requête simple

```typescript
export async function sendEdgeRequest(
    environmentId: number,
    method: string,
    path: string,
    body?: unknown,
    headers?: Record<string, string>,
    streaming = false,
    timeout = 30000
): Promise<EdgeResponse> {
    const connection = edgeConnections.get(environmentId);
    if (!connection) {
        throw new Error('Edge agent not connected');
    }

    const requestId = secureRandomUUID();

    return new Promise((resolve, reject) => {
        const timeoutHandle = setTimeout(() => {
            connection.pendingRequests.delete(requestId);
            reject(new Error('Request timeout'));
        }, timeout);

        connection.pendingRequests.set(requestId, {
            resolve,
            reject,
            timeout: timeoutHandle
        });

        const message: RequestMessage = {
            type: MessageType.REQUEST,
            requestId,
            method,
            path,
            headers: headers || {},
            body,
            streaming
        };

        connection.ws.send(JSON.stringify(message));
    });
}
```

### Requête streaming

```typescript
export function sendEdgeStreamRequest(
    environmentId: number,
    method: string,
    path: string,
    callbacks: {
        onData: (data: string, stream?: 'stdout' | 'stderr') => void;
        onEnd: (reason?: string) => void;
        onError: (error: string) => void;
    },
    body?: unknown,
    headers?: Record<string, string>
): { requestId: string; cancel: () => void } {
    const connection = edgeConnections.get(environmentId);
    if (!connection) {
        callbacks.onError('Edge agent not connected');
        return { requestId: '', cancel: () => {} };
    }

    const requestId = secureRandomUUID();

    connection.pendingStreamRequests.set(requestId, {
        onData: callbacks.onData,
        onEnd: callbacks.onEnd,
        onError: callbacks.onError
    });

    const message: RequestMessage = {
        type: MessageType.REQUEST,
        requestId,
        method,
        path,
        headers: headers || {},
        body,
        streaming: true
    };

    connection.ws.send(JSON.stringify(message));

    return {
        requestId,
        cancel: () => {
            connection.pendingStreamRequests.delete(requestId);
            const cancelMessage: StreamEndMessage = {
                type: 'stream_end',
                requestId,
                reason: 'cancelled'
            };
            connection.ws.send(JSON.stringify(cancelMessage));
        }
    };
}
```

## 5. Container Events

### Message container_event

```typescript
interface ContainerEventMessage {
    type: 'container_event';
    event: {
        containerId: string;
        containerName?: string;
        image?: string;
        action: string;           // start, stop, die, kill, restart, etc.
        actorAttributes?: Record<string, string>;
        timestamp: string;        // ISO 8601
    };
}
```

### Traitement des événements

```typescript
export async function handleEdgeContainerEvent(
    environmentId: number,
    event: ContainerEventMessage['event']
): Promise<void> {
    console.log(`Container event from env ${environmentId}: ${event.action}`);

    // Sauvegarder en DB
    const savedEvent = await logContainerEvent({
        environmentId,
        containerId: event.containerId,
        containerName: event.containerName || null,
        image: event.image || null,
        action: event.action as ContainerEventAction,
        actorAttributes: event.actorAttributes || null,
        timestamp: event.timestamp
    });

    // Émettre SSE pour les clients connectés
    containerEventEmitter.emit('event', savedEvent);

    // Envoyer notification
    const actionLabel = event.action.charAt(0).toUpperCase() 
                      + event.action.slice(1);
    const containerLabel = event.containerName 
                         || event.containerId.substring(0, 12);

    await sendEnvironmentNotification(
        environmentId,
        event.action as ContainerEventAction,
        {
            title: `Container ${actionLabel}`,
            message: `Container "${containerLabel}" ${event.action}`,
            type: event.action === 'die' ? 'error' : 'info'
        },
        event.image
    );
}
```

## 6. Métriques système

### Message metrics

```typescript
interface MetricsMessage {
    type: 'metrics';
    timestamp: number;          // Unix timestamp
    metrics: {
        cpuUsage: number;       // Pourcentage total (tous cores)
        cpuCores: number;       // Nombre de cores
        memoryTotal: number;    // Bytes
        memoryUsed: number;     // Bytes
        memoryFree: number;     // Bytes
        diskTotal: number;      // Bytes
        diskUsed: number;       // Bytes
        diskFree: number;       // Bytes
        networkRxBytes: number; // Bytes reçus
        networkTxBytes: number; // Bytes envoyés
        uptime: number;         // Secondes
    };
}
```

### Traitement des métriques

```typescript
export async function handleEdgeMetrics(
    environmentId: number,
    metrics: MetricsMessage['metrics']
): Promise<void> {
    // Stocker dans la connexion pour accès rapide
    const connection = edgeConnections.get(environmentId);
    if (connection) {
        connection.lastMetrics = {
            uptime: metrics.uptime,
            cpuUsage: metrics.cpuUsage,
            memoryTotal: metrics.memoryTotal,
            memoryUsed: metrics.memoryUsed
        };
    }

    // Normaliser CPU par core
    const cpuPercent = metrics.cpuCores > 0 
        ? metrics.cpuUsage / metrics.cpuCores 
        : metrics.cpuUsage;

    // Calculer % mémoire
    const memoryPercent = metrics.memoryTotal > 0
        ? (metrics.memoryUsed / metrics.memoryTotal) * 100
        : 0;

    // Sauvegarder en DB pour graphiques
    await saveHostMetric(
        cpuPercent,
        memoryPercent,
        metrics.memoryUsed,
        metrics.memoryTotal,
        environmentId
    );
}
```

## 7. Terminal bidirectionnel

### Messages exec

```typescript
// Windflow-sample → Agent : Démarrer exec
interface ExecStartMessage {
    type: 'exec_start';
    execId: string;           // UUID unique
    containerId: string;
    cmd: string;              // Commande (e.g., "/bin/bash")
    user: string;             // User dans le conteneur
    cols: number;             // Terminal width
    rows: number;             // Terminal height
}

// Agent → Windflow-sample : Exec prêt
interface ExecReadyMessage {
    type: 'exec_ready';
    execId: string;
}

// Windflow-sample → Agent : Input utilisateur
interface ExecInputMessage {
    type: 'exec_input';
    execId: string;
    data: string;             // Base64-encoded
}

// Agent → Windflow-sample : Output du conteneur
interface ExecOutputMessage {
    type: 'exec_output';
    execId: string;
    data: string;             // Base64-encoded
}

// Bi-directionnel : Resize terminal
interface ExecResizeMessage {
    type: 'exec_resize';
    execId: string;
    cols: number;
    rows: number;
}

// Bi-directionnel : Fin exec
interface ExecEndMessage {
    type: 'exec_end';
    execId: string;
    reason?: string;
}
```

## 8. Sécurité

### Token security
- Génération cryptographique : 32 bytes (256 bits)
- Hashing : Argon2id avec salt unique
- Préfixe : 8 caractères pour identification visuelle
- Expiration : Support des tokens temporaires
- Révocation : Désactivation immédiate

### Connection security
- TLS/WSS obligatoire en production
- Validation du token à la connexion
- Timeout automatique (90s sans heartbeat)
- Remplacement de connexion (1 agent max par environnement)
- Nettoyage des requêtes en attente lors de la déconnexion

### Request security
- Timeout par requête (30s par défaut)
- Validation de l'environnement ID
- Corrélation request/response par UUID
- Pas d'exécution de code arbitraire (routing Docker API uniquement)

## 9. Exemple d'utilisation

### Frontend TypeScript (Vue3)

```typescript
// routes/api/containers/+server.ts
import { sendEdgeRequest } from '$lib/server/hawser';
import { isEdgeConnected } from '$lib/server/hawser';

export async function GET({ locals, url }) {
    const envId = Number(url.searchParams.get('envId'));

    if (isEdgeConnected(envId)) {
        // Environnement distant via Hawser
        const response = await sendEdgeRequest(
            envId,
            'GET',
            '/containers/json?all=1'
        );

        return new Response(response.body, {
            status: response.statusCode,
            headers: response.headers
        });
    } else {
        // Environnement local
        const dockerResponse = await fetch(
            'http://localhost:2375/containers/json?all=1'
        );
        return dockerResponse;
    }
}
```

### Logs streaming

```typescript
// routes/api/containers/[id]/logs/+server.ts
import { sendEdgeStreamRequest } from '$lib/server/hawser';

export async function GET({ params, url, locals }) {
    const envId = Number(url.searchParams.get('envId'));
    const containerId = params.id;

    const stream = new ReadableStream({
        start(controller) {
            const { cancel } = sendEdgeStreamRequest(
                envId,
                'GET',
                `/containers/${containerId}/logs?stdout=1&stderr=1&follow=1`,
                {
                    onData: (data) => {
                        controller.enqueue(
                            new TextEncoder().encode(data)
                        );
                    },
                    onEnd: () => {
                        controller.close();
                    },
                    onError: (error) => {
                        controller.error(new Error(error));
                    }
                }
            );

            // Cleanup sur abort
            return () => cancel();
        }
    });

    return new Response(stream, {
        headers: {
            'Content-Type': 'text/plain',
            'Transfer-Encoding': 'chunked'
        }
    });
}
```

## 10. Monitoring

### Connection status

```typescript
export function isEdgeConnected(environmentId: number): boolean {
    return edgeConnections.has(environmentId);
}

export function getEdgeConnectionInfo(
    environmentId: number
): EdgeConnection | undefined {
    return edgeConnections.get(environmentId);
}

export function getAllEdgeConnections(): Map<number, EdgeConnection> {
    return edgeConnections;
}
```

### Dashboard metrics

```typescript
// Afficher uptime, CPU, mémoire dans le dashboard
const info = getEdgeConnectionInfo(envId);
if (info?.lastMetrics) {
    console.log(`Uptime: ${info.lastMetrics.uptime}s`);
    console.log(`CPU: ${info.lastMetrics.cpuUsage}%`);
    console.log(`Memory: ${info.lastMetrics.memoryUsed} / ${info.lastMetrics.memoryTotal}`);
}
```

---

[← Vulnerability Scanning](07-VULNERABILITY-SCANNING.md) | [Suivant : Scheduler →](09-SCHEDULER.md)
