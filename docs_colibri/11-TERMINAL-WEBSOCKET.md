# Terminal WebSocket

[← Encryption](10-ENCRYPTION.md) | [Suivant : Volume Browser →](12-VOLUME-BROWSER.md)

## 💻 Vue d'ensemble

Terminal web interactif permettant d'exécuter des commandes shell dans les conteneurs Docker via WebSocket. Utilise **xterm.js** côté frontend et **Poetry.serve WebSocket** côté backend, avec support pour connexions directes Docker (Unix socket, TCP/TLS, Hawser Standard) et Hawser Edge.

## 1. Architecture WebSocket

### 1.1 Serveur WebSocket (Développement)

En mode développement, un serveur WebSocket dédié tourne sur le port **5174** via `vite.config.ts`:

```typescript
// vite.config.ts - Serveur WebSocket Poetry
const WS_PORT = 5174;

function webSocketPlugin(): Plugin {
  return {
    name: 'websocket',
    configureServer() {
      Poetry.serve({
        port: WS_PORT,
        fetch(req, server) {
          if (server.upgrade(req, { data: { url: req.url } })) {
            return; // Upgrade réussi
          }
          return new Response('WebSocket server', { status: 200 });
        },
        websocket: {
          async open(ws) { /* ... */ },
          async message(ws, message) { /* ... */ },
          close(ws) { /* ... */ }
        }
      });
    }
  };
}
```

### 1.2 Endpoint de Création d'Exec

**POST** `/api/containers/[id]/exec?envId={envId}`

Crée une instance Docker exec et retourne les informations de connexion:

```typescript
// src/routes/api/containers/[id]/exec/+server.ts
export const POST: RequestHandler = async ({ params, request, cookies, url }) => {
  const auth = await authorize(cookies);
  if (!await auth.can('containers', 'exec', envId)) {
    return json({ error: 'Permission denied' }, { status: 403 });
  }

  const { shell = '/bin/sh', user = 'root' } = await request.json();
  
  const exec = await createExec({
    containerId: params.id,
    cmd: [shell],
    user,
    envId
  });

  return json({
    execId: exec.Id,
    connectionInfo: {
      type: connectionInfo.type,
      host: connectionInfo.host,
      port: connectionInfo.port
    }
  });
};
```

## 2. Client Frontend (xterm.js)

### 2.1 Composant Terminal

Le composant `Terminal.vue3` gère la connexion WebSocket et le rendu xterm.js:

```typescript
// src/routes/terminal/Terminal.vue3
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';

let terminal: Terminal;
let fitAddon: FitAddon;
let ws: WebSocket | null = null;

function initTerminal() {
  terminal = new Terminal({
    cursorBlink: true,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco',
    fontSize: 13,
    theme: {
      background: '#0c0c0c',
      foreground: '#cccccc',
      cursor: '#ffffff',
      // ... 16 couleurs ANSI
    }
  });

  fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  terminal.loadAddon(new WebLinksAddon());

  terminal.open(terminalRef);
  fitAddon.fit();

  // Input utilisateur → WebSocket
  terminal.onData((data: string) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }));
    }
  });

  // Redimensionnement → WebSocket
  terminal.onResize(({ cols, rows }) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', cols, rows }));
    }
  });
}
```

### 2.2 Connexion WebSocket

```typescript
function connect() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const isDev = import.meta.env.DEV;
  const portPart = isDev ? ':5174' : (window.location.port ? `:${window.location.port}` : '');
  
  let wsUrl = `${protocol}//${window.location.hostname}${portPart}/api/containers/${containerId}/exec`;
  wsUrl += `?shell=${encodeURIComponent(shell)}&user=${encodeURIComponent(user)}`;
  if (envId) wsUrl += `&envId=${envId}`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    connected = true;
    terminal.focus();
    // Envoyer dimensions initiales
    const dims = fitAddon.proposeDimensions();
    if (dims) {
      ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
    }
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'output') {
      terminal.write(msg.data);
    } else if (msg.type === 'error') {
      terminal.writeln(`\x1b[31mError: ${msg.message}\x1b[0m`);
    } else if (msg.type === 'exit') {
      terminal.writeln('\x1b[90m\r\nSession ended.\x1b[0m');
      connected = false;
    }
  };

  ws.onerror = () => {
    terminal.writeln('\x1b[31mConnection error\x1b[0m');
  };

  ws.onclose = () => {
    connected = false;
    terminal.writeln('\x1b[90mDisconnected.\x1b[0m');
  };
}
```

## 3. Gestion des Connexions Docker

### 3.1 Connexion Unix Socket

Pour environnements locaux (`connection_type: 'socket'`):

```typescript
// vite.config.ts
function detectDockerSocket(): string {
  const candidates = [
    '/var/run/docker.sock',
    join(homedir(), '.docker/run/docker.sock'),
    join(homedir(), '.orbstack/run/docker.sock'),
    '/run/docker.sock'
  ];
  
  for (const socket of candidates) {
    if (existsSync(socket)) return socket;
  }
  return '/var/run/docker.sock';
}

