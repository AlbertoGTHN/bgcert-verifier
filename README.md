# ICCBPO Certificate QR Code Checker

Enterprise-grade background check certificate validation platform for HR and Compliance teams at Interactive Contact Center (ICCBPO). Automatically verifies criminal background checks, police clearances, and government-issued certificates from multiple countries via QR code verification.

---

## Features

| Feature | Description |
|---|---|
| **Multi-file Upload** | Drag-and-drop single or bulk PDF uploads |
| **Multi-language OCR** | English, Spanish, Portuguese, French via Tesseract |
| **QR Extraction** | pyzbar + OpenCV + ZXing with rotation/quality handling |
| **Headless Verification** | Playwright visits QR URLs and screenshots the result |
| **3-Status Classification** | Verified Authentic / Failed Fraudulent / Technical Issue |
| **Fraud Detection** | Metadata, font, image tampering, copy-paste artifact analysis |
| **Report Export** | PDF, Excel, CSV with screenshots and all fields |
| **Role-Based Access** | Admin / Compliance / HR / Viewer roles |
| **Audit Logging** | Full audit trail of all actions |
| **Dark/Light Mode** | Enterprise UI with ICCBPO branding |
| **Docker Ready** | Full Docker Compose deployment |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Nginx (port 80)                      │
└──────────────┬───────────────────────────┬──────────────────┘
               │                           │
        ┌──────▼──────┐             ┌──────▼──────┐
        │  Frontend   │             │   Backend   │
        │  Next.js 14 │             │  FastAPI    │
        │  port 3000  │             │  port 8000  │
        └─────────────┘             └──────┬──────┘
                                          │
              ┌──────────┬───────────────┬┴──────────┐
              │          │               │           │
       ┌──────▼──┐ ┌────▼────┐  ┌──────▼──┐ ┌─────▼──────┐
       │PostgreSQL│ │  Redis  │  │ Celery  │ │  Playwright │
       │  DB     │ │ Cache/Q │  │ Worker  │ │  Browser    │
       └─────────┘ └─────────┘  └─────────┘ └────────────┘
```

---

## Processing Pipeline

```
1. PDF Upload
      ↓
2. PyMuPDF → High-res page images (300 DPI)
      ↓
3. Tesseract OCR → Text extraction + language detection
      ↓
4. pyzbar + OpenCV + ZXing → QR code extraction
      ↓
5. Playwright → Visit QR URL + Screenshot
      ↓
6. Keyword analysis → Domain validation → Classification
      ↓
7. Fraud detection → Metadata + font + image analysis
      ↓
8. Result: VERIFIED / FAILED / TECHNICAL ISSUE
```

---

## Quick Start

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker + Docker Compose (Linux)
- 4GB RAM minimum, 8GB recommended
- Internet access for QR URL verification

### Windows
```bat
scripts\install.bat
```

### Linux / Mac
```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### Manual
```bash
# 1. Clone / copy files
# 2. Create .env
cp .env.example .env
# Edit .env with your passwords

# 3. Create directories
mkdir uploads screenshots reports

# 4. Build and start
docker-compose build
docker-compose up -d

# 5. Check status
docker-compose ps
```

---

## Access URLs

| Service | URL |
|---|---|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **API Documentation** | http://localhost:8000/api/docs |
| **Celery Monitor** | http://localhost:5555 |



---

## Environment Variables

See `.env.example` for all configuration options. Key variables:

```env
# Required
SECRET_KEY=your-super-secret-key
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/dbname
REDIS_URL=redis://:pass@redis:6379/0

# Optional
PLAYWRIGHT_HEADLESS=true       # Set false for debugging
OCR_DPI=300                    # Higher = better but slower
FILE_RETENTION_DAYS=90         # Auto-delete uploaded files
NOTIFICATION_ENABLED=false     # Email notifications
```

---

## API Reference

### Authentication
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@iccbpo.com",
  "password": "Admin@ICCBPO2024!"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { ... }
}
```

Use the token in subsequent requests:
```http
Authorization: Bearer eyJ...
```

### Upload Certificate
```http
POST /api/v1/upload/single
Content-Type: multipart/form-data
Authorization: Bearer <token>

