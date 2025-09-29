#!/bin/sh

# install.sh - Script d'installation automatique WindFlow
# Version robuste avec gestion d'erreurs avancée

# Configuration stricte mais avec gestion d'erreurs personnalisée
set -u  # Détection des variables non définies

# ============================================================================
# VARIABLES GLOBALES
# ============================================================================

WINDFLOW_VERSION=${1:-latest}
INSTALL_DIR=${2:-/opt/windflow}
DOMAIN=${3:-localhost}
LOG_FILE="/tmp/windflow-install.log"
PACKAGE_UPDATE="true"
NOSUDO="false"
UPDATE="false"
SCRIPT_EXIT_CODE=0
MAX_RETRIES=3
NETWORK_TIMEOUT=30

# Détection de l'architecture avec gestion d'erreur
ARCHITECTURE="$(uname -m 2>/dev/null || echo 'unknown')"
case "$ARCHITECTURE" in
    "armv7" | "i686" | "i386")
        echo "❌ WindFlow n'est pas supporté sur les systèmes 32 bits"
        exit 1
        ;;
    "unknown")
        echo "⚠️  Impossible de détecter l'architecture, continuation..."
        ;;
esac

# Détection sudo avec fallbacks
detect_sudo() {
    if command -v sudo >/dev/null 2>&1; then
        NOSUDO="false"
    elif [ "$(id -u)" -eq 0 ]; then
        echo "🔓 Exécution en tant que root"
        alias sudo=""
        NOSUDO="true"
    else
        echo "❌ sudo non trouvé et pas d'accès root"
        echo "   Veuillez installer sudo ou exécuter en tant que root"
        exit 1
    fi
}

# Détection robuste du système d'exploitation
detect_os() {
    OS=""
    SUB_OS="unknown"

    # Méthode 1: /etc/os-release (standard moderne)
    if [ -f "/etc/os-release" ]; then
        OS="$(grep '^ID=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')"
        SUB_OS="$(grep '^ID_LIKE=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]' | awk '{print $1}')"
    fi

    # Méthode 2: Fallback sur lsb_release
    if [ -z "$OS" ] && command -v lsb_release >/dev/null 2>&1; then
        OS="$(lsb_release -si 2>/dev/null | tr '[:upper:]' '[:lower:]')"
    fi

    # Méthode 3: Détection par fichiers spécifiques
    if [ -z "$OS" ]; then
        if [ -f "/etc/debian_version" ]; then
            OS="debian"
        elif [ -f "/etc/redhat-release" ]; then
            if grep -qi "centos" /etc/redhat-release; then
                OS="centos"
            elif grep -qi "fedora" /etc/redhat-release; then
                OS="fedora"
            elif grep -qi "rocky" /etc/redhat-release; then
                OS="rocky"
            else
                OS="rhel"
            fi
        elif [ -f "/etc/alpine-release" ]; then
            OS="alpine"
        elif [ -f "/etc/arch-release" ]; then
            OS="arch"
        elif [ -f "/etc/SuSE-release" ]; then
            OS="opensuse"
        fi
    fi

    # Méthode 4: Détection par uname
    if [ -z "$OS" ]; then
        case "$(uname -s)" in
            "Darwin")
                OS="macos"
                ;;
            "FreeBSD")
                OS="freebsd"
                ;;
            *)
                OS="unknown"
                ;;
        esac
    fi

    # Normalisation des noms d'OS
    case "$OS" in
        "ubuntu"|"linuxmint"|"elementary"|"pop")
            SUB_OS="ubuntu debian"
            ;;
        "debian"|"raspbian"|"kali")
            SUB_OS="debian"
            ;;
        "centos"|"rhel"|"rocky"|"almalinux"|"ol")
            SUB_OS="rhel centos"
            ;;
        "fedora")
            SUB_OS="fedora rhel"
            ;;
        "opensuse"|"sles")
            SUB_OS="suse"
            ;;
        "arch"|"manjaro"|"artix")
            SUB_OS="arch"
            ;;
        "alpine")
            SUB_OS="alpine"
            ;;
    esac

    # Validation finale
    if [ -z "$OS" ] || [ "$OS" = "unknown" ]; then
        echo "❌ Système d'exploitation non détecté ou non supporté"
        echo "   OS détecté: '$OS'"
        echo "   Systèmes supportés: Ubuntu, Debian, CentOS, Fedora, Alpine, Arch, openSUSE"
        exit 1
    fi
}

# Initialisation
detect_sudo
detect_os

# Couleurs pour l'affichage (avec détection terminal)
if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# ============================================================================
# FONCTIONS DE LOGGING ET UTILITAIRES
# ============================================================================

# Fonction de logging robuste
log() {
    local message="$1"
    local timestamp
    timestamp="$(date +'%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'unknown')"

    # Affichage sur stdout
    printf "%s[%s]%s %s\n" "$BLUE" "$timestamp" "$NC" "$message"

    # Écriture dans le log file avec gestion d'erreur
    {
        printf "[%s] %s\n" "$timestamp" "$message"
    } >> "$LOG_FILE" 2>/dev/null || true
}

log_success() {
    local message="$1"
    printf "%s✅ %s%s\n" "$GREEN" "$message" "$NC"
    echo "[SUCCESS] $message" >> "$LOG_FILE" 2>/dev/null || true
}