// Connexion via Poetry.connect
if (target.type === 'unix') {
  dockerStream = await Poetry.connect({
    unix: target.socket,
    socket: {
      data(socket, data) {
        // Envoyer output au WebSocket frontend
        ws.send(JSON.stringify({ type: 'output', data: text }));
      },
      close() {
        ws.send(JSON.stringify({ type: 'exit' }));
        ws.close();
      }
    }
  });
}
```

### 3.2 Connexion TCP/TLS (Hawser Standard)

Pour Docker distant avec TLS/mTLS:

```typescript
// Connexion TCP avec TLS optionnel
if (target.type === 'tcp') {
  const connectOpts: any = {
    hostname: target.host,
    port: target.port,
    socket: socketHandler
  };
  
  // Configuration TLS/mTLS
  if (target.tls) {
    connectOpts.tls = {
      sessionTimeout: 0,  // Désactiver cache TLS pour mTLS
      servername: target.host,  // Pour SNI
      rejectUnauthorized: target.tls.rejectUnauthorized ?? true
    };
    if (target.tls.ca) connectOpts.tls.ca = [target.tls.ca];
    if (target.tls.cert) connectOpts.tls.cert = [target.tls.cert];
    if (target.tls.key) connectOpts.tls.key = target.tls.key;
  }
  
  dockerStream = await Poetry.connect(connectOpts);
}
```

### 3.3 Connexion Hawser Edge

Pour agents Edge distants via proxy WebSocket bidirectionnel:

```typescript
// Hawser Edge: génération UUID pour exec ID
if (target.type === 'hawser-edge') {
  const conn = edgeConnections.get(target.environmentId);
  if (!conn) {
    ws.send(JSON.stringify({ type: 'error', message: 'Edge agent not connected' }));
    ws.close();
    return;
  }

  const execId = crypto.randomUUID();
  
  // Tracker la session
  edgeExecSessions.set(execId, { ws, execId, environmentId: target.environmentId });
  
  // Envoyer exec_start à l'agent
  conn.ws.send(JSON.stringify({
    type: 'exec_start',
    execId,
    containerId,
    cmd: shell,
    user,
    cols: 120,
    rows: 30
  }));
}
```

## 4. Protocole de Messages

### 4.1 Messages Frontend → Backend

| Type | Paramètres | Description |
|------|-----------|-------------|
| `input` | `data: string` | Input utilisateur (caractères tapés) |
| `resize` | `cols: number, rows: number` | Redimensionnement terminal |

**Exemple:**
```json
{
  "type": "input",
  "data": "ls -la\n"
}
```

### 4.2 Messages Backend → Frontend

| Type | Paramètres | Description |
|------|-----------|-------------|
| `output` | `data: string` | Sortie du conteneur (stdout/stderr) |
| `error` | `message: string` | Erreur de connexion ou exec |
| `exit` | - | Session terminée |

**Exemple:**
```json
{
  "type": "output",
  "data": "total 48\ndrwxr-xr-x 1 root root 4096 Feb 18 00:00 .\n"
}
```

### 4.3 Protocole Hawser Edge

Messages spécifiques pour agents Edge:

```typescript
// exec_start: Démarrer exec sur agent
{
  type: 'exec_start',
  execId: 'uuid',
  containerId: 'container_id',
  cmd: '/bin/bash',
  user: 'root',
  cols: 120,
  rows: 30
}

