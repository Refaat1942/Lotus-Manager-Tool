@echo off
echo ============================================
echo  Lotus Manager Web - VPS Deployment
echo  Repo: https://github.com/Refaat1942/Lotus-Manager-Tool
echo  URL:  http://187.124.15.14:16320
echo  Login: admin / admin
echo ============================================
echo.
echo SSH into your VPS, then run:
echo.
echo   git clone https://github.com/Refaat1942/Lotus-Manager-Tool.git /opt/lotus-manager
echo   cd /opt/lotus-manager
echo   chmod +x deploy/deploy.sh
echo   ./deploy/deploy.sh
echo   ufw allow 16320/tcp
echo.
echo To update later:
echo   cd /opt/lotus-manager ^&^& git pull ^&^& docker compose up -d --build
echo.
pause
