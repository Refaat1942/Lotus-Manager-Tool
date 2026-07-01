@echo off
echo ============================================
echo  Lotus Manager Web - VPS Deployment
echo  Target: http://187.124.15.14:16320
echo  Login:  admin / admin
echo ============================================
echo.
echo 1. Copy project to VPS:
echo    scp -r core web_app run_web.py Dockerfile docker-compose.yml deploy root@187.124.15.14:/opt/lotus-manager/
echo.
echo 2. SSH into VPS and run:
echo    cd /opt/lotus-manager
echo    chmod +x deploy/deploy.sh
echo    ./deploy/deploy.sh
echo.
echo 3. Open firewall port 16320 if needed:
echo    ufw allow 16320/tcp
echo.
pause
