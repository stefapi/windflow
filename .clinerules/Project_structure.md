
## Structure des Projets

### Répertoire Racine
```
windflow/
├── Makefile               # Orchestrateur principal de tâches
├── Dockerfile             # Image Docker backend
├── compose.yaml           # Configuration services
├── docker-compose.yml     # Configuration services
├── compose.override.yml   # Surcharges pour développement
├── compose.prod.yml       # Configuration production
├── entrypoint.sh          # Script d'entrée Docker
├── debug.sh               # Script de debug développement
├── install.sh             # Script d'installation automatique
├── start.py               # Point d'entrée Python alternatif
├── gunicorn_conf.py       # Configuration serveur production
├── .env                   # Variables d'environnement locales
├── .env.example           # Template des variables d'environnement
├── .dockerignore          # Exclusions Docker build
├── .gitignore             # Exclusions Git
├── .editorconfig          # Configuration éditeur
├── pyproject.toml         # Configuration Python/Poetry
├── poetry.lock            # Verrous dépendances Python
├── requirements.txt       # Dépendances pour production
├── Vagrantfile            # Configuration développement Vagrant
└── package.json           # Scripts NPM globaux (si applicable)
```

### ClI
```
cli/
├── commands/          # Commandes CLI par catégorie
├── services/          # Services CLI
├── tui/               # Interfaces TUI
├── utils/             # Utilitaires CLI
├── config.py          # Configuration
├── main.py            # Point d'entrée CLI
├── tests/             # Tests CLI/TUI
└── completion/        # Scripts auto-complétion
```

### Backend (FastAPI)
```
backend/
├── app/
│   ├── api/           # Endpoints API REST
│   ├── auth/          # Authentification
│   ├── core/          # Configuration et utilitaires
│   ├── helper/        # Classes ou lib utilisées globalement
│   ├── middleware/    # Middlewares
│   ├── models/        # Modèles SQLAlchemy
│   ├── schemas/       # Schemas Pydantic
│   ├── services/      # Logique métier
│   ├── tasks/         # Tâches Celery
│   ├── tests/         # Tests automatisés
│   └── main.py        # Point d'entrée FastAPI
└── tests/             # Tests automatisés du backend
```

### Frontend (Vue.js 3)
```
frontend/
├── src/
│   ├── components/     # Composants réutilisables
│   │   ├── ui/         # Composants de base
│   │   └── features/   # Composants métier
│   ├── composables/    # Composables
│   ├── layout/         # Formats de page
│   ├── router/         # routeurs
│   ├── views/          # Pages/vues
│   ├── stores/         # State management Pinia
│   ├── services/       # API services
│   ├── types/          # Types TypeScript
│   └── utils/          # Utilitaires
├── public/             # Assets statiques
├── tests/              # Tests automatisés du frontend
└── package.json
```
### Documentation
```
doc/
├── spec/               # Specifications du projet
└── package.json
```

### Répertoire dev/
```
dev/
├── data/                # Données de développement
│   ├── fixtures/        # Jeux de données de test
│   ├── backups/         # Sauvegardes développement
│   ├── conf/            # Configurations spécifiques
│   ├── log/             # Logs de développement
│   ├── migration/       # Données de migration
│   └── users/           # Données utilisateurs de test
├── scripts/             # Scripts d'automatisation
│   ├── setup/           # Scripts d'installation/configuration
│   ├── generation/      # Génération de code automatique
│   ├── validation/      # Scripts de validation
│   └── deployment/      # Scripts de déploiement
└── templates/           # Templates de génération
    ├── backend/         # Templates Python/FastAPI
    ├── frontend/        # Templates Vue.js/TypeScript
    ├── infrastructure/  # Templates Docker/K8s
    └── documentation/   # Templates documentation
```