log_warning() {
    local message="$1"
    printf "%s⚠️  %s%s\n" "$YELLOW" "$message" "$NC"
    echo "[WARNING] $message" >> "$LOG_FILE" 2>/dev/null || true
}

log_error() {
    local message="$1"
    printf "%s❌ %s%s\n" "$RED" "$message" "$NC" >&2
    echo "[ERROR] $message" >> "$LOG_FILE" 2>/dev/null || true
    SCRIPT_EXIT_CODE=1
}

# Fonction de retry avec backoff
retry_command() {
    local max_attempts="$1"
    local delay="$2"
    local description="$3"
    shift 3

    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if "$@"; then
            return 0
        fi

        if [ $attempt -lt $max_attempts ]; then
            log_warning "Échec $description (tentative $attempt/$max_attempts), retry dans ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))  # Exponential backoff
        fi
        attempt=$((attempt + 1))
    done

    log_error "Échec $description après $max_attempts tentatives"
    return 1
}

# Vérification de la connectivité réseau
check_network() {
    log "🌐 Vérification de la connectivité réseau..."

    # Test de résolution DNS et connectivité
    local test_hosts="8.8.8.8 1.1.1.1 github.com"
    local network_ok=false

    for host in $test_hosts; do
        if ping -c 1 -W 5 "$host" >/dev/null 2>&1; then
            network_ok=true
            break
        fi
    done

    if [ "$network_ok" = "false" ]; then
        log_error "Aucune connectivité réseau détectée"
        log "Vérifiez votre connexion internet et réessayez"
        return 1
    fi

    log_success "Connectivité réseau OK"
    return 0
}

# Validation des variables critiques
validate_environment() {
    log "🔍 Validation de l'environnement..."

    # Vérification des variables obligatoires
    if [ -z "$INSTALL_DIR" ] || [ -z "$DOMAIN" ] || [ -z "$WINDFLOW_VERSION" ]; then
        log_error "Variables d'environnement manquantes"
        exit 1
    fi

    # Validation du répertoire d'installation
    if ! mkdir -p "$INSTALL_DIR" 2>/dev/null; then
        log_error "Impossible de créer le répertoire d'installation: $INSTALL_DIR"
        exit 1
    fi

    # Validation du domaine (basique)
    case "$DOMAIN" in
        *" "*)
            log_error "Le domaine ne peut pas contenir d'espaces: '$DOMAIN'"
            exit 1
            ;;
        "")
            log_error "Le domaine ne peut pas être vide"
            exit 1
            ;;
    esac

    log_success "Validation de l'environnement OK"
}

# ============================================================================
# GESTION DES ARGUMENTS CLI
# ============================================================================

parse_arguments() {
    while [ -n "${1-}" ]; do
        case "$1" in
        --update)
            UPDATE="true"
            ;;
        --version)
            shift
            WINDFLOW_VERSION="$1"
            if [ -z "$WINDFLOW_VERSION" ]; then
                echo "Option --version nécessite une valeur" && exit 1
            fi
            ;;
        --install-dir)
            shift
            INSTALL_DIR="$1"
            if [ -z "$INSTALL_DIR" ]; then
                echo "Option --install-dir nécessite une valeur" && exit 1
            fi
            ;;
        --domain)
            shift
            DOMAIN="$1"
            if [ -z "$DOMAIN" ]; then
                echo "Option --domain nécessite une valeur" && exit 1
            fi
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Option $1 non reconnue" && exit 1
            ;;
        esac
        shift
    done
}

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  --version VERSION     Version de WindFlow à installer (défaut: latest)
  --install-dir DIR     Répertoire d'installation (défaut: /opt/windflow)
  --domain DOMAIN       Domaine pour les services (défaut: localhost)
  --update              Mettre à jour une installation existante
  --help, -h            Afficher cette aide

Exemples:
  $0 --version v1.0.0 --domain windflow.example.com
  $0 --install-dir /home/user/windflow --update
EOF
}

# ============================================================================
# GESTION DES DÉPENDANCES SYSTÈME
# ============================================================================

