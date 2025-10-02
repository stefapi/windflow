#!/bin/bash

# ============================================================================
# WINDFLOW - INSTALLATION MINIMALE ULTRA-SIMPLE
# ============================================================================
# Script d'installation rapide pour le core minimal de WindFlow
# Version: 2.0 - Architecture Modulaire
# ============================================================================

set -e  # Exit on error

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    WINDFLOW INSTALLATION                       ║"
    echo "║              Installation Minimale Ultra-Rapide                ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ============================================================================
# VÉRIFICATIONS PRÉREQUIS
# ============================================================================

check_prerequisites() {
    print_info "Vérification des prérequis..."

    local missing_deps=()

    # Vérifier Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    else
        print_success "Docker trouvé: $(docker --version | cut -d ' ' -f3 | cut -d ',' -f1)"
    fi

    # Vérifier Docker Compose
    if ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    else
        print_success "Docker Compose trouvé: $(docker compose version --short)"
    fi

    # Vérifier Git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        print_success "Git trouvé: $(git --version | cut -d ' ' -f3)"
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Prérequis manquants: ${missing_deps[*]}"
        echo ""
        print_info "Installation des prérequis:"
        echo "  - Docker: https://docs.docker.com/engine/install/"
        echo "  - Docker Compose: Inclus avec Docker Desktop"
        echo "  - Git: https://git-scm.com/downloads"
        exit 1
    fi

    print_success "Tous les prérequis sont satisfaits"
    echo ""
}

# ============================================================================
# CONFIGURATION
# ============================================================================

setup_environment() {
    print_info "Configuration de l'environnement..."

    # Copier .env.example vers .env si nécessaire
    if [ ! -f .env ]; then
        if [ -f env.example ]; then
            cp env.example .env
            print_success "Fichier .env créé à partir de env.example"
        else
            print_error "Fichier env.example introuvable"
            exit 1
        fi
    else
        print_warning "Fichier .env existe déjà, conservation de la configuration actuelle"
    fi

    # Générer un secret key aléatoire si nécessaire
    if grep -q "change-this-secret-key" .env; then
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "$(date +%s | sha256sum | base64 | head -c 32)")
        sed -i.bak "s/change-this-secret-key-in-production-use-openssl-rand-hex-32/$SECRET_KEY/" .env
        print_success "Secret key généré automatiquement"
    fi

    # Générer des mots de passe aléatoires
    if grep -q "change-this-password" .env; then
        DB_PASSWORD=$(openssl rand -base64 16 2>/dev/null || echo "windflow$(date +%s)")
        sed -i.bak "s/change-this-password/$DB_PASSWORD/g" .env
        print_success "Mots de passe générés automatiquement"
    fi

    # Nettoyer les fichiers de backup
    rm -f .env.bak

    print_success "Configuration de l'environnement terminée"
    echo ""
}

# ============================================================================
# INSTALLATION
# ============================================================================

install_minimal() {
    print_info "Installation du Core Minimal WindFlow..."
    echo ""
    print_info "Services inclus:"
    echo "  • API Backend (FastAPI)"
    echo "  • PostgreSQL"
    echo "  • Redis"
    echo "  • Frontend (Vue.js 3)"
    echo "  • Nginx (Reverse Proxy)"
    echo "  • Celery Worker"
    echo ""

    # Arrêter les conteneurs existants
    print_info "Arrêt des conteneurs existants..."
    docker compose down 2>/dev/null || true

    # Construire et démarrer les services
    print_info "Construction et démarrage des services (cela peut prendre quelques minutes)..."
    if docker compose -f docker-compose.minimal.yml up -d --build; then
        print_success "Services démarrés avec succès"
    else
        print_error "Échec du démarrage des services"
        exit 1
    fi

    # Attendre que les services soient prêts
    print_info "Attente de la disponibilité des services..."
    sleep 10

    # Vérifier la santé des services
    if docker compose -f docker-compose.minimal.yml ps | grep -q "Up"; then
        print_success "Les services sont opérationnels"
    else
        print_warning "Certains services pourraient ne pas être prêts"
    fi

    echo ""
}

