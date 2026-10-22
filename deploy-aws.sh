#!/usr/bin/env bash
# ==============================================================================
# HMFDA - Automated AWS EC2 Deployment Script
# Hybrid Multimodal Fall Detection and Alert System
# Compatible with Ubuntu 22.04 LTS / Ubuntu 24.04 LTS
# ==============================================================================

set -euo pipefail

echo "===================================================================="
echo "  🚀 Starting HMFDA AWS Deployment"
echo "===================================================================="

# 1. Update and upgrade apt packages
echo "📦 [1/6] Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git

# 2. Add Swap Space (Crucial for smooth Docker builds on t3.medium / t3.large)
if ! swapon --show | grep -q "/swapfile"; then
    echo "💾 [2/6] Configuring 2GB Swap space..."
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    echo "💾 [2/6] Swap space already present. Skipping..."
fi

# 3. Install Docker and Docker Compose plugin
if ! command -v docker &> /dev/null; then
    echo "🐳 [3/6] Installing official Docker Engine..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
else
    echo "🐳 [3/6] Docker already installed. Skipping..."
fi

# 4. Environment & APK preparation
echo "⚙️  [4/6] Checking directory structure & environment variables..."

# Auto-detect and fix repository folder structure if cloned inside itself
if [ ! -d "Hybrid-Multimodel-Fall-Detection-System" ]; then
    if [ -d "HMFDA/Hybrid-Multimodel-Fall-Detection-System" ]; then
        echo "📁 Found nested HMFDA folder. Moving files to current directory..."
        mv HMFDA/Hybrid-Multimodel-Fall-Detection-System ./
        [ -d "HMFDA/FallAlert" ] && mv HMFDA/FallAlert ./
    fi
fi

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env from .env.example"
    fi
fi

mkdir -p docker/web/download
if [ -f FallAlert/app/build/outputs/apk/debug/app-debug.apk ]; then
    cp FallAlert/app/build/outputs/apk/debug/app-debug.apk docker/web/download/fallalert.apk
    echo "✅ FallAlert APK prepared for direct download at /download/fallalert.apk"
elif [ -f docker/web/download/fallalert.apk ]; then
    echo "✅ Existing fallalert.apk found in download directory"
else
    echo "⚠️  No APK found yet. You can build it in Android Studio or copy it into docker/web/download/fallalert.apk later."
fi

# 5. Build and launch Docker containers
echo "🏗️  [5/6] Building and starting HMFDA microservices via Docker Compose..."
sudo docker compose down --remove-orphans || true
sudo docker compose up -d --build

# 6. Verification & Connectivity Report
echo "🔍 [6/6] Checking container health status..."
sleep 5
sudo docker compose ps

# Fetch Public IP
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com || curl -s ifconfig.me || echo "<YOUR-AWS-PUBLIC-IP>")

echo ""
echo "===================================================================="
echo "  🎉 DEPLOYMENT SUCCESSFUL!"
echo "===================================================================="
echo "Public IP Address: $PUBLIC_IP"
echo ""
echo "🌐 Access Links:"
echo "  • Web Gateway & APK Download : http://$PUBLIC_IP"
echo "  • Direct APK Download Link   : http://$PUBLIC_IP/download/fallalert.apk"
echo "  • 3D Digital Twin Dashboard  : http://$PUBLIC_IP/dashboard/ (or http://$PUBLIC_IP:8501)"
echo "  • Centralized Alert Manager  : http://$PUBLIC_IP:8002"
echo "  • Outdoor Sensor Receiver    : http://$PUBLIC_IP:8000"
echo ""
echo "📱 Android Mobile App Setup (FallAlert):"
echo "  1. Download APK onto your phone from: http://$PUBLIC_IP/download/fallalert.apk"
echo "  2. Open FallAlert app -> Settings"
echo "  3. Set 'Server URL' to: http://$PUBLIC_IP:8002"
echo "  4. Add Emergency Contact phone number"
echo "  5. Press 'START TRACKING'!"
echo "===================================================================="