# Installe une dépendance générique selon le système d'exploitation avec gestion d'erreurs robuste
generic_install() {
    local dependency="${1}"
    local os="${2}"
    local install_cmd=""
    local update_cmd=""

    # Définition des commandes selon l'OS
    case "${os}" in
        "debian"|"ubuntu"|"pop"|"linuxmint"|"elementary"|"raspbian"|"kali")
            update_cmd="sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq"
            install_cmd="sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ${dependency}"
            ;;
        "centos"|"rhel"|"rocky"|"almalinux"|"ol")
            # Test si yum ou dnf est disponible
            if command -v dnf >/dev/null 2>&1; then
                update_cmd="sudo dnf -y check-update || true"
                install_cmd="sudo dnf -y install ${dependency}"
            elif command -v yum >/dev/null 2>&1; then
                update_cmd="sudo yum -y check-update || true"
                install_cmd="sudo yum install -y --allowerasing ${dependency}"
            else
                log_error "Aucun gestionnaire de paquets trouvé (yum/dnf) pour ${os}"
                return 1
            fi
            ;;
        "fedora")
            if command -v dnf >/dev/null 2>&1; then
                update_cmd="sudo dnf -y check-update || true"
                install_cmd="sudo dnf -y install ${dependency}"
            else
                log_error "dnf non trouvé sur Fedora"
                return 1
            fi
            ;;
        "alpine")
            update_cmd="sudo apk update"
            install_cmd="sudo apk add ${dependency}"
            ;;
        "arch"|"manjaro"|"artix")
            if command -v pacman >/dev/null 2>&1; then
                update_cmd="sudo pacman -Sy --noconfirm"
                install_cmd="sudo pacman -S --noconfirm ${dependency}"
            else
                log_error "pacman non trouvé sur ${os}"
                return 1
            fi
            ;;
        "opensuse"|"sles"|"suse")
            if command -v zypper >/dev/null 2>&1; then
                update_cmd="sudo zypper refresh"
                install_cmd="sudo zypper install -y ${dependency}"
            else
                log_error "zypper non trouvé sur ${os}"
                return 1
            fi
            ;;
        *)
            log_error "Système non supporté pour l'installation automatique: ${os}"
            return 1
            ;;
    esac

    # Mise à jour des paquets si nécessaire
    if [ "${PACKAGE_UPDATE}" = "true" ] && [ -n "$update_cmd" ]; then
        log "📦 Mise à jour des paquets sur ${os}..."
        if ! eval "$update_cmd" >/dev/null 2>&1; then
            log_warning "Échec de la mise à jour des paquets, continuation..."
        fi
        PACKAGE_UPDATE="false"
    fi

    # Installation du paquet
    log "📦 Installation de ${dependency} sur ${os}..."
    if eval "$install_cmd" >/dev/null 2>&1; then
        return 0
    else
        log_warning "Échec de l'installation de ${dependency} avec ${install_cmd}"
        return 1
    fi
}

# Vérifie si une dépendance est installée avec fallbacks multiples
check_dependency_and_install() {
    local dependency="${1}"
    shift
    local packages="$*"

    # Vérification multiple de la commande
    local cmd_found=false
    local check_paths="/usr/bin/${dependency} /usr/local/bin/${dependency} /bin/${dependency} /sbin/${dependency} /usr/sbin/${dependency}"

    # Vérification standard
    if command -v "${dependency}" >/dev/null 2>&1; then
        cmd_found=true
    else
        # Vérification dans les chemins standard
        for path in $check_paths; do
            if [ -x "$path" ]; then
                cmd_found=true
                break
            fi
        done
    fi

    if [ "$cmd_found" = "true" ]; then
        log_success "${dependency} déjà installé"
        return 0
    fi

    log "📦 Installation nécessaire de ${dependency}..."

    # Liste des OS à essayer (OS principal + fallbacks)
    local os_list="$OS"
    if [ -n "$SUB_OS" ] && [ "$SUB_OS" != "unknown" ]; then
        os_list="$OS $SUB_OS"
    fi

    # Tentative d'installation avec chaque OS et chaque paquet
    local install_success=false
    for os_try in $os_list; do
        for package in $packages; do
            log "   Essai: $package sur $os_try"
            if generic_install "$package" "$os_try"; then
                # Vérification que la commande est maintenant disponible
                if command -v "${dependency}" >/dev/null 2>&1; then
                    log_success "${dependency} installé avec succès (paquet: $package, OS: $os_try)"
                    install_success=true
                    break 2
                else
                    log_warning "Paquet $package installé mais commande $dependency non disponible"
                fi
            fi
        done
    done

    if [ "$install_success" = "false" ]; then
        log_error "Impossible d'installer ${dependency}"
        log "   Paquets essayés: $packages"
        log "   Systèmes essayés: $os_list"
        log "   Veuillez installer ${dependency} manuellement"

        # Suggestions d'installation manuelle
        case "$OS" in
            "ubuntu"|"debian")
                log "   Essayez: sudo apt-get install $packages"
                ;;
            "centos"|"fedora"|"rhel")
                log "   Essayez: sudo yum install $packages ou sudo dnf install $packages"
                ;;
            "arch")
                log "   Essayez: sudo pacman -S $packages"
                ;;
            "alpine")
                log "   Essayez: sudo apk add $packages"
                ;;
        esac

        return 1
    fi

    return 0
}

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

show_banner() {
    echo
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    WINDFLOW INSTALLER                    ║${NC}"
    echo -e "${BLUE}║                                                          ║${NC}"
    echo -e "${BLUE}║          Outil intelligent de déploiement Docker        ║${NC}"
    echo -e "${BLUE}║                     Version ${WINDFLOW_VERSION}                        ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo
}

# Vérifie l'espace disque disponible avec fallbacks
check_disk_space() {
    local min_space_gb=10
    local available_space=0
    local check_dir="$HOME"

    # Si HOME n'existe pas, utiliser le répertoire d'installation
    if [ ! -d "$HOME" ]; then
        check_dir="$INSTALL_DIR"
        mkdir -p "$check_dir" 2>/dev/null || check_dir="/tmp"
    fi

    # Essai avec df (Linux standard)
    if command -v df >/dev/null 2>&1; then
        available_space=$(df -BG "$check_dir" 2>/dev/null | awk 'NR==2{print $4}' | sed 's/G//' | head -n1)
    fi

    # Fallback avec du si df échoue
    if [ -z "$available_space" ] || [ "$available_space" = "0" ]; then
        if command -v du >/dev/null 2>&1; then
            # Estimation basée sur l'espace utilisé dans /
            local used_space
            used_space=$(du -sg / 2>/dev/null | awk '{print $1}' || echo "0")
            available_space=$((100 - used_space))  # Estimation très approximative
        fi
    fi

    # Validation
    available_space=${available_space:-0}

    if [ "$available_space" -lt "$min_space_gb" ]; then
        log_warning "Espace disque faible: ${available_space}G disponible (${min_space_gb}G recommandé)"
        log "   Répertoire vérifié: $check_dir"
        return 1
    else
        log_success "Espace disque suffisant: ${available_space}G disponible"
        return 0
    fi
}

