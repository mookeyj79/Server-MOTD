#!/usr/bin/env bash
set -euo pipefail

# Color codes
RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[0;33m'
NC='\033[0m'

# Logging function
log() {
    printf "\n${GRN}[*]${NC} $1\n"
}

warn() {
    printf "\n${YEL}[!]${NC} $1\n"
}

# Start
log "Installing required packages..."
sudo apt update
sudo apt install -y python3 python3-pip python3-requests lsb-release figlet jq toilet boxes lolcat lastlog2

# Determine Linux Distro
UNAME=$(uname | tr '[:upper:]' '[:lower:]')
DISTRO=""

if [ "$UNAME" == "linux" ]; then
    if [ -f /etc/lsb-release ] || [ -d /etc/lsb-release.d ]; then
        DISTRO=$(lsb_release -i | cut -d: -f2 | sed 's/^\t//')
    else
        DISTRO=$(ls -d /etc/[A-Za-z]*[_-][rv]e[lr]* 2>/dev/null | grep -v "lsb" | head -n1 | cut -d'/' -f3 | cut -d'-' -f1 | cut -d'_' -f1)
    fi
fi

[ -z "$DISTRO" ] && DISTRO=$UNAME

# Install Ubuntu-specific packages
if [ "$DISTRO" == "Ubuntu" ]; then
    log "Installing Ubuntu specific packages..."
    sudo apt install -y update-motd update-notifier-common
fi

log "Installing Python packages..."
sudo -H python3 -m pip install -r requirements.txt --break-system-packages

log "Cleaning up existing MOTD files..."
sudo rm -rf /etc/update-motd.d /etc/motd /etc/motd.dynamic 2>/dev/null || true

# Disable motd-news if present
if [ -f /etc/default/motd-news ]; then
    log "Disabling motd-news..."
    sudo sed -i 's/ENABLED=1/ENABLED=0/g' /etc/default/motd-news
fi

log "Creating files and directories..."
sudo mkdir -m 755 /etc/update-motd.d
sudo touch /etc/motd
sudo chmod 644 /etc/motd

REAL_USER=$(logname)
sudo chown "$REAL_USER:$REAL_USER" /etc/update-motd.d /etc/motd

sudo touch activity.log
sudo chmod 644 activity.log

log "Copying MOTD files to system..."
sudo cp -a ./motd/* /etc/update-motd.d/
sudo chmod 755 /etc/update-motd.d/*
sudo chmod 644 /etc/update-motd.d/colors.txt

if [ -f /etc/ssh/sshd_config ]; then
    log "Adjusting sshd_config..."
    sudo sed -i 's/PrintLastLog yes/PrintLastLog no/g' /etc/ssh/sshd_config
fi

if [ ! -f ./config.json ]; then
    warn "Copying default config..."
    warn "You should edit this file."
    cp ./config.json.example ./config.json
fi

log "Finished!"
