#!/bin/bash

# ============================================================================
# WINDFLOW - INSTALLATION MINIMALE ULTRA-SIMPLE
# ============================================================================
# Script d'installation rapide pour le core minimal de WindFlow
# Version: 2.1 - Architecture Modulaire + Auto-installation prérequis
# ============================================================================

set -e  # Exit on error

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Options globales
SKIP_DOCKER_INSTALL=false

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
# DÉTECTION DE L'OS
# ============================================================================

# Variables globales remplies par detect_os()
OS_TYPE=""      # debian | ubuntu | fedora | centos | rocky | alma | arch | alpine | unknown
PKG_MANAGER=""  # apt | dnf | pacman | apk | unknown

detect_os() {
    print_info "Détection du système d'exploitation..."

    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        local id_lower
        id_lower=$(echo "${ID:-}" | tr '[:upper:]' '[:lower:]')
        local id_like_lower
        id_like_lower=$(echo "${ID_LIKE:-}" | tr '[:upper:]' '[:lower:]')

        case "$id_lower" in
            debian)
                OS_TYPE="debian"
                PKG_MANAGER="apt"
                ;;
            ubuntu)
                OS_TYPE="ubuntu"
                PKG_MANAGER="apt"
                ;;
            fedora)
                OS_TYPE="fedora"
                PKG_MANAGER="dnf"
                ;;
            centos | "centos stream")
                OS_TYPE="centos"
                PKG_MANAGER="dnf"
                ;;
            rocky)
                OS_TYPE="rocky"
                PKG_MANAGER="dnf"
                ;;
            almalinux)
                OS_TYPE="alma"
                PKG_MANAGER="dnf"
                ;;
            arch)
                OS_TYPE="arch"
                PKG_MANAGER="pacman"
                ;;
            alpine)
                OS_TYPE="alpine"
                PKG_MANAGER="apk"
                ;;
            *)
                # Fallback via ID_LIKE
                if echo "$id_like_lower" | grep -q "debian\|ubuntu"; then
                    OS_TYPE="debian"
                    PKG_MANAGER="apt"
                elif echo "$id_like_lower" | grep -q "rhel\|fedora\|centos"; then
                    OS_TYPE="centos"
                    PKG_MANAGER="dnf"
                else
                    OS_TYPE="unknown"
                    PKG_MANAGER="unknown"
                fi
                ;;
        esac
    elif command -v apt-get &>/dev/null; then
        OS_TYPE="debian"
        PKG_MANAGER="apt"
    elif command -v dnf &>/dev/null; then
        OS_TYPE="centos"
        PKG_MANAGER="dnf"
    elif command -v pacman &>/dev/null; then
        OS_TYPE="arch"
        PKG_MANAGER="pacman"
    elif command -v apk &>/dev/null; then
        OS_TYPE="alpine"
        PKG_MANAGER="apk"
    else
        OS_TYPE="unknown"
        PKG_MANAGER="unknown"
    fi

    print_success "OS détecté: ${OS_TYPE} (gestionnaire: ${PKG_MANAGER})"
}

# ============================================================================
# GESTIONNAIRES DE PAQUETS
# ============================================================================
# Chaque fonction accepte une liste de paquets en arguments.
# Usage: pkg_install_apt curl wget git
#        pkg_install_dnf curl wget git
# ============================================================================

pkg_install_apt() {
    # Installe les paquets via apt-get (Debian, Ubuntu et dérivés)
    print_info "Installation via apt: $*"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$@"
}

pkg_install_dnf() {
    # Installe les paquets via dnf (Fedora, CentOS Stream, Rocky, AlmaLinux)
    print_info "Installation via dnf: $*"
    dnf install -y -q "$@"
}

pkg_install_pacman() {
    # Installe les paquets via pacman (Arch Linux)
    print_info "Installation via pacman: $*"
    pacman -S --noconfirm --needed "$@"
}

pkg_install_apk() {
    # Installe les paquets via apk (Alpine Linux)
    print_info "Installation via apk: $*"
    apk add --no-cache "$@"
}

# Fonction générique : appelle le bon installeur selon PKG_MANAGER
pkg_install() {
    case "$PKG_MANAGER" in
        apt)    pkg_install_apt    "$@" ;;
        dnf)    pkg_install_dnf    "$@" ;;
        pacman) pkg_install_pacman "$@" ;;
        apk)    pkg_install_apk    "$@" ;;
        *)
            print_error "Gestionnaire de paquets inconnu: ${PKG_MANAGER}"
            return 1
            ;;
    esac
}

# ============================================================================
# INSTALLATION DE DOCKER
# ============================================================================