# ============================================================================
# POST-INSTALLATION
# ============================================================================

run_migrations() {
    print_info "Exécution des migrations de base de données..."

    # Attendre que PostgreSQL soit prêt
    sleep 5

    if docker compose -f docker-compose.minimal.yml exec -T api alembic upgrade head 2>/dev/null; then
        print_success "Migrations appliquées avec succès"
    else
        print_warning "Les migrations ont échoué, vous devrez peut-être les exécuter manuellement"
        print_info "Commande: docker compose exec api alembic upgrade head"
    fi

    echo ""
}

display_info() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗"
    echo "║           ✅ INSTALLATION TERMINÉE AVEC SUCCÈS                 ║"
    echo "╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_info "Accès aux services:"
    echo ""
    echo "  🌐 Interface Web     : http://localhost:8080"
    echo "  📚 API Documentation : http://localhost:8080/api/docs"
    echo "  🔧 API Backend       : http://localhost:8080/api"
    echo ""
    print_info "Commandes utiles:"
    echo ""
    echo "  # Voir les logs"
    echo "  docker compose -f docker-compose.minimal.yml logs -f"
    echo ""
    echo "  # Arrêter les services"
    echo "  docker compose -f docker-compose.minimal.yml down"
    echo ""
    echo "  # Redémarrer les services"
    echo "  docker compose -f docker-compose.minimal.yml restart"
    echo ""
    echo "  # Voir l'état des services"
    echo "  docker compose -f docker-compose.minimal.yml ps"
    echo ""
    print_info "Extensions disponibles:"
    echo ""
    echo "  # Activer le monitoring (Prometheus + Grafana)"
    echo "  ./scripts/enable-extension.sh monitoring"
    echo ""
    echo "  # Activer les logs centralisés (ELK Stack)"
    echo "  ./scripts/enable-extension.sh logging"
    echo ""
    echo "  # Activer l'IA (LiteLLM + Ollama)"
    echo "  ./scripts/enable-extension.sh ai"
    echo ""
    echo "  # Liste complète des extensions"
    echo "  ./scripts/enable-extension.sh --list"
    echo ""
    print_info "Documentation:"
    echo ""
    echo "  📖 README             : cat README.md"
    echo "  🏗️  Architecture       : cat doc/ARCHITECTURE-MODULAIRE.md"
    echo "  🧩 Guide Extensions   : cat doc/EXTENSIONS-GUIDE.md"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

main() {
    clear
    print_header

    # Vérifier que nous sommes dans le bon répertoire
    if [ ! -f "docker-compose.minimal.yml" ]; then
        print_error "Fichier docker-compose.minimal.yml introuvable"
        print_info "Exécutez ce script depuis la racine du projet WindFlow"
        exit 1
    fi

    # Exécution des étapes
    check_prerequisites
    setup_environment
    install_minimal
    run_migrations
    display_info

    print_success "Installation terminée!"
    exit 0
}

# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

# Gestion des arguments
case "${1:-}" in
    --help|-h)
        print_header
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Afficher cette aide"
        echo "  --version, -v  Afficher la version"
        echo ""
        echo "Description:"
        echo "  Installe le Core Minimal de WindFlow avec les services essentiels uniquement."
        echo "  Pour ajouter des fonctionnalités avancées, utilisez le script enable-extension.sh"
        echo ""
        echo "Exemples:"
        echo "  $0                                    # Installation minimale"
        echo "  ./scripts/enable-extension.sh monitoring  # Ajouter le monitoring"
        exit 0
        ;;
    --version|-v)
        echo "WindFlow Installation Script v2.0 - Architecture Modulaire"
        exit 0
        ;;
    "")
        # Pas d'arguments, installation normale
        main
        ;;
    *)
        print_error "Option inconnue: $1"
        echo "Utilisez --help pour voir les options disponibles"
        exit 1
        ;;
esac