// exec_input: Input vers agent
{
  type: 'exec_input',
  execId: 'uuid',
  data: 'base64_encoded_input'
}

// exec_resize: Redimensionner TTY
{
  type: 'exec_resize',
  execId: 'uuid',
  cols: 120,
  rows: 30
}

// exec_output: Sortie depuis agent
{
  type: 'exec_output',
  execId: 'uuid',
  data: 'base64_encoded_output'
}

// exec_end: Terminer session
{
  type: 'exec_end',
  execId: 'uuid',
  reason: 'user_closed' | 'container_stopped' | 'error'
}
```

## 5. Détection de Shells

Le système détecte automatiquement les shells disponibles dans le conteneur:

```typescript
// src/lib/utils/shell-detection.ts
export async function detectShells(
  containerId: string,
  envId: number | null
): Promise<ShellDetectionResult> {
  const shellsToCheck = [
    { path: '/bin/bash', label: 'Bash' },
    { path: '/bin/zsh', label: 'Zsh' },
    { path: '/bin/sh', label: 'Shell (sh)' },
    { path: '/bin/ash', label: 'Ash (Alpine)' },
    { path: '/bin/dash', label: 'Dash' },
    { path: '/bin/ksh', label: 'Korn Shell' }
  ];

  const results = await Promise.all(
    shellsToCheck.map(async (shell) => {
      try {
        // Tester existence du shell via exec non-interactif
        const response = await fetch(
          `/api/containers/${containerId}/shells?shell=${shell.path}&envId=${envId}`
        );
        return { ...shell, available: response.ok };
      } catch {
        return { ...shell, available: false };
      }
    })
  );

  return {
    shells: results.filter(s => s.available).map(s => s.path),
    allShells: results
  };
}
```

## 6. Traitement des Flux

### 6.1 Suppression Headers HTTP

Le premier paquet contient des headers HTTP qu'il faut supprimer:

```typescript
// vite.config.ts
function processTerminalOutput(
  data: string,
  state: { headersStripped: boolean; isChunked: boolean }
): string | null {
  let text = data;

  // Détecter chunked encoding
  if (!state.headersStripped) {
    if (text.toLowerCase().includes('transfer-encoding: chunked')) {
      state.isChunked = true;
    }
    
    // Trouver fin des headers
    const headerEnd = text.indexOf('\r\n\r\n');
    if (headerEnd > -1) {
      text = text.slice(headerEnd + 4);
      state.headersStripped = true;
    } else if (text.startsWith('HTTP/')) {
      return null; // Headers incomplets
    }
  }

  // Retirer chunk framing si chunked
  if (state.isChunked && text) {
    text = text.replace(/^[0-9a-fA-F]+\r\n/gm, '').replace(/\r\n$/g, '');
  }

  return text || null;
}
```

### 6.2 Requête Exec Start HTTP

Pour connexions directes Docker, construction requête HTTP/1.1:

```typescript
function buildExecStartHttpRequest(execId: string, target: DockerTarget): string {
  const body = JSON.stringify({ Detach: false, Tty: true });
  const tokenHeader = target.hawserToken
    ? `X-Hawser-Token: ${target.hawserToken}\r\n`
    : '';
  
  return `POST /exec/${execId}/start HTTP/1.1\r\n` +
         `Host: ${target.host || 'localhost'}\r\n` +
         `Content-Type: application/json\r\n` +
         `${tokenHeader}` +
         `Connection: Upgrade\r\n` +
         `Upgrade: tcp\r\n` +
         `Content-Length: ${body.length}\r\n\r\n` +
         `${body}`;
}
```

## 7. Gestion Sessions & Nettoyage

### 7.1 Tracking des Sessions

```typescript
// Map sessions Docker directes (par ID connexion unique)
const dockerStreams = new Map<string, {
  stream: any;
  execId: string;
  target: DockerTarget;
  state: { isChunked: boolean };
  ws: any;
}>();