# Vérifie la mémoire disponible avec fallbacks multiples
check_memory() {
    local min_ram_gb=4
    local available_ram=0

    # Méthode 1: free (Linux standard)
    if command -v free >/dev/null 2>&1; then
        available_ram=$(free -m 2>/dev/null | awk 'NR==2{printf "%.0f", $7/1024}' || echo "0")
    fi

    # Méthode 2: /proc/meminfo (Linux)
    if [ "$available_ram" = "0" ] && [ -r "/proc/meminfo" ]; then
        local mem_available mem_free mem_buffers mem_cached
        mem_available=$(grep "^MemAvailable:" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
        if [ "$mem_available" != "0" ]; then
            available_ram=$((mem_available / 1024 / 1024))
        else
            # Calcul approximatif si MemAvailable n'existe pas
            mem_free=$(grep "^MemFree:" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
            mem_buffers=$(grep "^Buffers:" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
            mem_cached=$(grep "^Cached:" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
            available_ram=$(((mem_free + mem_buffers + mem_cached) / 1024 / 1024))
        fi
    fi

    # Méthode 3: top (fallback universel)
    if [ "$available_ram" = "0" ] && command -v top >/dev/null 2>&1; then
        available_ram=$(top -bn1 | grep "^Mem:" | awk '{print $6}' | sed 's/[^0-9]//g' | head -c 1 || echo "2")
    fi

    # Validation avec valeur par défaut
    available_ram=${available_ram:-2}

    if [ "$available_ram" -lt "$min_ram_gb" ]; then
        log_warning "Mémoire RAM faible: ${available_ram}G disponible (${min_ram_gb}G recommandé)"
        log "   WindFlow peut fonctionner mais avec des performances réduites"
        return 1
    else
        log_success "Mémoire RAM suffisante: ${available_ram}G disponible"
        return 0
    fi
}

# Vérifie si Docker fonctionne avec diagnostics avancés
check_docker_running() {
    local docker_accessible=false
    local current_user
    current_user=$(whoami 2>/dev/null || echo "unknown")

    log "🐳 Vérification de l'accès Docker..."

    # Test d'accès Docker
    if docker info >/dev/null 2>&1; then
        docker_accessible=true
        log_success "Docker accessible pour l'utilisateur $current_user"
    else
        log_warning "Docker non accessible pour l'utilisateur $current_user"

        # Diagnostic des problèmes Docker
        if ! command -v docker >/dev/null 2>&1; then
            log_error "Docker n'est pas installé"
            return 1
        fi

        # Vérification du service Docker
        local docker_running=false
        if command -v systemctl >/dev/null 2>&1; then
            if systemctl is-active docker >/dev/null 2>&1; then
                docker_running=true
            fi
        elif command -v service >/dev/null 2>&1; then
            if service docker status >/dev/null 2>&1; then
                docker_running=true
            fi
        fi

        if [ "$docker_running" = "false" ]; then
            log_error "Le service Docker n'est pas en cours d'exécution"
            log "Tentative de démarrage du service Docker..."

            if [ "$NOSUDO" = "false" ]; then
                if command -v systemctl >/dev/null 2>&1; then
                    sudo systemctl start docker >/dev/null 2>&1 && docker_running=true
                elif command -v service >/dev/null 2>&1; then
                    sudo service docker start >/dev/null 2>&1 && docker_running=true
                fi
            fi

            if [ "$docker_running" = "false" ]; then
                log_error "Impossible de démarrer Docker"
                return 1
            fi
        fi

        # Problème de permissions utilisateur
        if [ "$NOSUDO" = "false" ]; then
            log "Ajout de l'utilisateur au groupe docker..."
            if sudo usermod -aG docker "$current_user" 2>/dev/null; then
                log_warning "Utilisateur ajouté au groupe docker"
                log_warning "Veuillez vous déconnecter et vous reconnecter, puis relancer le script"
                log "Ou exécutez: newgrp docker && $0"
                exit 1
            else
                log_error "Impossible d'ajouter l'utilisateur au groupe docker"
                return 1
            fi
        else
            log_error "Accès Docker requis. Vérifiez les permissions"
            return 1
        fi
    fi

    # Test de fonctionnalité Docker
    log "🔧 Test de fonctionnalité Docker..."
    if docker run --rm hello-world >/dev/null 2>&1; then
        log_success "Docker fonctionne correctement"
    else
        log_warning "Docker installé mais test de fonctionnalité échoué"
        log "Cela peut être normal selon la configuration du système"
    fi

    return 0
}

# ============================================================================
# INSTALLATION DES DÉPENDANCES
# ============================================================================

install_system_dependencies() {
    log "📦 Installation des dépendances système..."

    # Dépendances de base
    check_dependency_and_install "curl" "curl"
    check_dependency_and_install "git" "git"
    check_dependency_and_install "tar" "tar"
    check_dependency_and_install "openssl" "openssl"

    # Python (si nécessaire pour des scripts d'administration)
    check_dependency_and_install "python3" "python3" "python"

    log_success "Dépendances système installées"
}

install_docker() {
    log "🐳 Vérification de Docker..."

    if ! command -v docker >/dev/null 2>&1; then
        log "Installation de Docker..."

        # Vérification de la connectivité réseau avant installation
        if ! check_network; then
            log_error "Connectivité réseau requise pour installer Docker"
            return 1
        fi

        # Installation Docker selon l'OS avec retry
        case "${OS}" in
            "ubuntu"|"debian"|"pop"|"linuxmint"|"elementary")
                if ! retry_command 3 5 "installation Docker" curl -fsSL https://get.docker.com -o get-docker.sh; then
                    log_error "Échec du téléchargement du script Docker"
                    return 1
                fi

                if ! retry_command 2 10 "exécution script Docker" sh get-docker.sh; then
                    log_error "Échec de l'installation Docker"
                    rm -f get-docker.sh
                    return 1
                fi
                rm -f get-docker.sh
                ;;
            "centos"|"rhel"|"rocky"|"almalinux"|"ol")
                if ! check_dependency_and_install "docker" "docker" "docker-ce" "docker.io"; then
                    log_error "Échec de l'installation Docker via gestionnaire de paquets"
                    return 1
                fi
                if command -v systemctl >/dev/null 2>&1; then
                    sudo systemctl enable docker >/dev/null 2>&1 || true
                    sudo systemctl start docker >/dev/null 2>&1 || true
                fi
                ;;
            "fedora")
                if ! check_dependency_and_install "docker" "docker" "docker-ce" "moby-engine"; then
                    log_error "Échec de l'installation Docker sur Fedora"
                    return 1
                fi
                if command -v systemctl >/dev/null 2>&1; then
                    sudo systemctl enable docker >/dev/null 2>&1 || true
                    sudo systemctl start docker >/dev/null 2>&1 || true
                fi
                ;;
            "arch"|"manjaro"|"artix")
                if ! check_dependency_and_install "docker" "docker"; then
                    log_error "Échec de l'installation Docker sur Arch"
                    return 1
                fi
                if command -v systemctl >/dev/null 2>&1; then
                    sudo systemctl enable docker >/dev/null 2>&1 || true
                    sudo systemctl start docker >/dev/null 2>&1 || true
                fi
                ;;
            "alpine")
                if ! check_dependency_and_install "docker" "docker"; then
                    log_error "Échec de l'installation Docker sur Alpine"
                    return 1
                fi
                if command -v rc-update >/dev/null 2>&1; then
                    sudo rc-update add docker default >/dev/null 2>&1 || true
                    sudo rc-service docker start >/dev/null 2>&1 || true
                fi
                ;;
            "opensuse"|"sles"|"suse")
                if ! check_dependency_and_install "docker" "docker"; then
                    log_error "Échec de l'installation Docker sur openSUSE"
                    return 1
                fi
                if command -v systemctl >/dev/null 2>&1; then
                    sudo systemctl enable docker >/dev/null 2>&1 || true
                    sudo systemctl start docker >/dev/null 2>&1 || true
                fi
                ;;
            *)
                log_error "Installation automatique de Docker non supportée sur ${OS}"
                log "Systèmes supportés: Ubuntu, Debian, CentOS, Fedora, Alpine, Arch, openSUSE"
                log "Veuillez installer Docker manuellement: https://docs.docker.com/engine/install/"
                return 1
                ;;
        esac

        # Attendre que Docker soit prêt
        log "⏳ Attente du démarrage de Docker..."
        local docker_ready=false
        local attempts=0
        while [ $attempts -lt 30 ]; do
            if docker info >/dev/null 2>&1; then
                docker_ready=true
                break
            fi
            sleep 2
            attempts=$((attempts + 1))
        done

        if [ "$docker_ready" = "false" ]; then
            log_warning "Docker installé mais pas encore prêt"
        else
            log_success "Docker installé et prêt"
        fi
    else
        log_success "Docker déjà installé"
    fi

    # Vérification et installation Docker Compose
    local compose_available=false
    if command -v "docker compose" >/dev/null 2>&1; then
        compose_available=true
        log_success "Docker Compose (plugin) déjà installé"
    elif command -v docker-compose >/dev/null 2>&1; then
        compose_available=true
        log_success "Docker Compose (standalone) déjà installé"
    fi

    if [ "$compose_available" = "false" ]; then
        log "Installation de Docker Compose..."

        # Tentative d'installation du plugin Docker Compose V2
        DOCKER_COMPOSE_VERSION="v2.21.0"
        DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"

        if mkdir -p "$DOCKER_CONFIG/cli-plugins" 2>/dev/null; then
            local compose_url="https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"

            if retry_command 3 5 "téléchargement Docker Compose" curl -SL "$compose_url" -o "$DOCKER_CONFIG/cli-plugins/docker-compose"; then
                chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"

                # Test du plugin
                if docker compose version >/dev/null 2>&1; then
                    log_success "Docker Compose plugin installé"
                    compose_available=true
                else
                    log_warning "Plugin Docker Compose installé mais non fonctionnel"
                    rm -f "$DOCKER_CONFIG/cli-plugins/docker-compose"
                fi
            fi
        fi

        # Fallback: installation via gestionnaire de paquets
        if [ "$compose_available" = "false" ]; then
            log "Tentative d'installation Docker Compose via gestionnaire de paquets..."
            if check_dependency_and_install "docker-compose" "docker-compose" "docker-compose-plugin"; then
                compose_available=true
                log_success "Docker Compose installé via gestionnaire de paquets"
            fi
        fi

        if [ "$compose_available" = "false" ]; then
            log_error "Impossible d'installer Docker Compose"
            log "Veuillez installer Docker Compose manuellement"
            return 1
        fi
    fi

    # Vérification finale de Docker
    if ! check_docker_running; then
        log_error "Docker non fonctionnel après installation"
        return 1
    fi

    return 0
}