file: <PDF file>
```

### Bulk Upload
```http
POST /api/v1/upload/bulk
Content-Type: multipart/form-data
Authorization: Bearer <token>

files: <PDF file 1>
files: <PDF file 2>
...
```

### List Certificates
```http
GET /api/v1/certificates?status=verified_authentic&country=Colombia&page=1&size=20
Authorization: Bearer <token>
```

### Export Reports
```http
GET /api/v1/reports/export/pdf?status=verified_authentic
GET /api/v1/reports/export/excel
GET /api/v1/reports/export/csv?cert_ids=uuid1,uuid2
Authorization: Bearer <token>
```

---

## Verification Status Logic

### ✅ VERIFIED AUTHENTIC
- QR code successfully decoded
- URL reachable (HTTP 2xx)
- Domain is official (.gov, .gob, police/ministry portals)
- Page contains validation keywords: "valid", "auténtico", "sin antecedentes", etc.

### ❌ FAILED / POSSIBLY FRAUDULENT
- QR code cannot be decoded
- QR URL is unreachable / non-existent domain
- Page explicitly states certificate is invalid
- Suspicious/fake domain detected
- PDF shows strong tampering indicators

### ⚠ TECHNICAL ISSUE
- Website timeout
- CAPTCHA blocking verification
- SSL/DNS error
- Government site unavailable
- Page content unclear / unexpected structure
- Note: This does NOT mean the certificate is fraudulent!

---

## Supported Countries

Currently optimized for detection (patterns can be extended in `pdf_processor.py`):

| Country | Certificate Types |
|---|---|
| Colombia | Antecedentes judiciales (DIJÍN, SIJÍN) |
| Peru | PNP clearance |
| Mexico | Carta de no antecedentes penales |
| Chile | Registro Civil clearance |
| Brazil | Certidão antecedentes criminais |
| Argentina | Antecedentes penales |
| Philippines | NBI/PNP clearance |
| India | Police verification certificate |
| United States | FBI background check |
| United Kingdom | DBS check |

---

## Roles & Permissions

| Permission | Admin | Compliance | HR | Viewer |
|---|---|---|---|---|
| Upload certificates | ✓ | ✓ | ✓ | — |
| View own certificates | ✓ | ✓ | ✓ | ✓ |
| View all certificates | ✓ | ✓ | — | — |
| Delete certificates | ✓ | ✓ | — | — |
| Export reports | ✓ | ✓ | ✓ | — |
| Manage users | ✓ | — | — | — |
| View audit logs | ✓ | ✓ | — | — |
| Override status | ✓ | ✓ | — | — |

---

## Security

- JWT authentication with access + refresh tokens
- Bcrypt password hashing
- File validation (magic bytes check, not just extension)
- All uploads stored with UUID filenames (not original names)
- Files encrypted at rest (optional, configure `ENCRYPTION_KEY`)
- Auto-deletion after configurable retention period
- HTTPS enforcement via Nginx (configure SSL certs in `nginx/ssl/`)
- Security headers (X-Frame-Options, HSTS, CSP, etc.)
- Rate limiting on all endpoints
- MFA (TOTP) support

---

## Development Setup (Without Docker)

### Backend
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Troubleshooting

**OCR not working:**
- Ensure Tesseract is installed: `tesseract --version`
- Install language packs: `apt install tesseract-ocr-spa tesseract-ocr-por`

**QR code not detected:**
- Try increasing DPI in `.env`: `OCR_DPI=400`
- Check if document has embedded QR (not just printed)

**Verification fails for all certificates:**
- Check internet connectivity from Docker containers
- Some government sites block automated requests — classified as TECHNICAL_ISSUE (not fraud)

**Playwright/Chromium issues:**
- Run: `docker-compose exec backend playwright install chromium --with-deps`

---

## License

Proprietary — Interactive Contact Center (ICCBPO). All rights reserved.

---

*Built for ICCBPO HR and Compliance operations teams.*
