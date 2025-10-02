#!/usr/bin/env bash
# ============================================================================
# WindFlow Backend Launcher
# ============================================================================
# Script de lancement du backend FastAPI WindFlow
#
# Usage:
#   ./run.sh              # Lance en mode development (avec reload)
#   ./run.sh dev          # Lance en mode development (avec reload)
#   ./run.sh prod         # Lance en mode production (sans reload)
#   ./run.sh --help       # Affiche l'aide
#
# Prérequis:
#   - Poetry installé (https://python-poetry.org/)
#   - Python 3.11+
#
# Variables d'environnement (optionnelles):
#   HOST              # Adresse d'écoute (défaut: 0.0.0.0)
#   PORT              # Port d'écoute (défaut: 8000)
#   LOG_LEVEL         # Niveau de log (défaut: info)
#   WORKERS           # Nombre de workers (production uniquement)
#
# ============================================================================

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# Couleurs pour l'affichage
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration par défaut
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BACKEND_MODULE="backend.app.main:app"
readonly DEFAULT_HOST="${HOST:-0.0.0.0}"
readonly DEFAULT_PORT="${PORT:-8000}"
readonly DEFAULT_LOG_LEVEL="${LOG_LEVEL:-info}"
readonly DATA_DIR="${SCRIPT_DIR}/data/windflow"
readonly ENV_FILE="${SCRIPT_DIR}/.env"
readonly ENV_EXAMPLE="${SCRIPT_DIR}/env.example"

# Mode par défaut
MODE="${1:-dev}"

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_help() {
    cat << EOF
${GREEN}WindFlow Backend Launcher${NC}

${BLUE}Usage:${NC}
  ./run.sh [MODE]

${BLUE}Modes:${NC}
  dev       Lance le backend en mode développement avec hot-reload (défaut)
  prod      Lance le backend en mode production
  --help    Affiche cette aide

${BLUE}Variables d'environnement:${NC}
  HOST              Adresse d'écoute (défaut: 0.0.0.0)
  PORT              Port d'écoute (défaut: 8000)
  LOG_LEVEL         Niveau de log (défaut: info)
  WORKERS           Nombre de workers en mode production (défaut: 4)

${BLUE}Exemples:${NC}
  ./run.sh                    # Mode développement
  ./run.sh dev                # Mode développement
  ./run.sh prod               # Mode production
  PORT=8080 ./run.sh          # Mode développement sur le port 8080
  WORKERS=8 ./run.sh prod     # Mode production avec 8 workers

${BLUE}Documentation:${NC}
  - Backend:        doc/spec/03-technology-stack.md
  - Configuration:  doc/spec/15-deployment-guide.md
  - API:            http://localhost:8000/docs (une fois lancé)

EOF
}

# ============================================================================
# VALIDATIONS
# ============================================================================

check_poetry() {
    log_info "Vérification de Poetry..."

    if ! command -v poetry &> /dev/null; then
        log_error "Poetry n'est pas installé."
        echo ""
        echo "Installation de Poetry:"
        echo "  curl -sSL https://install.python-poetry.org | python3 -"
        echo ""
        echo "Ou consultez: https://python-poetry.org/docs/#installation"
        exit 1
    fi

    log_success "Poetry est installé: $(poetry --version)"
}

check_python_version() {
    log_info "Vérification de la version Python..."

    local python_version
    python_version=$(poetry run python --version 2>&1 | awk '{print $2}')
    local major_version
    major_version=$(echo "$python_version" | cut -d. -f1)
    local minor_version
    minor_version=$(echo "$python_version" | cut -d. -f2)

    if [[ "$major_version" -lt 3 ]] || [[ "$major_version" -eq 3 && "$minor_version" -lt 11 ]]; then
        log_error "Python 3.11+ est requis (version détectée: $python_version)"
        exit 1
    fi

    log_success "Version Python: $python_version"
}

check_dependencies() {
    log_info "Vérification des dépendances..."

    if [[ ! -f "${SCRIPT_DIR}/poetry.lock" ]]; then
        log_warning "poetry.lock non trouvé. Installation des dépendances..."
        poetry install
    else
        # Vérifier si les dépendances sont à jour
        if ! poetry check --quiet 2>/dev/null; then
            log_warning "Dépendances obsolètes. Mise à jour..."
            poetry install
        else
            log_success "Dépendances installées"
        fi
    fi
}