_docker_install_apt() {
    # Installation Docker sur Debian/Ubuntu via le dépôt officiel Docker
    print_info "Configuration du dépôt Docker officiel pour ${OS_TYPE}..."

    pkg_install_apt ca-certificates curl gnupg lsb-release

    # Clé GPG officielle Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${OS_TYPE}/gpg" \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Ajout du dépôt
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/${OS_TYPE} \
$(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq

    pkg_install_apt \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
}

_docker_install_dnf() {
    # Installation Docker sur Fedora/CentOS/Rocky/AlmaLinux via le dépôt officiel Docker
    print_info "Configuration du dépôt Docker officiel pour ${OS_TYPE}..."

    pkg_install_dnf dnf-plugins-core

    # Le dépôt Docker utilise "centos" comme base pour RHEL-like
    local repo_os="centos"
    if [ "$OS_TYPE" = "fedora" ]; then
        repo_os="fedora"
    fi

    dnf config-manager \
        --add-repo \
        "https://download.docker.com/linux/${repo_os}/docker-ce.repo"

    pkg_install_dnf \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
}

_docker_install_pacman() {
    # Installation Docker sur Arch Linux via les dépôts officiels
    print_info "Installation de Docker via pacman (Arch Linux)..."

    pkg_install_pacman \
        docker \
        docker-compose
}

_docker_install_apk() {
    # Installation Docker sur Alpine Linux via les dépôts community
    print_info "Installation de Docker via apk (Alpine Linux)..."

    # Activation du dépôt community si nécessaire
    if ! grep -q "community" /etc/apk/repositories 2>/dev/null; then
        local alpine_version
        alpine_version=$(cat /etc/alpine-release | cut -d. -f1-2)
        echo "https://dl-cdn.alpinelinux.org/alpine/v${alpine_version}/community" \
            >> /etc/apk/repositories
        apk update -q
    fi

    pkg_install_apk \
        docker \
        docker-cli-compose
}

install_docker() {
    # Vérifie les droits root
    if [ "$(id -u)" -ne 0 ]; then
        print_error "L'installation de Docker nécessite les droits root (sudo)"
        print_info "Relancez le script avec sudo ou installez Docker manuellement:"
        print_info "  https://docs.docker.com/engine/install/"
        exit 1
    fi

    print_info "Installation de Docker Engine..."

    case "$PKG_MANAGER" in
        apt)    _docker_install_apt    ;;
        dnf)    _docker_install_dnf    ;;
        pacman) _docker_install_pacman ;;
        apk)    _docker_install_apk    ;;
        *)
            print_error "OS non supporté pour l'installation automatique de Docker"
            print_info "Installez Docker manuellement: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac

    # Activation du service Docker
    if command -v systemctl &>/dev/null; then
        systemctl enable docker 2>/dev/null || true
        systemctl start docker  2>/dev/null || true
    elif command -v service &>/dev/null; then
        service docker start 2>/dev/null || true
    elif command -v rc-service &>/dev/null; then
        # Alpine (OpenRC)
        rc-update add docker default 2>/dev/null || true
        rc-service docker start 2>/dev/null || true
    fi

    # Ajout de l'utilisateur courant au groupe docker (si pas root)
    local current_user="${SUDO_USER:-$(whoami)}"
    if [ -n "$current_user" ] && [ "$current_user" != "root" ]; then
        usermod -aG docker "$current_user" 2>/dev/null || true
        print_warning "L'utilisateur '${current_user}' a été ajouté au groupe docker."
        print_warning "Reconnectez-vous ou exécutez 'newgrp docker' pour appliquer."
    fi

    print_success "Docker installé avec succès"
}

# ============================================================================
# VÉRIFICATIONS PRÉREQUIS
# ============================================================================

