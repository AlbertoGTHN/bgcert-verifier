@echo off
title ICCBPO Certificate Checker - Startup
color 0A

echo.
echo  ============================================================
echo   ICCBPO Certificate QR Code Checker
echo  ============================================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Docker Desktop is NOT running.
    echo.
    echo  Please:
    echo    1. Open Docker Desktop from Start Menu or Desktop
    echo    2. Wait for the whale icon in the system tray to stop animating
    echo    3. Run this script again
    echo.
    echo  Opening Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo.
    echo  Press any key once Docker Desktop is ready...
    pause >nul

    :: Check again
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [ERROR] Docker still not responding. Please start Docker Desktop manually.
        pause
        exit /b 1
    )
)

echo  [OK] Docker is running
echo.

:: Create directories if missing
if not exist "uploads" mkdir uploads
if not exist "screenshots" mkdir screenshots
if not exist "reports" mkdir reports

echo  [INFO] Starting services (first run will take 10-15 minutes to build)...
echo  [INFO] Using dev configuration (faster build)
echo.

docker compose -f docker-compose.dev.yml up --build -d

echo.
echo  [INFO] Waiting for services to start...
timeout /t 10 /nobreak >nul

docker compose -f docker-compose.dev.yml ps

echo.
echo  ============================================================
echo   Application is starting!
echo  ============================================================
echo.
echo   Frontend:   http://localhost:3000
echo   Backend:    http://localhost:8000
echo   API Docs:   http://localhost:8000/api/docs
echo.
echo   Login:
echo     Email:    admin@iccbpo.com
echo     Password: Admin@ICCBPO2024!
echo.
echo  Opening browser...
timeout /t 5 /nobreak >nul
start "" "http://localhost:3000"
echo.
echo  Press any key to view logs (Ctrl+C to stop watching logs)
pause >nul
docker compose -f docker-compose.dev.yml logs -f