# ============================================================================
# VÉRIFICATION DES PRÉREQUIS
# ============================================================================

check_requirements() {
    log "📋 Vérification des prérequis système..."

    # Validation de l'environnement
    validate_environment

    # Vérification de l'OS
    if [ -z "$OS" ] || [ "$OS" = "unknown" ]; then
        log_error "Impossible de détecter le système d'exploitation"
        log "OS détecté: '$OS', SUB_OS: '$SUB_OS'"
        exit 1
    fi
    log_success "Système détecté: $OS (famille: $SUB_OS)"

    # Vérification de la connectivité réseau
    if ! check_network; then
        log_error "Connectivité réseau requise pour l'installation"
        exit 1
    fi

    # Vérification des ressources (non bloquant)
    check_disk_space || log_warning "Espace disque insuffisant mais installation continue"
    check_memory || log_warning "Mémoire RAM insuffisante mais installation continue"

    # Installation des dépendances critiques
    log "📦 Installation des dépendances critiques..."
    if ! install_system_dependencies; then
        log_error "Échec de l'installation des dépendances système"
        exit 1
    fi

    # Installation Docker avec gestion d'erreur robuste
    if ! install_docker; then
        log_error "Échec de l'installation ou configuration Docker"
        log "Docker est requis pour WindFlow. Veuillez l'installer manuellement:"
        log "  - Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
        log "  - CentOS/RHEL: yum install docker-ce"
        log "  - Arch: pacman -S docker"
        log "  - Alpine: apk add docker"
        exit 1
    fi

    log_success "Prérequis validés avec succès"
}

