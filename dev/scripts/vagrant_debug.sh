#!/bin/bash

groupadd docker
# add user with password D0ck3rd3bug
useradd dockerdebug -p '$y$j9T$ZID4LGDrzXpFb3mHiE36..$SobBnzvHXNjivjiPWvV1kGVN0/XgBQT7yxIOwnitop/'
sed -Ei 's/^#?\s*PasswordAuthentication\s+(yes|no)/PasswordAuthentication yes/' /etc/ssh/sshd_config
usermod -aG docker dockerdebug
service ssh restart
apt update
apt install -y avahi-daemon
service dbus restart