setup_environment() {
    log_info "Configuration de l'environnement..."

    # Vérifier si .env existe
    if [[ ! -f "$ENV_FILE" ]]; then
        log_warning "Fichier .env non trouvé."

        if [[ -f "$ENV_EXAMPLE" ]]; then
            echo ""
            read -p "Voulez-vous créer .env depuis env.example? (O/n) " -n 1 -r
            echo ""

            if [[ $REPLY =~ ^[Oo]$ ]] || [[ -z $REPLY ]]; then
                cp "$ENV_EXAMPLE" "$ENV_FILE"
                log_success "Fichier .env créé depuis env.example"
                log_warning "⚠ Pensez à configurer les variables dans .env avant la production!"
            else
                log_warning "L'application utilisera les valeurs par défaut"
            fi
        else
            log_warning "env.example non trouvé. L'application utilisera les valeurs par défaut"
        fi
    else
        log_success "Fichier .env trouvé"
    fi

    # Créer le répertoire de données pour SQLite
    if [[ ! -d "$DATA_DIR" ]]; then
        log_info "Création du répertoire de données: $DATA_DIR"
        mkdir -p "$DATA_DIR"
        log_success "Répertoire de données créé"
    fi
}

validate_mode() {
    case "$MODE" in
        dev|development)
            MODE="dev"
            ;;
        prod|production)
            MODE="prod"
            ;;
        --help|-h|help)
            print_help
            exit 0
            ;;
        *)
            log_error "Mode invalide: $MODE"
            echo ""
            echo "Modes valides: dev, prod"
            echo "Utilisez --help pour plus d'informations"
            exit 1
            ;;
    esac
}

# ============================================================================
# LANCEMENT DU BACKEND
# ============================================================================

start_development() {
    log_info "Lancement du backend en mode DÉVELOPPEMENT..."
    echo ""
    log_info "Configuration:"
    echo "  - Module:     ${BACKEND_MODULE}"
    echo "  - Host:       ${DEFAULT_HOST}"
    echo "  - Port:       ${DEFAULT_PORT}"
    echo "  - Log Level:  ${DEFAULT_LOG_LEVEL}"
    echo "  - Hot Reload: Activé"
    echo ""
    log_success "Backend démarré!"
    log_info "API disponible sur: http://localhost:${DEFAULT_PORT}"
    log_info "Documentation API:  http://localhost:${DEFAULT_PORT}/docs"
    log_info "Health check:       http://localhost:${DEFAULT_PORT}/health"
    echo ""
    log_info "Appuyez sur Ctrl+C pour arrêter"
    echo ""

    # Lancer uvicorn avec reload
    poetry run uvicorn "${BACKEND_MODULE}" \
        --host "${DEFAULT_HOST}" \
        --port "${DEFAULT_PORT}" \
        --reload \
        --log-level "${DEFAULT_LOG_LEVEL}"
}

start_production() {
    local workers="${WORKERS:-4}"

    log_info "Lancement du backend en mode PRODUCTION..."
    echo ""
    log_info "Configuration:"
    echo "  - Module:     ${BACKEND_MODULE}"
    echo "  - Host:       ${DEFAULT_HOST}"
    echo "  - Port:       ${DEFAULT_PORT}"
    echo "  - Log Level:  ${DEFAULT_LOG_LEVEL}"
    echo "  - Workers:    ${workers}"
    echo "  - Hot Reload: Désactivé"
    echo ""
    log_success "Backend démarré!"
    log_info "API disponible sur: http://localhost:${DEFAULT_PORT}"
    log_info "Documentation API:  http://localhost:${DEFAULT_PORT}/docs"
    log_info "Health check:       http://localhost:${DEFAULT_PORT}/health"
    echo ""
    log_info "Appuyez sur Ctrl+C pour arrêter"
    echo ""

    # Lancer uvicorn en mode production
    poetry run uvicorn "${BACKEND_MODULE}" \
        --host "${DEFAULT_HOST}" \
        --port "${DEFAULT_PORT}" \
        --workers "${workers}" \
        --log-level "${DEFAULT_LOG_LEVEL}" \
        --no-access-log
}

# ============================================================================
# SCRIPT PRINCIPAL
# ============================================================================

main() {
    # Afficher l'en-tête
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                    ║${NC}"
    echo -e "${GREEN}║           WindFlow Backend Launcher                ║${NC}"
    echo -e "${GREEN}║                                                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Valider le mode
    validate_mode

    # Validations
    check_poetry
    check_python_version
    check_dependencies
    setup_environment

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Lancer le backend selon le mode
    case "$MODE" in
        dev)
            start_development
            ;;
        prod)
            start_production
            ;;
    esac
}

# Gestion des signaux
trap 'echo ""; log_warning "Arrêt du backend..."; exit 0' INT TERM

# Lancer le script
main "$@"