check_prerequisites() {
    print_info "Vérification des prérequis..."

    local missing_deps=()
    local need_docker=false

    # Vérifier Docker
    if ! command -v docker &>/dev/null; then
        missing_deps+=("docker")
        need_docker=true
    else
        print_success "Docker trouvé: $(docker --version | cut -d ' ' -f3 | cut -d ',' -f1)"
    fi

    # Vérifier Docker Compose (plugin intégré uniquement)
    if command -v docker &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
        if ! $need_docker; then
            missing_deps+=("docker-compose-plugin")
            need_docker=true
        fi
    elif command -v docker &>/dev/null; then
        print_success "Docker Compose trouvé: $(docker compose version --short 2>/dev/null || echo 'ok')"
    fi

    # Vérifier Git
    if ! command -v git &>/dev/null; then
        missing_deps+=("git")
    else
        print_success "Git trouvé: $(git --version | cut -d ' ' -f3)"
    fi

    # Installation automatique si des dépendances manquent
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_warning "Prérequis manquants: ${missing_deps[*]}"
        echo ""

        if $SKIP_DOCKER_INSTALL; then
            print_error "Option --skip-docker-install activée: installation automatique désactivée"
            print_info "Installez manuellement:"
            print_info "  - Docker Engine: https://docs.docker.com/engine/install/"
            print_info "  - Git: https://git-scm.com/downloads"
            exit 1
        fi

        print_info "Installation automatique des prérequis manquants..."
        echo ""

        # Détecter l'OS si pas encore fait
        if [ -z "$PKG_MANAGER" ]; then
            detect_os
        fi

        # Installer Docker si nécessaire
        if $need_docker; then
            install_docker
        fi

        # Installer Git si nécessaire
        if ! command -v git &>/dev/null; then
            print_info "Installation de Git..."
            pkg_install git
            print_success "Git installé"
        fi
    fi

    # Vérification finale
    local final_missing=()

    if ! command -v docker &>/dev/null; then
        final_missing+=("docker")
    fi

    if command -v docker &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
        final_missing+=("docker-compose-plugin")
    fi

    if ! command -v git &>/dev/null; then
        final_missing+=("git")
    fi

    if [ ${#final_missing[@]} -ne 0 ]; then
        print_error "Impossible d'installer: ${final_missing[*]}"
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
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || date +%s | sha256sum | cut -c1-64)
        # Délimiteur | : hex ne contient jamais ce caractère
        sed -i.bak "s|change-this-secret-key-in-production-use-openssl-rand-hex-32|${SECRET_KEY}|" .env
        print_success "Secret key généré automatiquement"
    fi

    # Générer des mots de passe aléatoires
    if grep -q "change-this-password" .env; then
        # hex uniquement : évite les caractères spéciaux (/, +, =) qui cassent sed
        DB_PASSWORD=$(openssl rand -hex 16 2>/dev/null || echo "windflow$(date +%s | sha256sum | cut -c1-16)")
        # Délimiteur | : hex ne contient jamais ce caractère
        sed -i.bak "s|change-this-password|${DB_PASSWORD}|g" .env
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
    print_header

    # Vérifier que nous sommes dans le bon répertoire
    if [ ! -f "docker-compose.minimal.yml" ]; then
        print_error "Fichier docker-compose.minimal.yml introuvable"
        print_info "Exécutez ce script depuis la racine du projet WindFlow"
        exit 1
    fi

    # Détecter l'OS en amont
    detect_os

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
# POINT D'ENTRÉE - Gestion des arguments
# ============================================================================

INSTALL_DIR=""
DOMAIN=""

# Parse all arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            print_header
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --help, -h                  Afficher cette aide"
            echo "  --version, -v               Afficher la version"
            echo "  --install-dir <path>        Répertoire d'installation (défaut: répertoire courant)"
            echo "  --domain <domain>           Domaine pour WindFlow (défaut: localhost)"
            echo "  --skip-docker-install       Ne pas installer Docker automatiquement"
            echo ""
            echo "Description:"
            echo "  Installe le Core Minimal de WindFlow avec les services essentiels uniquement."
            echo "  Docker Engine est installé automatiquement si absent (Debian, Ubuntu, Fedora,"
            echo "  CentOS Stream, Rocky, AlmaLinux, Arch Linux, Alpine Linux)."
            echo "  Pour ajouter des fonctionnalités avancées, utilisez le script enable-extension.sh"
            echo ""
            echo "Exemples:"
            echo "  $0                                               # Installation minimale"
            echo "  $0 --install-dir /opt/windflow --domain example.com"
            echo "  $0 --skip-docker-install                         # Docker doit être préinstallé"
            echo "  ./scripts/enable-extension.sh monitoring         # Ajouter le monitoring"
            exit 0
            ;;
        --version|-v)
            echo "WindFlow Installation Script v2.1 - Architecture Modulaire"
            exit 0
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --skip-docker-install)
            SKIP_DOCKER_INSTALL=true
            shift
            ;;
        *)
            print_error "Option inconnue: $1"
            echo "Utilisez --help pour voir les options disponibles"
            exit 1
            ;;
    esac
done

# Si un répertoire d'installation est spécifié, se déplacer dedans (ou le créer)
if [[ -n "$INSTALL_DIR" ]]; then
    print_info "Répertoire d'installation: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    # Copier les fichiers du projet si on n'est pas déjà dans le bon dossier
    if [[ "$(realpath .)" != "$(realpath "$INSTALL_DIR")" ]]; then
        cp -r . "$INSTALL_DIR/"
        cd "$INSTALL_DIR"
    fi
fi

# Si un domaine est spécifié, le stocker pour usage futur
if [[ -n "$DOMAIN" ]]; then
    print_info "Domaine configuré: $DOMAIN"
    export WINDFLOW_DOMAIN="$DOMAIN"
fi

main
