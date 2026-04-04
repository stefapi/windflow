# -*- mode: ruby -*-
# vi: set ft=ruby :

# WindFlow Vagrant Development Environment
# Supports multiple Linux distributions for testing installation robustness

Vagrant.configure("2") do |config|
  # Default configuration for all VMs
  config.vm.box_check_update = false

  # Vagrant disksize plugin configuration (if available)
  if Vagrant.has_plugin?("vagrant-disksize")
    config.disksize.size = '60GB'
  end

  # ============================================================================
  # DEBUG CONFIGURATION - Development and Testing
  # ============================================================================

  config.vm.define "windflow-debug", primary: true, autostart: true do |debug|
    debug.vm.box = "bento/debian-13"
    debug.vm.hostname = "windflow-debug"

    # Network configuration for debug access
    # MAC address is fixed to ensure consistent IP address for remote debugging
    # Note: bridge interface name depends on the host machine (adapt to your local interface)
    debug.vm.network "public_network", dhcp: true, mac: "080027051304", bridge: "enp15s0"

    # Port forwarding for WindFlow services
    debug.vm.network "forwarded_port", guest: 3000, host: 3003   # Frontend
    debug.vm.network "forwarded_port", guest: 8000, host: 8000   # API Backend
    debug.vm.network "forwarded_port", guest: 3001, host: 3001   # Grafana
    debug.vm.network "forwarded_port", guest: 9090, host: 9091   # Prometheus
    debug.vm.network "forwarded_port", guest: 5555, host: 5555   # Flower (Celery monitoring)
    debug.vm.network "forwarded_port", guest: 5432, host: 5432   # PostgreSQL
    debug.vm.network "forwarded_port", guest: 6379, host: 6479   # Redis
    debug.vm.network "forwarded_port", guest: 8200, host: 8200   # Vault
    debug.vm.network "forwarded_port", guest: 22, host: 2222, id: "ssh"   # SSH

    # VirtualBox configuration
    debug.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-debug"
      vb.memory = "16384"   # 16GB RAM for comprehensive testing
      vb.cpus = 4
      vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
      vb.customize ["modifyvm", :id, "--natdnsproxy1", "on"]
    end

    # -------------------------------------------------------------------------
    # Provisioner 1: System setup (runs BEFORE /vagrant is mounted)
    # This block must NOT reference /vagrant - it runs before Guest Additions
    # are ready. All content is inlined from dev/scripts/vagrant_debug.sh
    # -------------------------------------------------------------------------
    debug.vm.provision "shell", name: "debug-system-setup", inline: <<-SHELL
      set -e
      echo "🔧 WindFlow Debug Environment Setup"

      # Execute debug script if present
      if [ -e /vagrant/dev/scripts/vagrant_debug.sh ]; then
        echo "📋 Executing vagrant_debug.sh..."
        bash /vagrant/dev/scripts/vagrant_debug.sh
      fi

      echo "✅ System setup complete - ready for Guest Additions"
    SHELL

    # -------------------------------------------------------------------------
    # Provisioner 2: WindFlow installation (runs AFTER /vagrant is mounted)
    # At this point Guest Additions are installed and /vagrant is available
    # -------------------------------------------------------------------------
    debug.vm.provision "shell", name: "windflow-install", inline: <<-SHELL
      echo "🚀 Installing WindFlow..."
      if [ -e /vagrant/scripts/install.sh ]; then
        cd /vagrant
        bash scripts/install.sh --install-dir /home/vagrant/windflow --domain localhost
      else
        echo "⚠️  /vagrant/scripts/install.sh not found - skipping WindFlow installation"
      fi

      echo "✅ WindFlow Debug Environment Ready"
      echo "🌐 Access WindFlow at: http://localhost:3003"
      echo "🔑 SSH: vagrant ssh windflow-debug"
      echo "🐳 Docker user: dockerdebug / D0ck3rd3bug"
    SHELL
  end

  # ============================================================================
  # MULTI-DISTRIBUTION TESTING ENVIRONMENTS
  # ============================================================================

  # Debian Testing Environment
  config.vm.define "windflow-debian", autostart: false do |debian|
    debian.vm.box = "bento/debian-13"
    debian.vm.hostname = "windflow-debian"

    # Port forwarding with offset
    debian.vm.network "forwarded_port", guest: 3000, host: 3100
    debian.vm.network "forwarded_port", guest: 8000, host: 8100
    debian.vm.network "forwarded_port", guest: 3001, host: 3101

    debian.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-debian"
      vb.memory = "4096"
      vb.cpus = 2
    end

    debian.vm.provision "shell", inline: <<-SHELL
      echo "🐧 Testing WindFlow on Debian"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # Ubuntu Testing Environment
  config.vm.define "windflow-ubuntu", autostart: false do |ubuntu|
    ubuntu.vm.box = "cloud-image/ubuntu-26.04"
    ubuntu.vm.hostname = "windflow-ubuntu"

    # Port forwarding with offset
    ubuntu.vm.network "forwarded_port", guest: 3000, host: 3200
    ubuntu.vm.network "forwarded_port", guest: 8000, host: 8200
    ubuntu.vm.network "forwarded_port", guest: 3001, host: 3201

    ubuntu.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-ubuntu"
      vb.memory = "4096"
      vb.cpus = 2
    end

    ubuntu.vm.provision "shell", inline: <<-SHELL
      echo "🟠 Testing WindFlow on Ubuntu"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # Fedora Testing Environment
  config.vm.define "windflow-fedora", autostart: false do |fedora|
    fedora.vm.box = "cloud-image/fedora-43"
    fedora.vm.hostname = "windflow-fedora"

    # Port forwarding with offset
    fedora.vm.network "forwarded_port", guest: 3000, host: 3300
    fedora.vm.network "forwarded_port", guest: 8000, host: 8300
    fedora.vm.network "forwarded_port", guest: 3001, host: 3301

    fedora.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-fedora"
      vb.memory = "4096"
      vb.cpus = 2
    end

    fedora.vm.provision "shell", inline: <<-SHELL
      echo "🔴 Testing WindFlow on Fedora"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # CentOS Stream Testing Environment
  config.vm.define "windflow-centos", autostart: false do |centos|
    centos.vm.box = "cloud-image/centos-10-stream"
    centos.vm.hostname = "windflow-centos"

    # Port forwarding with offset
    centos.vm.network "forwarded_port", guest: 3000, host: 3400
    centos.vm.network "forwarded_port", guest: 8000, host: 8400
    centos.vm.network "forwarded_port", guest: 3001, host: 3401

    centos.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-centos"
      vb.memory = "4096"
      vb.cpus = 2
    end

    centos.vm.provision "shell", inline: <<-SHELL
      echo "🟢 Testing WindFlow on CentOS Stream"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # Rocky Linux Testing Environment
  config.vm.define "windflow-rocky", autostart: false do |rocky|
    rocky.vm.box = "cloud-image/rocky-10"
    rocky.vm.hostname = "windflow-rocky"

    # Port forwarding with offset
    rocky.vm.network "forwarded_port", guest: 3000, host: 3500
    rocky.vm.network "forwarded_port", guest: 8000, host: 8500
    rocky.vm.network "forwarded_port", guest: 3001, host: 3501

    rocky.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-rocky"
      vb.memory = "4096"
      vb.cpus = 2
    end

    rocky.vm.provision "shell", inline: <<-SHELL
      echo "⛰️ Testing WindFlow on Rocky Linux"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # AlmaLinux Testing Environment
  config.vm.define "windflow-alma", autostart: false do |alma|
    alma.vm.box = "cloud-image/almalinux-10"
    alma.vm.hostname = "windflow-alma"

    # Port forwarding with offset
    alma.vm.network "forwarded_port", guest: 3000, host: 3600
    alma.vm.network "forwarded_port", guest: 8000, host: 8600
    alma.vm.network "forwarded_port", guest: 3001, host: 3601

    alma.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-alma"
      vb.memory = "4096"
      vb.cpus = 2
    end

    alma.vm.provision "shell", inline: <<-SHELL
      echo "🦅 Testing WindFlow on AlmaLinux"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # Arch Linux Testing Environment
  config.vm.define "windflow-arch", autostart: false do |arch|
    arch.vm.box = "archlinux/archlinux"
    arch.vm.hostname = "windflow-arch"

    # Port forwarding with offset
    arch.vm.network "forwarded_port", guest: 3000, host: 3700
    arch.vm.network "forwarded_port", guest: 8000, host: 8700
    arch.vm.network "forwarded_port", guest: 3001, host: 3701

    arch.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-arch"
      vb.memory = "4096"
      vb.cpus = 2
    end

    arch.vm.provision "shell", inline: <<-SHELL
      echo "🏹 Testing WindFlow on Arch Linux"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # ============================================================================
  # SPECIALIZED TESTING ENVIRONMENTS
  # ============================================================================

  # Alpine Linux Testing Environment (Lightweight)
  config.vm.define "windflow-alpine", autostart: false do |alpine|
    alpine.vm.box = "cloud-image/alpine-3.23"
    alpine.vm.hostname = "windflow-alpine"

    # Port forwarding with offset
    alpine.vm.network "forwarded_port", guest: 3000, host: 3800
    alpine.vm.network "forwarded_port", guest: 8000, host: 8800
    alpine.vm.network "forwarded_port", guest: 3001, host: 3801

    alpine.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-alpine"
      vb.memory = "2048"
      vb.cpus = 2
    end

    alpine.vm.provision "shell", inline: <<-SHELL
      echo "🏔️ Testing WindFlow on Alpine Linux"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # Minimal Testing Environment (Resource constrained)
  config.vm.define "windflow-minimal", autostart: false do |minimal|
    minimal.vm.box = "cloud-image/debian-13"
    minimal.vm.hostname = "windflow-minimal"

    # Port forwarding with offset
    minimal.vm.network "forwarded_port", guest: 3000, host: 3900
    minimal.vm.network "forwarded_port", guest: 8000, host: 8900

    minimal.vm.provider "virtualbox" do |vb|
      vb.name = "windflow-minimal"
      vb.memory = "2048"  # Minimal RAM to test constraints
      vb.cpus = 1
    end

    minimal.vm.provision "shell", inline: <<-SHELL
      echo "⚡ Testing WindFlow on Minimal Resources"
      cd /vagrant && bash scripts/install.sh --install-dir /opt/windflow --domain localhost
    SHELL
  end

  # ============================================================================
  # GLOBAL PROVISIONING (Common to all VMs except debug)
  # ============================================================================

  # This runs after the specific provisioning
  config.vm.provision "shell", run: "always", inline: <<-SHELL
    echo "🔄 Global post-provisioning tasks"

    # Ensure Docker is running
    if command -v systemctl >/dev/null 2>&1; then
      systemctl enable docker 2>/dev/null || true
      systemctl start docker 2>/dev/null || true
    fi

    # Display service status
    if command -v docker >/dev/null 2>&1; then
      echo "🐳 Docker status:"
      docker --version
      docker info 2>/dev/null | grep "Server Version" || echo "Docker not running"
    fi

    # Display WindFlow status if installed
    if [ -d "/opt/windflow" ] || [ -d "/home/vagrant/windflow" ]; then
      echo "🚀 WindFlow installation detected"
      if command -v docker-compose >/dev/null 2>&1; then
        echo "📊 Container status:"
        docker-compose ps 2>/dev/null || echo "No containers running"
      elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        echo "📊 Container status:"
        docker compose ps 2>/dev/null || echo "No containers running"
      fi
    fi

    echo "✅ Global provisioning completed"
  SHELL
