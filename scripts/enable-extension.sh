#!/bin/bash

# ============================================================================
# WINDFLOW - GESTION DES EXTENSIONS
# ============================================================================
# Script pour activer/désactiver les extensions optionnelles de WindFlow
# Version: 1.0 - Architecture Modulaire
# ============================================================================

set -e  # Exit on error

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# EXTENSIONS DISPONIBLES
# ============================================================================

declare -A EXTENSIONS=(
    ["monitoring"]="Prometheus + Grafana - Métriques et dashboards"
    ["logging"]="ELK Stack - Centralisation des logs"
    ["vault"]="HashiCorp Vault - Gestion des secrets"
    ["sso"]="Keycloak - Single Sign-On et authentification"
    ["ai"]="LiteLLM + Ollama - Intelligence artificielle"
    ["kubernetes"]="Support Kubernetes - Orchestration K8s"
    ["swarm"]="Docker Swarm - Orchestration en cluster"
)

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              WINDFLOW - GESTION DES EXTENSIONS                 ║"
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
# FONCTIONS PRINCIPALES
# ============================================================================

list_extensions() {
    print_header
    echo -e "${CYAN}Extensions disponibles:${NC}"
    echo ""

    for ext in "${!EXTENSIONS[@]}" | sort; do
        local status="❌ Désactivée"

        # Vérifier si l'extension est activée dans .env
        if [ -f .env ] && grep -q "ENABLE_$(echo "$ext" | tr '[:lower:]' '[:upper:]')=true" .env 2>/dev/null; then
            status="✅ Activée"
        fi

        printf "  %-15s : %s\n" "$ext" "${EXTENSIONS[$ext]}"
        printf "  %-15s   %s\n" "" "$status"
        echo ""
    done

    echo -e "${CYAN}Ressources requises par extension:${NC}"
    echo ""
    echo "  monitoring    : +500 MB RAM, +0.5 CPU"
    echo "  logging       : +2 GB RAM, +1 CPU"
    echo "  vault         : +256 MB RAM, +0.2 CPU"
    echo "  sso           : +800 MB RAM, +0.5 CPU"
    echo "  ai            : +128 MB RAM (LiteLLM) | +8 GB RAM (Ollama avec modèle)"
    echo "  kubernetes    : Variable selon cluster"
    echo "  swarm         : Minimal"
    echo ""
}

enable_extension() {
    local extension=$1

    # Vérifier que l'extension existe
    if [[ ! -v EXTENSIONS[$extension] ]]; then
        print_error "Extension inconnue: $extension"
        echo ""
        print_info "Extensions disponibles: ${!EXTENSIONS[*]}"
        print_info "Utilisez --list pour voir tous les détails"
        exit 1
    fi

    print_header
    print_info "Activation de l'extension: $extension"
    echo "Description: ${EXTENSIONS[$extension]}"
    echo ""

    # Vérifier le fichier .env
    if [ ! -f .env ]; then
        print_error "Fichier .env introuvable"
        print_info "Exécutez d'abord: ./scripts/install.sh"
        exit 1
    fi

    # Activer l'extension dans .env
    local env_var="ENABLE_$(echo "$extension" | tr '[:lower:]' '[:upper:]')"

    if grep -q "$env_var=true" .env 2>/dev/null; then
        print_warning "L'extension $extension est déjà activée"
    else
        # Mettre à jour .env
        if grep -q "$env_var=" .env 2>/dev/null; then
            sed -i.bak "s/$env_var=false/$env_var=true/" .env
        else
            echo "$env_var=true" >> .env
        fi
        print_success "Extension $extension activée dans .env"
        rm -f .env.bak
    fi

    # Démarrer les services de l'extension
    case $extension in
        monitoring)
            enable_monitoring
            ;;
        logging)
            enable_logging
            ;;
        vault)
            enable_vault
            ;;
        sso)
            enable_sso
            ;;
        ai)
            enable_ai
            ;;
        kubernetes)
            enable_kubernetes
            ;;
        swarm)
            enable_swarm
            ;;
    esac

    echo ""
    print_success "Extension $extension activée avec succès!"
    echo ""
}

disable_extension() {
    local extension=$1

    # Vérifier que l'extension existe
    if [[ ! -v EXTENSIONS[$extension] ]]; then
        print_error "Extension inconnue: $extension"
        exit 1
    fi

    print_header
    print_info "Désactivation de l'extension: $extension"
    echo ""

    # Désactiver dans .env
    local env_var="ENABLE_$(echo "$extension" | tr '[:lower:]' '[:upper:]')"

    if grep -q "$env_var=true" .env 2>/dev/null; then
        sed -i.bak "s/$env_var=true/$env_var=false/" .env
        print_success "Extension $extension désactivée dans .env"
        rm -f .env.bak
    else
        print_warning "L'extension $extension est déjà désactivée"
    fi

    # Arrêter les services
    print_info "Arrêt des services de l'extension..."
    docker compose --profile "$extension" down 2>/dev/null || true

    echo ""
    print_success "Extension $extension désactivée avec succès!"
    echo ""
}

# ============================================================================
# FONCTIONS D'ACTIVATION PAR EXTENSION
# ============================================================================

