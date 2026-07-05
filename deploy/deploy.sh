#!/bin/bash
set -e

APP_DIR="/opt/lotus-manager"
REPO="https://github.com/Refaat1942/Lotus-Manager-Tool.git"
PORT=16320

echo "=== Lotus Manager Web - VPS Deploy ==="

if [ -d "$APP_DIR/.git" ]; then
    echo "Updating existing repo..."
    cd $APP_DIR
    git fetch origin main
    git reset --hard origin/main
else
    echo "Cloning repository..."
    sudo rm -rf $APP_DIR
    sudo git clone $REPO $APP_DIR
    cd $APP_DIR
fi

COMMIT=$(git rev-parse --short HEAD)
echo "Deploying commit: $COMMIT"

if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi

export APP_VERSION="$COMMIT"

sudo docker compose down 2>/dev/null || true
sudo docker compose build --no-cache --build-arg APP_VERSION="$COMMIT"
sudo docker compose up -d --force-recreate

echo ""
echo "✓ Deployed successfully!"
echo "  Commit: $COMMIT"
echo "  URL:    http://$(hostname -I | awk '{print $1}'):$PORT"
echo "  Login:  admin / admin"
echo "  Tip:    Hard-refresh browser (Ctrl+F5) after deploy"