end

# ============================================================================
# VAGRANT USAGE INSTRUCTIONS
# ============================================================================
#
# 📦 Required plugins (install once on the host):
#   vagrant plugin install vagrant-vbguest    # Auto-install VirtualBox Guest Additions
#   vagrant plugin install vagrant-disksize   # Resize VM disk (optional)
#
# 🚀 Quick Start:
#   vagrant up                         # Launches windflow-debug (default)
#   vagrant up windflow-debug          # Explicit launch of debug environment
#   vagrant ssh                        # Connect to windflow-debug (default)
#   vagrant ssh windflow-debug         # Access debug environment
#
# 🧪 Testing on specific distributions:
#   vagrant up windflow-debian          # Test on Debian
#   vagrant up windflow-ubuntu          # Test on Ubuntu
#   vagrant up windflow-fedora          # Test on Fedora
#   vagrant up windflow-centos          # Test on CentOS Stream
#   vagrant up windflow-rocky           # Test on Rocky Linux
#   vagrant up windflow-alma            # Test on AlmaLinux
#   vagrant up windflow-arch            # Test on Arch Linux
#   vagrant up windflow-alpine          # Test on Alpine Linux
#
# 🔧 Resource testing:
#   vagrant up windflow-minimal         # Test on minimal resources
#
# 🌐 Access URLs (when using windflow-debug):
#   Frontend:    http://localhost:3003
#   API:         http://localhost:8000
#   API Docs:    http://localhost:8000/docs
#   Grafana:     http://localhost:3001
#   Prometheus:  http://localhost:9091
#   Flower:      http://localhost:5555
#
# 📝 Debug Access:
#   SSH User:    dockerdebug
#   Password:    D0ck3rd3bug
#   SSH Port:    2222
#
# 🔄 Management:
#   vagrant reload <vm-name>            # Restart VM
#   vagrant halt <vm-name>              # Stop VM
#   vagrant destroy <vm-name>           # Remove VM
#   vagrant status                      # Show all VMs status
#
# ============================================================================