enable_monitoring() {
    print_info "Démarrage des services de monitoring..."

    if docker compose -f docker-compose.yml -f docker-compose.extensions.yml --profile monitoring up -d; then
        print_success "Services de monitoring démarrés"
        echo ""
        print_info "Accès:"
        echo "  • Prometheus : http://localhost:9090"
        echo "  • Grafana    : http://localhost:3000 (admin/admin)"
    else
        print_error "Échec du démarrage des services de monitoring"
        exit 1
    fi
}

enable_logging() {
    print_info "Démarrage de l'ELK Stack..."
    print_warning "Cela peut prendre plusieurs minutes..."

    if docker compose -f docker-compose.yml -f docker-compose.extensions.yml --profile logging up -d; then
        print_success "ELK Stack démarrée"
        echo ""
        print_info "Accès:"
        echo "  • Kibana         : http://localhost:5601"
        echo "  • Elasticsearch  : http://localhost:9200"
    else
        print_error "Échec du démarrage de l'ELK Stack"
        exit 1
    fi
}

enable_vault() {
    print_info "Démarrage de HashiCorp Vault..."

    if docker compose -f docker-compose.yml -f docker-compose.extensions.yml --profile vault up -d; then
        print_success "Vault démarré"
        echo ""
        print_warning "Vault nécessite une initialisation:"
        echo "  docker compose exec vault vault operator init"
        echo "  docker compose exec vault vault operator unseal"
        echo ""
        print_info "Accès:"
        echo "  • Vault UI : http://localhost:8200"
    else
        print_error "Échec du démarrage de Vault"
        exit 1
    fi
}

enable_sso() {
    print_info "Démarrage de Keycloak..."
    print_warning "Cela peut prendre quelques minutes..."

    if docker compose -f docker-compose.yml -f docker-compose.extensions.yml --profile sso up -d; then
        print_success "Keycloak démarré"
        echo ""
        print_info "Accès:"
        echo "  • Keycloak Admin : http://localhost:8180/admin"
        echo "  • Credentials    : Voir variables KEYCLOAK_ADMIN_* dans .env"
    else
        print_error "Échec du démarrage de Keycloak"
        exit 1
    fi
}

enable_ai() {
    print_info "Démarrage des services IA..."

    if docker compose -f docker-compose.yml -f docker-compose.extensions.yml --profile ai up -d; then
        print_success "Services IA démarrés"
        echo ""
        print_info "Accès:"
        echo "  • LiteLLM : http://localhost:4000"
        echo "  • Ollama  : http://localhost:11434"
        echo ""
        print_info "Configuration:"
        echo "  Configurez LLM_PROVIDER et clés API dans .env"
    else
        print_error "Échec du démarrage des services IA"
        exit 1
    fi
}

enable_kubernetes() {
    print_info "Activation du support Kubernetes..."
    print_warning "Cette extension nécessite un cluster Kubernetes existant"
    echo ""
    print_info "Configuration requise:"
    echo "  1. kubectl installé et configuré"
    echo "  2. Helm 3 installé"
    echo "  3. Cluster Kubernetes accessible"
    echo ""
    print_info "Installation des charts Helm:"
    echo "  helm install windflow ./infrastructure/helm/windflow"
}

enable_swarm() {
    print_info "Activation du support Docker Swarm..."
    print_warning "Cette extension nécessite un cluster Swarm initialisé"
    echo ""
    print_info "Initialisation Swarm (si nécessaire):"
    echo "  docker swarm init"
    echo ""
    print_info "Déploiement sur Swarm:"
    echo "  docker stack deploy -c docker-compose.yml windflow"
}

# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

show_usage() {
    print_header
    echo "Usage: $0 <extension> [--disable] | [--list] | [--help]"
    echo ""
    echo "Actions:"
    echo "  <extension>        Activer une extension"
    echo "  --list, -l         Lister toutes les extensions disponibles"
    echo "  --disable <ext>    Désactiver une extension"
    echo "  --help, -h         Afficher cette aide"
    echo ""
    echo "Extensions disponibles:"
    for ext in "${!EXTENSIONS[@]}" | sort; do
        printf "  %-15s : %s\n" "$ext" "${EXTENSIONS[$ext]}"
    done
    echo ""
    echo "Exemples:"
    echo "  $0 monitoring              # Activer le monitoring"
    echo "  $0 --disable logging       # Désactiver les logs"
    echo "  $0 --list                  # Voir toutes les extensions"
    echo ""
}

main() {
    # Vérifier qu'on est dans le bon répertoire
    if [ ! -f "docker-compose.yml" ]; then
        print_error "Fichier docker-compose.yml introuvable"
        print_info "Exécutez ce script depuis la racine du projet WindFlow"
        exit 1
    fi

    case "${1:-}" in
        --list|-l)
            list_extensions
            ;;
        --disable)
            if [ -z "${2:-}" ]; then
                print_error "Extension non spécifiée"
                show_usage
                exit 1
            fi
            disable_extension "$2"
            ;;
        --help|-h)
            show_usage
            ;;
        "")
            print_error "Aucune action spécifiée"
            show_usage
            exit 1
            ;;
        *)
            enable_extension "$1"
            ;;
    esac
}

# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

main "$@"