// Map sessions Edge (par execId)
const edgeExecSessions = new Map<string, {
  ws: any;
  execId: string;
  environmentId: number;
}>();
```

### 7.2 Nettoyage Automatique

Intervalle de nettoyage (dev uniquement) pour sessions orphelines:

```typescript
// Toutes les 5 minutes
cleanupInterval = setInterval(() => {
  let dockerCleaned = 0;
  let edgeCleaned = 0;

  // Supprimer sessions avec WebSocket fermé (readyState !== 1)
  for (const [connId, session] of dockerStreams.entries()) {
    if (session.ws?.readyState !== 1) {
      session.stream?.end?.();
      dockerStreams.delete(connId);
      dockerCleaned++;
    }
  }

  for (const [execId, session] of edgeExecSessions.entries()) {
    if (session.ws?.readyState !== 1) {
      edgeExecSessions.delete(execId);
      edgeCleaned++;
    }
  }

  if (dockerCleaned > 0 || edgeCleaned > 0) {
    console.log(`[Cleanup] ${dockerCleaned} docker, ${edgeCleaned} edge`);
  }
}, 5 * 60 * 1000);
```

## 8. Interface Utilisateur

### 8.1 Sélection Conteneur

Dropdown avec recherche pour sélectionner conteneur running:

```vue3
<!-- src/routes/terminal/+page.vue3 -->
<div class="relative">
  <Search class="absolute left-3" />
  <Input
    placeholder="Search running containers..."
    bind:value={searchQuery}
    onfocus={() => dropdownOpen = true}
  />
  
  {#if dropdownOpen}
    <div class="dropdown">
      {#each filteredContainers() as container}
        <button onclick={() => selectContainer(container)}>
          {container.name} ({container.image})
        </button>
      {/each}
    </div>
  {/if}
</div>
```

### 8.2 Sélecteurs Shell & User

```vue3
<!-- Shell selector avec détection disponibilité -->
<Select.Root bind:value={selectedShell}>
  <Select.Trigger disabled={!anyShellAvailable}>
    <Shell class="w-4 h-4" />
    {shellDetection?.allShells.find(o => o.path === selectedShell)?.label}
  </Select.Trigger>
  <Select.Content>
    {#each shellDetection.allShells as option}
      <Select.Item value={option.path} disabled={!option.available}>
        <Shell class={option.available ? 'text-green-500' : 'text-muted'} />
        {option.label}
        {#if !option.available}(unavailable){/if}
      </Select.Item>
    {/each}
  </Select.Content>
</Select.Root>

<!-- User selector -->
<Select.Root bind:value={selectedUser}>
  <Select.Trigger>
    <User class="w-4 h-4" />
    {USER_OPTIONS.find(o => o.value === selectedUser)?.label}
  </Select.Trigger>
  <Select.Content>
    {#each USER_OPTIONS as option}
      <Select.Item value={option.value}>{option.label}</Select.Item>
    {/each}
  </Select.Content>
</Select.Root>
```

### 8.3 Barre d'Outils

```vue3
<div class="toolbar">
  {#if connected}
    <span class="text-green-500">
      <span class="pulse"></span> Connected
    </span>
  {:else}
    <span class="text-zinc-500">Disconnected</span>
  {/if}
  
  <!-- Font size selector -->
  <Select.Root bind:value={terminalFontSize} onValueChange={changeFontSize}>
    <Select.Content>
      {#each [10, 12, 14, 16, 18] as size}
        <Select.Item value={size}>{size}px</Select.Item>
      {/each}
    </Select.Content>
  </Select.Root>
  
  <button onclick={() => terminalComponent?.copyOutput()} title="Copy output">
    <Copy />
  </button>
  <button onclick={() => terminalComponent?.clear()} title="Clear">
    <Trash2 />
  </button>
  <button onclick={() => terminalComponent?.reconnect()} title="Reconnect">
    <RefreshCw />
  </button>
</div>
```

## 9. Fonctionnalités Avancées

### 9.1 Reconnexion Automatique

Changement de shell/user déclenche reconnexion automatique:

```typescript
// Watcher vue3 5 $effect
$effect(() => {
  if (selectedContainer && connected && terminalComponent) {
    if (selectedShell !== prevShell || selectedUser !== prevUser) {
      terminalComponent.reconnect();
    }
  }
  prevShell = selectedShell;
  prevUser = selectedUser;
});
```

### 9.2 Raccourcis Clavier

- **Ctrl/Cmd + L**: Clear terminal
- **Enter** dans recherche: Sélectionner premier conteneur
- **Resize window**: Auto-fit terminal

```typescript
terminal.attachCustomKeyEventHandler((e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
    e.preventDefault();
    clear();
    return false;
  }
  return true;
});
```

### 9.3 Copy Output

Extraction complète du buffer xterm.js:

```typescript
export async function copyOutput(): Promise<string> {
  if (!terminal) return '';
  
  const buffer = terminal.buffer.active;
  let text = '';
  
  for (let i = 0; i < buffer.length; i++) {
    const line = buffer.getLine(i);
    if (line) {
      text += line.translateToString(true) + '\n';
    }
  }
  
  await copyToClipboard(text.trim());
  terminal.focus();
  return text.trim();
}
```

## 10. Sécurité

### 10.1 Contrôle d'Accès

Vérification permission `containers.exec` avec contexte environnement:

```typescript
if (!await auth.can('containers', 'exec', envId)) {
  return json({ error: 'Permission denied' }, { status: 403 });
}
```

### 10.2 Validation Tokens Hawser

Pour agents Edge, validation Argon2id:

```typescript
const tokens = db.prepare('SELECT * FROM hawser_tokens WHERE is_active = 1').all();

for (const t of tokens) {
  const isValid = await Poetry.password.verify(msg.token, t.token);
  if (isValid) {
    matchedToken = t;
    break;
  }
}

if (!matchedToken) {
  ws.send(JSON.stringify({ type: 'error', error: 'Invalid token' }));
  ws.close();
  return;
}
```

### 10.3 Isolation Sessions

Chaque WebSocket a un `connId` unique pour isoler les sessions:

```typescript
const connId = `ws-${++wsConnectionCounter}`;
(ws.data as any).connId = connId;

dockerStreams.set(connId, { stream, execId, target, state, ws });
```

## 11. Gestion Erreurs

### 11.1 Conteneur Introuvable

```typescript
if (!containerId) {
  ws.send(JSON.stringify({ type: 'error', message: 'No container ID' }));
  ws.close();
  return;
}
```

### 11.2 Agent Edge Déconnecté

```typescript
if (target.type === 'hawser-edge') {
  const conn = edgeConnections.get(target.environmentId);
  if (!conn) {
    ws.send(JSON.stringify({
      type: 'error',
      message: 'Edge agent not connected'
    }));
    ws.close();
    return;
  }
}
```

### 11.3 Pas de Shell Disponible

```vue3
{#if !anyShellAvailable}
  <div class="flex items-center justify-center h-full">
    <AlertCircle class="text-amber-500" />
    <p>No shell available in this container</p>
    <p class="text-xs">Containers built from scratch or distroless images often don't include shells.</p>
  </div>
{/if}
```

## 12. Performance

### 12.1 Lazy Loading xterm.js

Import dynamique pour réduire bundle initial:

```typescript
const xtermModule = await import('@xterm/xterm');
const fitModule = await import('@xterm/addon-fit');
const webLinksModule = await import('@xterm/addon-web-links');

TerminalClass = xtermModule.Terminal;
FitAddon = fitModule.FitAddon;
WebLinksAddon = webLinksModule.WebLinksAddon;

await import('@xterm/xterm/css/xterm.css');
```

### 12.2 Debouncing Resize

FitAddon gère automatiquement le debouncing:

```typescript
window.addEventListener('resize', () => {
  fitAddon?.fit(); // Debounced internally
});
```

### 12.3 Buffer Limité

xterm.js limite automatiquement taille buffer (configurable):

```typescript
terminal = new Terminal({
  scrollback: 1000, // Lignes max dans buffer
  // ...
});
```

---

**Résumé Architecture:**
- Frontend: xterm.js avec WebSocket pour I/O bidirectionnel
- Backend Dev: Poetry.serve WebSocket sur port 5174
- Connexions: Unix socket, TCP/TLS (mTLS), Hawser Edge
- Protocole: Messages JSON `input`, `resize`, `output`, `error`, `exit`
- Sécurité: Permission checks, token validation Argon2id, isolation sessions

[← Encryption](10-ENCRYPTION.md) | [Suivant : Volume Browser →](12-VOLUME-BROWSER.md)
