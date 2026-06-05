@echo off
echo ============================================================
echo  ICCBPO Certificate QR Code Checker - Windows Setup
echo ============================================================
echo.

:: Check for Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo Please install Docker Desktop from https://docker.com/desktop
    pause
    exit /b 1
)

:: Check for Docker Compose
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] docker-compose not found, trying 'docker compose'
)

:: Copy .env if not exists
if not exist .env (
    echo [INFO] Creating .env from template...
    copy .env.example .env
    echo [ACTION REQUIRED] Please edit .env and set your passwords before continuing!
    notepad .env
    pause
)

:: Create required directories
echo [INFO] Creating data directories...
mkdir uploads 2>nul
mkdir screenshots 2>nul
mkdir reports 2>nul

:: Build and start
echo [INFO] Building Docker containers (this may take 10-15 minutes on first run)...
docker-compose build

echo [INFO] Starting all services...
docker-compose up -d

echo.
echo [INFO] Waiting for services to initialize...
timeout /t 15 /nobreak >nul

:: Show status
docker-compose ps

echo.
echo ============================================================
echo  Setup Complete!
echo ============================================================
echo.
echo  Frontend:  http://localhost:3000
echo  Backend:   http://localhost:8000
echo  API Docs:  http://localhost:8000/api/docs
echo  Flower:    http://localhost:5555
echo.
echo  Default admin login:
echo    Email:    admin@iccbpo.com
echo    Password: Admin@ICCBPO2024!
echo.
echo  IMPORTANT: Change the admin password after first login!
echo ============================================================
pause
