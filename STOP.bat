@echo off
title ICCBPO - Stop Services
echo Stopping ICCBPO Certificate Checker...
docker compose -f docker-compose.dev.yml down
echo Done. Data is preserved in Docker volumes.
pause