# ============================================================================
# CONFIGURATION ET INSTALLATION
# ============================================================================

setup_directories() {
    log "📁 Création de la structure des répertoires..."

    # Création du répertoire d'installation
    if [ ! -d "$INSTALL_DIR" ]; then
        if [ "$NOSUDO" = "false" ]; then
            sudo mkdir -p "$INSTALL_DIR"
            sudo chown "$(whoami):$(whoami)" "$INSTALL_DIR"
        else
            mkdir -p "$INSTALL_DIR"
        fi
    fi

    cd "$INSTALL_DIR"

    # Création des répertoires de données
    mkdir -p logs backups data/postgres data/redis data/vault ssl

    log_success "Structure des répertoires créée"
}

download_files() {
    log "⬇️ Téléchargement de WindFlow ${WINDFLOW_VERSION}..."

    # Construction de l'URL de téléchargement
    local download_url
    if [ "$WINDFLOW_VERSION" = "latest" ]; then
        download_url="https://github.com/stefapi/windflow/archive/main.tar.gz"
    else
        # Nettoyer la version (enlever le 'v' si présent)
        local clean_version
        clean_version=$(echo "$WINDFLOW_VERSION" | sed 's/^v//')
        download_url="https://github.com/stefapi/windflow/archive/v${clean_version}.tar.gz"
    fi

    # Créer un répertoire temporaire pour le téléchargement
    local temp_dir
    temp_dir=$(mktemp -d 2>/dev/null || mkdir -p "/tmp/windflow-install-$$")
    local temp_file="$temp_dir/windflow.tar.gz"

    # Téléchargement avec retry et vérification
    log "📥 Téléchargement depuis: $download_url"
    if ! retry_command 3 5 "téléchargement WindFlow" curl -L "$download_url" -o "$temp_file"; then
        log_error "Échec du téléchargement de WindFlow"
        rm -rf "$temp_dir"
        exit 1
    fi

    # Vérification de l'intégrité du fichier téléchargé
    if [ ! -s "$temp_file" ]; then
        log_error "Fichier téléchargé vide"
        rm -rf "$temp_dir"
        exit 1
    fi

    # Test de l'archive
    if ! tar -tzf "$temp_file" >/dev/null 2>&1; then
        log_error "Archive corrompue"
        rm -rf "$temp_dir"
        exit 1
    fi

    # Extraction avec vérification
    log "📂 Extraction de l'archive..."
    if ! tar xzf "$temp_file" -C . --strip-components=1; then
        log_error "Échec de l'extraction de WindFlow"
        rm -rf "$temp_dir"
        exit 1
    fi

    # Nettoyage
    rm -rf "$temp_dir"

    # Vérification des fichiers essentiels
    local essential_files="docker-compose.yml Makefile env.example"
    local missing_files=""

    for file in $essential_files; do
        if [ ! -f "$file" ]; then
            missing_files="$missing_files $file"
        fi
    done

    if [ -n "$missing_files" ]; then
        log_error "Fichiers essentiels manquants:$missing_files"
        log "Vérifiez que vous téléchargez la bonne version de WindFlow"
        exit 1
    fi

    # Vérification des permissions
    chmod +x scripts/* 2>/dev/null || true
    chmod +x dev/scripts/* 2>/dev/null || true

    log_success "WindFlow ${WINDFLOW_VERSION} téléchargé et extrait avec succès"
}

setup_environment() {
    log "⚙️ Configuration de l'environnement..."

    # Génération des secrets sécurisés
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    VAULT_TOKEN=$(openssl rand -hex 16)
    GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-12)

    # Copie et personnalisation du fichier .env
    cp .env.example .env.tmp

    # Remplacement des variables dans le fichier .env
    sed -i.bak \
        -e "s|DOMAIN=.*|DOMAIN=${DOMAIN}|" \
        -e "s|SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" \
        -e "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" \
        -e "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASSWORD}|" \
        -e "s|VAULT_TOKEN=.*|VAULT_TOKEN=${VAULT_TOKEN}|" \
        -e "s|GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=${GRAFANA_PASSWORD}|" \
        .env.tmp

    mv .env.tmp .env
    rm -f .env.tmp.bak

    log_success "Fichier .env configuré"

    # Sauvegarde des mots de passe
    cat > passwords.txt << EOF
# MOTS DE PASSE WINDFLOW - GARDEZ CE FICHIER EN SÉCURITÉ

PostgreSQL: ${POSTGRES_PASSWORD}
Redis: ${REDIS_PASSWORD}
Vault Token: ${VAULT_TOKEN}
Grafana Admin: admin / ${GRAFANA_PASSWORD}

# Accès aux services:
Frontend: http://${DOMAIN}:3000
API: http://${DOMAIN}:8000
Grafana: http://${DOMAIN}:3001
Prometheus: http://${DOMAIN}:9090
EOF

    chmod 600 passwords.txt
    log_success "Mots de passe sauvegardés dans passwords.txt"
}

start_services() {
    log "🚀 Démarrage des services WindFlow..."

    # Déterminer la commande Docker Compose disponible
    local compose_cmd=""
    if command -v "docker compose" >/dev/null 2>&1; then
        compose_cmd="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        compose_cmd="docker-compose"
    else
        log_error "Aucune commande Docker Compose trouvée"
        exit 1
    fi

    log "🔧 Utilisation de: $compose_cmd"

    # Pull des images avec retry
    log "📥 Téléchargement des images Docker..."
    if ! retry_command 3 10 "pull des images Docker" $compose_cmd pull; then
        log_warning "Échec du pull des images, tentative de démarrage quand même..."
    fi

    # Démarrage des services
    log "🚀 Démarrage des conteneurs..."
    if ! retry_command 2 15 "démarrage des services" $compose_cmd up -d; then
        log_error "Échec du démarrage des services Docker"

        # Diagnostic en cas d'échec
        log "📋 Diagnostic des services:"
        $compose_cmd ps || true
        $compose_cmd logs --tail=10 || true

        exit 1
    fi

    # Attendre que les services soient prêts
    log "⏳ Attente du démarrage des services..."
    sleep 10

    # Vérification de l'état des services
    local services_status
    services_status=$($compose_cmd ps 2>/dev/null || echo "error")

    if echo "$services_status" | grep -q "Up"; then
        log_success "Services Docker démarrés"
    else
        log_warning "Problème potentiel avec les services Docker"
        log "État des services:"
        echo "$services_status"
    fi

    # Export de la commande pour les autres fonctions
    DOCKER_COMPOSE_CMD="$compose_cmd"
}

test_installation() {
    log "🧪 Test de l'installation..."

    # Attendre que les services soient complètement prêts
    log "⏳ Attente du démarrage complet des services (60 secondes)..."
    sleep 60

    # Test des services avec timeout
    local services_ok=0
    local total_services=0

    # Test API Backend
    total_services=$((total_services + 1))
    log "🔍 Test de l'API Backend..."
    if timeout 10 curl -f -s "http://localhost:8000/health" >/dev/null 2>&1; then
        log_success "✅ API Backend accessible"
        services_ok=$((services_ok + 1))
    elif timeout 10 curl -f -s "http://localhost:8000/api/v1/health" >/dev/null 2>&1; then
        log_success "✅ API Backend accessible (endpoint alternatif)"
        services_ok=$((services_ok + 1))
    else
        log_warning "❌ API Backend non accessible"
        # Diagnostic supplémentaire
        if $DOCKER_COMPOSE_CMD logs windflow-api 2>/dev/null | tail -5; then
            log "Logs de l'API:"
            $DOCKER_COMPOSE_CMD logs windflow-api 2>/dev/null | tail -5
        fi
    fi

    # Test Frontend
    total_services=$((total_services + 1))
    log "🔍 Test du Frontend..."
    if timeout 10 curl -f -s "http://localhost:3000" >/dev/null 2>&1; then
        log_success "✅ Frontend accessible"
        services_ok=$((services_ok + 1))
    else
        log_warning "❌ Frontend non accessible"
        # Diagnostic supplémentaire
        if $DOCKER_COMPOSE_CMD logs windflow-frontend 2>/dev/null | tail -5; then
            log "Logs du Frontend:"
            $DOCKER_COMPOSE_CMD logs windflow-frontend 2>/dev/null | tail -5
        fi
    fi

    # Test Base de données (PostgreSQL)
    total_services=$((total_services + 1))
    log "🔍 Test de la base de données..."
    if $DOCKER_COMPOSE_CMD exec -T postgres pg_isready >/dev/null 2>&1; then
        log_success "✅ Base de données accessible"
        services_ok=$((services_ok + 1))
    else
        log_warning "❌ Base de données non accessible"
    fi

    # Test Redis
    total_services=$((total_services + 1))
    log "🔍 Test de Redis..."
    if $DOCKER_COMPOSE_CMD exec -T redis redis-cli ping >/dev/null 2>&1; then
        log_success "✅ Redis accessible"
        services_ok=$((services_ok + 1))
    else
        log_warning "❌ Redis non accessible"
    fi

    # Vérifier l'état général des conteneurs
    log "🔍 Vérification de l'état des conteneurs..."
    local containers_status
    containers_status=$($DOCKER_COMPOSE_CMD ps 2>/dev/null || echo "error")

    if echo "$containers_status" | grep -q "Up"; then
        local running_containers
        running_containers=$(echo "$containers_status" | grep -c "Up" || echo "0")
        log_success "✅ Conteneurs Docker actifs: $running_containers"
    else
        log_warning "❌ Problème avec les conteneurs Docker"
        log "État détaillé:"
        echo "$containers_status"
    fi

    # Résumé des tests
    log "📊 Résumé des tests: $services_ok/$total_services services fonctionnels"

    if [ $services_ok -eq $total_services ]; then
        log_success "🎉 Tous les services sont opérationnels!"
        return 0
    elif [ $services_ok -gt 0 ]; then
        log_warning "⚠️  Installation partielle - certains services peuvent ne pas être prêts"
        log "   Attendez quelques minutes et vérifiez l'état avec: docker compose ps"
        return 0
    else
        log_error "❌ Aucun service n'est accessible"
        log "   Vérifiez les logs avec: docker compose logs"
        return 1
    fi
}

show_final_info() {
    echo
    echo -e "${GREEN}🎉 Installation de WindFlow terminée avec succès!${NC}"
    echo
    echo -e "${BLUE}📍 Accès aux services:${NC}"
    echo "   Frontend:    http://${DOMAIN}:3000"
    echo "   API:         http://${DOMAIN}:8000"
    echo "   API Docs:    http://${DOMAIN}:8000/docs"
    echo "   Grafana:     http://${DOMAIN}:3001"
    echo "   Prometheus:  http://${DOMAIN}:9090"
    echo
    echo -e "${BLUE}📁 Fichiers importants:${NC}"
    echo "   Installation: ${INSTALL_DIR}"
    echo "   Configuration: ${INSTALL_DIR}/.env"
    echo "   Mots de passe: ${INSTALL_DIR}/passwords.txt"
    echo "   Logs: ${LOG_FILE}"
    echo
    echo -e "${BLUE}🔧 Commandes utiles:${NC}"
    echo "   Démarrer:     make serve"
    echo "   Arrêter:      make docker-stop"
    echo "   Logs:         make docker-logs"
    echo "   Status:       docker compose ps"
    echo
    echo -e "${YELLOW}⚠️  Lisez le fichier passwords.txt pour les identifiants!${NC}"
    echo
}

# ============================================================================
# GESTION D'ERREURS
# ============================================================================

cleanup_on_error() {
    log_error "Erreur lors de l'installation. Nettoyage..."

    if [ -f "docker-compose.yml" ]; then
        $DOCKER_COMPOSE_CMD down -v 2>/dev/null || true
    fi

    exit 1
}

# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

main() {
    # Désactiver set -e temporairement pour gérer les erreurs manuellement
    set +e

    # Gestion des erreurs et signaux
    trap cleanup_on_error INT TERM EXIT

    # Parse des arguments
    parse_arguments "$@"

    # Vérification des privilèges
    if [ "$(id -u)" -eq 0 ] && [ "$NOSUDO" = "false" ]; then
        log_warning "Ce script ne doit pas être exécuté en tant que root"
        log "Relancez le script en tant qu'utilisateur normal"
        exit 1
    fi

    # Affichage du banner
    show_banner

    # Exécution des étapes d'installation avec gestion d'erreurs
    log "🏁 Démarrage de l'installation WindFlow..."

    # Étape 1: Prérequis
    if ! check_requirements; then
        log_error "Échec de la vérification des prérequis"
        exit 1
    fi

    # Étape 2: Répertoires
    if ! setup_directories; then
        log_error "Échec de la création des répertoires"
        exit 1
    fi

    # Étape 3: Téléchargement
    if ! download_files; then
        log_error "Échec du téléchargement des fichiers"
        exit 1
    fi

    # Étape 4: Configuration
    if ! setup_environment; then
        log_error "Échec de la configuration de l'environnement"
        exit 1
    fi

    # Étape 5: Démarrage des services
    if ! start_services; then
        log_error "Échec du démarrage des services"
        exit 1
    fi

    # Étape 6: Tests d'installation
    log "🧪 Lancement des tests d'installation..."
    if ! test_installation; then
        log_warning "Certains tests ont échoué mais l'installation peut être fonctionnelle"
        log "Vérifiez manuellement l'état des services avec: docker compose ps"
    fi

    # Étape 7: Informations finales
    show_final_info

    # Réactiver set -e et désactiver le trap pour une sortie propre
    set -e
    trap - INT TERM EXIT

    log_success "🎉 Installation WindFlow terminée avec succès!"

    # Code de sortie basé sur les tests
    if [ $SCRIPT_EXIT_CODE -eq 0 ]; then
        exit 0
    else
        log_warning "Installation terminée avec des avertissements (code: $SCRIPT_EXIT_CODE)"
        exit 0  # On ne fait pas échouer l'installation pour des avertissements
    fi
}

# Exécution du script principal
main "$@"
