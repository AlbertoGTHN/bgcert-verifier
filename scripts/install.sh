#!/bin/bash
set -e

echo "============================================================"
echo " ICCBPO Certificate QR Code Checker - Linux/Mac Setup"
echo "============================================================"
echo

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed."
    echo "Install: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "[ERROR] Docker Compose not found."
    exit 1
fi

COMPOSE_CMD="docker compose"
command -v docker-compose &> /dev/null && COMPOSE_CMD="docker-compose"

# Copy .env
if [ ! -f .env ]; then
    echo "[INFO] Creating .env from template..."
    cp .env.example .env
    echo "[IMPORTANT] Edit .env with your secure passwords before proceeding!"
    echo "Press Enter after editing .env..."
    read -r
fi

# Create directories
echo "[INFO] Creating data directories..."
mkdir -p uploads screenshots reports

# Set permissions
chmod 755 uploads screenshots reports

# Build
echo "[INFO] Building Docker images (first run: 10-15 min)..."
$COMPOSE_CMD build

# Start
echo "[INFO] Starting services..."
$COMPOSE_CMD up -d

echo "[INFO] Waiting for services..."
sleep 15

$COMPOSE_CMD ps

echo
echo "============================================================"
echo " Setup Complete!"
echo "============================================================"
echo
echo " Frontend:  http://localhost:3000"
echo " Backend:   http://localhost:8000"
echo " API Docs:  http://localhost:8000/api/docs"
echo " Flower:    http://localhost:5555"
echo
echo " Default admin:"
echo "   Email:    admin@iccbpo.com"
echo "   Password: Admin@ICCBPO2024!"
echo
echo " IMPORTANT: Change the admin password after first login!"
echo "============================================================"
