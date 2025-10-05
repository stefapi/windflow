# WindFlow Frontend

Modern Vue 3 frontend for the WindFlow Docker deployment platform.

## 🚀 Tech Stack

- **Vue 3** - Progressive JavaScript framework with Composition API
- **TypeScript** - Type-safe development
- **Vite** - Fast build tool and dev server
- **Element Plus** - Vue 3 UI component library
- **UnoCSS** - Instant on-demand atomic CSS engine
- **Pinia** - Vue state management
- **Vue Router** - Official routing solution
- **Vue Flow** - Visual workflow editor with node-based UI
- **Axios** - HTTP client for API requests
- **WebSocket** - Real-time communication for logs and notifications

## 📋 Prerequisites

- Node.js >= 18.x
- npm or pnpm

## 🛠️ Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` to set your API endpoint:
   ```env
   VITE_API_BASE_URL=http://localhost:8000/api/v1
   VITE_WS_URL=ws://localhost:8000/ws
   ```

## 🔧 Development

**Start development server:**
```bash
npm run dev
```

The application will be available at `http://localhost:5173`

**Type checking:**
```bash
npm run type-check
```

**Lint code:**
```bash
npm run lint
```

## 🏗️ Build

**Production build:**
```bash
npm run build
```

**Preview production build:**
```bash
npm run preview
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── layouts/          # Layout components (MainLayout)
│   ├── views/            # Page components
│   │   ├── Dashboard.vue
│   │   ├── Targets.vue
│   │   ├── Stacks.vue
│   │   ├── Deployments.vue
│   │   ├── Workflows.vue
│   │   ├── WorkflowEditor.vue
│   │   └── Marketplace.vue
│   ├── stores/           # Pinia stores
│   │   ├── auth.ts
│   │   ├── targets.ts
│   │   ├── stacks.ts
│   │   ├── deployments.ts
│   │   ├── workflows.ts
│   │   └── marketplace.ts
│   ├── services/         # API and WebSocket services
│   │   ├── api.ts        # REST API client
│   │   ├── http.ts       # HTTP client configuration
│   │   └── websocket.ts  # WebSocket service
│   ├── types/            # TypeScript type definitions
│   │   └── api.ts
│   ├── router/           # Vue Router configuration
│   │   └── index.ts
│   ├── App.vue           # Root component
│   └── main.ts           # Application entry point
├── index.html            # HTML template
├── vite.config.ts        # Vite configuration
├── tsconfig.json         # TypeScript configuration
├── uno.config.ts         # UnoCSS configuration
├── eslint.config.js      # ESLint configuration
└── package.json          # Dependencies and scripts
```

## 🎨 Key Features

### Visual Workflow Editor
- Drag-and-drop node-based workflow designer
- Pre-built node types (deploy, condition, notification)
- Real-time execution monitoring

### Real-time Updates
- WebSocket integration for live deployment logs
- Server-Sent Events (SSE) for notifications
- Automatic reconnection with exponential backoff

### State Management
- Centralized Pinia stores for all entities
- Persistent authentication state
- Reactive data updates

### Responsive UI
- Element Plus components with UnoCSS styling
- Mobile-friendly responsive design
- Dark mode support (via Element Plus)

## 🔌 API Integration

The frontend communicates with the WindFlow backend API:

- **Authentication:** JWT-based token authentication
- **REST API:** CRUD operations for all entities
- **WebSocket:** Real-time updates for deployments and notifications

## 🧪 Development Guidelines

- Use **Composition API** with `<script setup>`
- Follow **TypeScript strict mode**
- Use **Element Plus** components for UI
- Use **UnoCSS** utility classes for styling
- Store state in **Pinia stores**
- Follow Vue 3 best practices

## 📝 Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run type-check` | Run TypeScript type checking |
| `npm run lint` | Lint and fix code |

## 🤝 Contributing

Follow the project's coding guidelines and ensure all type checks pass before committing.

## 📄 License

Part of the WindFlow project. See main repository LICENSE file.
