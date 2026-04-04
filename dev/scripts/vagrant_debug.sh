#!/bin/bash
set -e

# ============================================================================
# WindFlow - Debug Environment Setup Script
# Run as root during Vagrant provisioning
# ============================================================================

echo "🔧 Setting up WindFlow debug environment..."

# Create docker group if it doesn't exist
groupadd -f docker

# Create dockerdebug user if it doesn't exist
if ! id -u dockerdebug &>/dev/null; then
  # Password: D0ck3rd3bug
  useradd -m -s /bin/bash -p '$y$j9T$ZID4LGDrzXpFb3mHiE36..$SobBnzvHXNjivjiPWvV1kGVN0/XgBQT7yxIOwnitop/' dockerdebug
  echo "✅ User dockerdebug created"
else
  echo "ℹ️  User dockerdebug already exists, skipping creation"
fi

# Add dockerdebug to docker group
usermod -aG docker dockerdebug

# Enable password authentication for SSH
sed -Ei 's/^#?\s*PasswordAuthentication\s+(yes|no)/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Restart SSH daemon
if command -v systemctl &>/dev/null; then
  systemctl restart ssh || systemctl restart sshd || true
else
  service ssh restart || service sshd restart || true
fi

# Update package list and install avahi-daemon for mDNS hostname resolution
apt-get update -qq
apt-get install -y -q avahi-daemon

# Restart dbus (required by avahi)
if command -v systemctl &>/dev/null; then
  systemctl restart dbus || true
  systemctl enable avahi-daemon || true
  systemctl start avahi-daemon || true
else
  service dbus restart || true
  service avahi-daemon restart || true
fi

echo "✅ Debug environment setup complete"
echo "   SSH user: dockerdebug / D0ck3rd3bug"
