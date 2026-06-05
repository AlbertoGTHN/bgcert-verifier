# ICC Background Certificate QR Code Checker
## Technical Documentation

**Version:** 1.0.0  
**Organization:** Interactive Contact Center (ICC)  
**Platform:** Web Application (Dockerized)  
**Date:** May 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Backend — FastAPI Application](#4-backend--fastapi-application)
5. [Frontend — Next.js Application](#5-frontend--nextjs-application)
6. [Certificate Validation Pipeline](#6-certificate-validation-pipeline)
7. [Database Design](#7-database-design)
8. [Authentication & Security](#8-authentication--security)
9. [Docker & Infrastructure](#9-docker--infrastructure)
10. [API Reference Summary](#10-api-reference-summary)
11. [Report Generation](#11-report-generation)
12. [Configuration Reference](#12-configuration-reference)

---

## 1. Project Overview

The ICC Background Certificate QR Code Checker is an enterprise-grade web platform built for HR and Compliance teams at Interactive Contact Center (ICC). Its purpose is to automatically validate employee background check certificates — criminal records, police clearances, and government-issued documents — from multiple countries.

### Core Capabilities

| Capability | Description |
|---|---|
| PDF Upload | Single and bulk upload (up to 50 files at once) via drag-and-drop |
| OCR Extraction | Multi-language text extraction (English, Spanish, Portuguese, French) |
| QR Code Detection | Six-strategy QR extraction handling rotated/partial/low-quality codes |
| Web Verification | Headless browser visits the QR URL and classifies the response |
| Fraud Detection | Metadata, font, ELA image analysis, and PDF structure inspection |
| Report Export | PDF, Excel, and CSV reports with color-coded status summaries |
| Role-Based Access | Admin / Compliance / HR / Viewer permission tiers |

### Validation Outcomes

The system produces exactly three classification results, chosen deliberately:

- **VERIFIED AUTHENTIC** — The QR URL was reachable and the destination page confirmed the certificate is valid.
- **FAILED / FRAUDULENT** — The destination page explicitly indicates the certificate is invalid, or fraud signals are strong.
- **TECHNICAL ISSUE** — The URL could not be reached (network error, timeout, CAPTCHA). This is intentionally *not* treated as fraud — a connectivity problem does not prove forgery.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│              http://localhost:3000                       │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Next.js Frontend (port 3000)                │
│  • React 18 + TypeScript + Tailwind CSS                  │
│  • Proxies /api/* → backend:8000 (internal Docker net)   │
└──────────────────────┬──────────────────────────────────┘
                       │  HTTP (Docker internal network)
┌──────────────────────▼──────────────────────────────────┐
│             FastAPI Backend (port 8000)                  │
│  • Python 3.11 + SQLAlchemy async                        │
│  • Background tasks (FastAPI BackgroundTasks)            │
│  • Serves /screenshots and /reports as static files      │
└────┬──────────────┬────────────────┬────────────────────┘
     │              │                │
┌────▼────┐  ┌──────▼──────┐  ┌─────▼──────┐
│PostgreSQL│  │    Redis    │  │  File      │
│(port5432)│  │ (port 6379) │  │  Storage   │
│ Data    │  │ Cache/Queue │  │ uploads/   │
│ storage │  │             │  │screenshots/│
└─────────┘  └─────────────┘  └────────────┘
```

**Key architectural decisions:**

- The Next.js server rewrites `/api/*` requests to the backend container using the internal Docker hostname `backend:8000`. The browser never calls the backend directly, eliminating CORS issues.
- File processing runs as FastAPI `BackgroundTasks` (in-process async) for the development stack, keeping the setup simple without requiring a separate Celery worker process.
- PostgreSQL stores all structured data. Uploaded PDFs, screenshots, and generated reports are stored as files on a shared Docker volume.

---

## 3. Technology Stack

### Backend

| Library | Version | Purpose |
|---|---|---|
| **FastAPI** | 0.111.0 | Async Python web framework; automatic OpenAPI docs at `/api/docs` |
| **Uvicorn** | 0.29.0 | ASGI server; runs the FastAPI app with 4 workers |
| **SQLAlchemy** | 2.0.30 | ORM for database access; uses async engine with `asyncpg` |
| **Alembic** | 1.13.1 | Database migration tool; migrations run at container startup |
| **asyncpg** | 0.29.0 | Async PostgreSQL driver used by SQLAlchemy |
| **psycopg2-binary** | 2.9.9 | Sync PostgreSQL driver used by Alembic during migrations |
| **Pydantic** | 2.7.1 | Request/response data validation and serialization |
| **pydantic-settings** | 2.2.1 | Loads app configuration from environment variables |
| **python-jose** | 3.3.0 | JWT access and refresh token creation and verification |
| **passlib + bcrypt** | 1.7.4 / 4.0.1 | Password hashing with bcrypt algorithm |
| **pyotp** | 2.9.0 | TOTP-based multi-factor authentication |
| **Celery** | 5.3.6 | Async task queue (available for production scale-out) |
| **Redis** | 5.0.4 | Message broker for Celery; also used for caching |
| **PyMuPDF (fitz)** | 1.24.3 | Renders PDF pages to high-resolution images (300 DPI) |
| **pdf2image** | 1.17.0 | Alternative PDF-to-image conversion using Poppler |
| **Pillow** | 10.3.0 | Image manipulation and preprocessing |
| **pytesseract** | 0.3.10 | Python interface to Tesseract OCR engine |
| **opencv-python-headless** | 4.9.0.80 | Image preprocessing (CLAHE, thresholding, QR detection) |
| **numpy** | 1.26.4 | Array operations used throughout image processing |
| **pyzbar** | 0.1.9 | Fast QR/barcode decoding (wraps libzbar) |
| **zxing-cpp** | 2.2.0 | Secondary QR decoder; catches codes pyzbar misses |
| **Playwright** | 1.43.0 | Chromium headless browser for visiting QR URLs |
| **httpx** | 0.27.0 | Async HTTP client for lightweight URL pre-checks |
| **beautifulsoup4** | 4.12.3 | HTML parsing of verification page content |
| **tldextract** | 5.1.2 | Domain/TLD analysis for official domain scoring |
| **reportlab** | 4.2.0 | Programmatic PDF report generation |
| **openpyxl** | 3.1.2 | Excel (.xlsx) report generation with conditional formatting |
| **loguru** | 0.7.2 | Structured application logging |
| **slowapi** | 0.1.9 | Rate limiting middleware for FastAPI |

**System-level dependencies installed in the Docker image:**

- `tesseract-ocr` + language packs: `tesseract-ocr-eng`, `tesseract-ocr-spa`, `tesseract-ocr-por`, `tesseract-ocr-fra`
- `libzbar0` — native library required by pyzbar
- `poppler-utils` — required by pdf2image
- Playwright's Chromium browser with all its OS dependencies

### Frontend

| Library | Version | Purpose |
|---|---|---|
| **Next.js** | 14.2.3 | React framework with App Router, SSR, and API proxy rewrites |
| **React** | 18.3.1 | UI component library |
| **TypeScript** | — | Static typing throughout the frontend |
| **Tailwind CSS** | 3.4.3 | Utility-first CSS; dark theme with custom ICC brand colors |
| **Zustand** | 4.5.2 | Lightweight global state management (auth store) |
| **TanStack Query** | 5.37.1 | Server state: caching, background refetch, loading states |
| **axios** | 1.7.2 | HTTP client with interceptors for auth token injection |
| **react-dropzone** | 14.2.3 | Drag-and-drop file upload zone |
| **recharts** | 2.12.7 | Charts for dashboard statistics |
| **lucide-react** | 0.378.0 | SVG icon library |
| **react-hot-toast** | 2.4.1 | Toast notification system |
| **js-cookie** | 3.0.5 | Cookie management for JWT token storage |
| **zod** | 3.23.8 | Runtime schema validation on form inputs |
| **date-fns** | 3.6.0 | Date formatting utilities |
| **clsx + tailwind-merge** | — | Conditional CSS class composition |

---

## 4. Backend — FastAPI Application

### Entry Point: `main.py`

The FastAPI application is created in `main.py` with:

- **Lifespan handler** — On startup: runs Alembic migrations (`alembic upgrade head`), calls `Base.metadata.create_all` to create any missing tables, and creates the initial admin user if none exists. On shutdown: disposes the database engine.
- **CORS middleware** — Configured with allowed origins from the `ALLOWED_ORIGINS` environment variable (JSON array format required by pydantic-settings v2).
- **Security headers middleware** — Adds `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, and `Referrer-Policy` to every response.
- **Rate limiting** — `slowapi` limits requests per IP using Redis as the backend store.
- **Static file mounts** — `/screenshots` and `/reports` URL paths are served directly from the filesystem directories.

### Configuration: `app/config.py`

`Settings` is a Pydantic `BaseSettings` class. All configuration is read from environment variables (falling back to defaults). Key settings groups:

| Group | Variables |
|---|---|
| App | `APP_ENV`, `DEBUG`, `SECRET_KEY`, `ALLOWED_ORIGINS` |
| Database | `DATABASE_URL` (async/asyncpg), `DATABASE_URL_SYNC` (sync/psycopg2 for Alembic) |
| JWT | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` |
| File Storage | `UPLOAD_DIR`, `SCREENSHOT_DIR`, `REPORTS_DIR`, `TEMP_DIR`, `MAX_FILE_SIZE_MB` |
| OCR | `TESSERACT_CMD`, `OCR_LANGUAGES`, `OCR_DPI` |
| Playwright | `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_TIMEOUT_MS` |
| Admin Seed | `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` |

### Models: `app/models/`

Three SQLAlchemy ORM models map to PostgreSQL tables:

**`User`** — Stores authentication and role data.

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| email | VARCHAR(255) | Unique index |
| hashed_password | VARCHAR(255) | bcrypt hash |
| role | ENUM | `admin`, `compliance`, `hr`, `viewer` |
| is_active | BOOLEAN | Account enabled flag |
| mfa_enabled / mfa_secret | BOOLEAN / VARCHAR | TOTP MFA fields |

**`Certificate`** — Stores all data extracted from a single PDF submission.

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| filename / original_filename | VARCHAR | Stored name vs. uploaded name |
| file_hash | VARCHAR(64) | SHA-256 of uploaded file |
| status | ENUM | `pending`, `processing`, `verified_authentic`, `failed_fraudulent`, `technical_issue`, `error` |
| ocr_text | TEXT | Full extracted text |
| qr_code_found | BOOLEAN | Whether a QR code was detected |
| qr_url | TEXT | Decoded URL from QR code |
| confidence_score | FLOAT | 0.0–1.0 verification confidence |
| fraud_score | FLOAT | 0.0–1.0 fraud likelihood score |
| fraud_indicators | JSON | Structured fraud analysis results |
| screenshot_path | VARCHAR | Path to the Playwright screenshot |
| uploaded_by_id | UUID FK | References `users.id` |

**`AuditLog`** — Append-only record of every significant action.

### Schemas: `app/schemas/`

Pydantic v2 schemas separate from ORM models define the API contract:

- `auth.py` — `LoginRequest`, `TokenResponse`, `UserResponse`
- `certificate.py` — `CertificateResponse`, `CertificateListResponse`, `CertificateSummary`

### Routes: `app/routes/`

| File | Prefix | Key Endpoints |
|---|---|---|
| `health.py` | `/` | `GET /health` — DB + Redis liveness check |
| `auth.py` | `/api/v1/auth` | `POST /login`, `POST /refresh`, `GET /me`, `POST /logout` |
| `upload.py` | `/api/v1/upload` | `POST /single`, `POST /bulk` (up to 50 PDFs) |
| `certificates.py` | `/api/v1/certificates` | `GET /` (paginated + filtered), `GET /{id}`, `DELETE /{id}`, `PATCH /{id}/notes`, `GET /summary` |
| `reports.py` | `/api/v1/reports` | `GET /export/pdf`, `GET /export/excel`, `GET /export/csv` |
| `admin.py` | `/api/v1/admin` | User CRUD, system stats, audit log retrieval |

---

## 5. Frontend — Next.js Application

### Routing Structure (App Router)

```
src/app/
├── layout.tsx              Root layout — wraps all pages with providers
├── providers.tsx           React Query + Toast provider setup
├── page.tsx                / — Redirects to /dashboard if authenticated
├── login/page.tsx          /login — Login form
├── dashboard/page.tsx      /dashboard — Stats cards + upload zone
├── certificates/
│   ├── page.tsx            /certificates — Filterable results table
│   └── [id]/page.tsx       /certificates/[id] — Full certificate detail
├── reports/page.tsx        /reports — Report generation and download
└── admin/
    ├── users/page.tsx      /admin/users — User management (admin only)
    └── audit/page.tsx      /admin/audit — Audit log viewer
```

### Key Components

**`UploadZone.tsx`**
Drag-and-drop area built with `react-dropzone`. Accepts PDF files only, max 50 MB each. After uploading, it polls the backend every 2–3 seconds for each file's status and displays a per-file progress indicator. On completion it fires a toast notification with the final result.

**`ResultsTable.tsx`**
Full data table for browsing all certificates. Features:
- Text search across filename, holder name, cert number
- Status filter (All / Verified / Failed / Technical / Pending)
- Country filter
- Pagination
- Per-row action menu: view detail, download screenshot, delete
- Multi-select checkboxes with bulk export action

**`CertificateDetail.tsx`**
Full-page detail view for a single certificate. Shows:
- Status banner with color coding
- Document info (file name, size, pages, upload date)
- Holder info extracted by OCR (name, ID, cert number, dates)
- QR code section with the decoded URL and verification outcome
- Fraud analysis panel (collapsible) with individual indicators
- Screenshot viewer with fullscreen zoom
- Inline analyst notes editor

**`StatsCards.tsx`**
Six summary cards: Total, Verified, Failed, Technical Issue, In Progress, Average Confidence. Auto-refreshes every 10 seconds using React Query.

**`Sidebar.tsx`**
Fixed left navigation (260 px wide, dark `gray-950` background). Shows the ICC logo, navigation links filtered by the user's role, and a user info / sign-out panel at the bottom.

### State Management

**Auth Store (`store/authStore.ts`)** — Zustand store with `persist` middleware.
- Stores `user` object and JWT tokens in browser cookies via `js-cookie`.
- `login()` calls `/api/v1/auth/login` and saves the returned tokens.
- `logout()` clears cookies and redirects to `/login`.
- All axios requests attach the access token via a request interceptor in `lib/api.ts`.

### API Proxy

`next.config.js` rewrites all `/api/*` requests from the browser to `http://backend:8000/api/*` on the Next.js server side. This means:
- The browser only ever contacts `localhost:3000` — no cross-origin requests.
- The backend is never exposed to the browser directly.
- The rewrite uses `BACKEND_INTERNAL_URL` (Docker internal hostname) for container-to-container communication.

---

## 6. Certificate Validation Pipeline

When a PDF is uploaded, the following steps run asynchronously as a background task:

```
PDF Upload
    │
    ▼
1. File Validation (file_utils.py)
   • Checks PDF magic bytes (%PDF-)
   • Computes SHA-256 hash
   • Saves file to /app/uploads/
    │
    ▼
2. PDF → Images (pdf_processor.py)
   • PyMuPDF renders each page at 300 DPI
   • CLAHE contrast enhancement applied
   • Adaptive thresholding for better OCR
    │
    ▼
3. OCR Text Extraction (pdf_processor.py)
   • pytesseract with --oem 3 --psm 1 (auto page segmentation)
   • Languages: eng+spa+por+fra
   • Regex patterns detect country, holder name, cert number, dates
    │
    ▼
4. QR Code Extraction (qr_extractor.py)
   • Strategy 1: pyzbar on original image
   • Strategy 2: pyzbar on preprocessed image (CLAHE + Otsu threshold)
   • Strategy 3: OpenCV QRCodeDetector
   • Strategy 4: zxing-cpp
   • Strategy 5: Regional crops (5 page sections)
   • Strategy 6: Rotations (90° / 180° / 270°)
    │
    ▼
5. Web Verification (web_verifier.py)  ← Only if QR URL found
   • Playwright launches headless Chromium
   • Visits the QR URL, waits for networkidle
   • Captures full-page screenshot
   • Extracts visible text
   • Scores against VALID_KEYWORDS and INVALID_KEYWORDS lists
   • Scores domain against official government patterns
   │
   ├─► VERIFIED_AUTHENTIC  (valid keywords + trusted domain)
   ├─► FAILED_FRAUDULENT   (invalid keywords present)
   └─► TECHNICAL_ISSUE     (timeout / connection error / CAPTCHA)
    │
    ▼
6. Fraud Detection (fraud_detector.py)
   • PDF metadata: editing tool fingerprints (Photoshop, GIMP, etc.)
   • Font analysis: >6 different fonts is suspicious
   • ELA (Error Level Analysis): detects image manipulation artifacts
   • Overlapping text blocks: indicates copy-paste forgery
   • Multiple %PDF headers: hidden embedded documents
   • JavaScript / file attachment annotations
    │
    ▼
7. Results Saved to Database
   • Certificate record updated with all extracted fields
   • Final status set
   • Audit log entry created
```

### QR Extraction Strategy Rationale

Background check certificates are often submitted as scans. QR codes may be:
- Rotated if the page was scanned sideways
- Partially obscured by a stamp or fold
- Low contrast on thermal-printed paper
- Positioned in a corner that simple decoders miss

Using six sequential strategies with image preprocessing ensures maximum extraction rate before concluding no QR code is present.

---

## 7. Database Design

### PostgreSQL Schema

The database is managed by **Alembic** (migration `001_initial_schema.py`). Migrations run automatically at container startup before the application starts.

```sql
-- Enum types
CREATE TYPE userrole AS ENUM ('admin', 'compliance', 'hr', 'viewer');
CREATE TYPE validationstatus AS ENUM (
    'pending', 'processing', 'verified_authentic',
    'failed_fraudulent', 'technical_issue', 'error'
);
CREATE TYPE certificatetype AS ENUM (
    'criminal_background', 'police_clearance',
    'government_clearance', 'court_record', 'unknown'
);

-- Tables
users            -- Authentication and roles
certificates     -- All certificate data and results
audit_logs       -- Immutable action history
```

**Important:** SQLAlchemy ORM models use `values_callable=lambda x: [e.value for e in x]` and `create_type=False` on all `Enum()` column definitions. This ensures the ORM uses the lowercase string values (e.g., `"admin"`) that match the PostgreSQL enum, rather than the Python member names (e.g., `"ADMIN"`).

### Indexes

- `ix_users_email` — Unique index on `users.email`
- `ix_certificates_status` — Index on `certificates.status` for dashboard queries
- `ix_certificates_job_id` — Index on `certificates.job_id` for background task polling

---

## 8. Authentication & Security

### JWT Token Flow

```
1. POST /api/v1/auth/login  { email, password }
        ↓
2. Backend verifies bcrypt hash
        ↓
3. Returns { access_token, refresh_token, user }
        ↓
4. Frontend stores tokens in cookies (js-cookie)
        ↓
5. Every API request includes: Authorization: Bearer <access_token>
        ↓
6. get_current_user() dependency decodes JWT, queries DB for user
```

- Access tokens expire in 60 minutes.
- Refresh tokens expire in 7 days.
- Each token includes a `jti` (JWT ID) UUID for future revocation support.

### Role-Based Access Control

| Role | Capabilities |
|---|---|
| **Admin** | Full access — user management, all certificates, audit logs, system config |
| **Compliance** | View all certificates, access audit logs, generate reports |
| **HR** | Upload certificates, view own uploads, generate reports |
| **Viewer** | Read-only access to certificates and reports |

The `require_role(*roles)` dependency factory is applied to routes that need restricted access:

```python
@router.get("/admin/users")
async def list_users(current_user=Depends(require_role("admin"))):
    ...
```

### Password Security

- Passwords are hashed with **bcrypt** (cost factor 12).
- `passlib[bcrypt]` v1.7.4 is pinned with `bcrypt==4.0.1` specifically because passlib's internal `detect_wrap_bug` test is incompatible with bcrypt 4.2+.
- The initial admin user is seeded on first startup from `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables.

### File Security

- Uploaded files are validated against PDF magic bytes (`%PDF-`) before being accepted.
- Each file's SHA-256 hash is computed and stored for integrity verification.
- Files are stored with UUID-based names on disk, not the original filename.

---

## 9. Docker & Infrastructure

### Development Stack (`docker-compose.dev.yml`)

Four containers, no Nginx or Celery worker, designed for fast startup:

| Container | Image | Port | Purpose |
|---|---|---|---|
| `iccbpo_postgres` | postgres:15-alpine | 5432 | Persistent database |
| `iccbpo_redis` | redis:7-alpine | 6379 | Cache and task queue |
| `iccbpo_backend` | Built from `backend/Dockerfile` | 8000 | FastAPI API server |
| `iccbpo_frontend` | Built from `frontend/Dockerfile.dev` | 3000 | Next.js dev server |

### Backend Dockerfile

```dockerfile
FROM python:3.11-slim-bookworm

# System packages: Tesseract OCR + 4 language packs, libzbar0,
# Poppler, OpenCV dependencies, build tools, PostgreSQL client libs

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .
RUN mkdir -p /app/uploads /app/screenshots /app/reports /app/temp

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"]
```

### Frontend Dockerfile (Dev)

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
COPY . .
EXPOSE 3000
ENV HOSTNAME=0.0.0.0
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
```

`--legacy-peer-deps` is required because there is no `package-lock.json` in the repository.

### Startup Scripts

`START.bat` — Windows one-click launcher:
1. Checks if Docker Desktop is running (calls `docker info`); if not, launches it and waits.
2. Creates `uploads/`, `screenshots/`, and `reports/` directories if missing.
3. Runs `docker compose -f docker-compose.dev.yml up --build -d`.
4. Waits 10 seconds, then opens `http://localhost:3000` in the browser.

`STOP.bat` — Runs `docker compose -f docker-compose.dev.yml down` (preserves data volumes).

### Data Persistence

- **PostgreSQL data** — Stored in Docker named volume `postgres_data`. Survives container restarts and `docker compose down`.
- **Uploaded PDFs, screenshots, reports** — Bind-mounted from the project root (`./uploads`, `./screenshots`, `./reports`). Accessible directly on the host filesystem.

---

## 10. API Reference Summary

The full interactive API documentation is available at **http://localhost:8000/api/docs** (Swagger UI) while the application is running.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Email/password login, returns JWT tokens |
| POST | `/api/v1/auth/refresh` | Exchange refresh token for new access token |
| GET | `/api/v1/auth/me` | Get current user profile |
| POST | `/api/v1/auth/logout` | Invalidate session |

### Certificate Upload

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/upload/single` | Upload one PDF, returns certificate ID |
| POST | `/api/v1/upload/bulk` | Upload up to 50 PDFs, returns list of IDs |

### Certificates

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/certificates/` | List with pagination, status/country/search filters |
| GET | `/api/v1/certificates/summary` | Dashboard counts by status |
| GET | `/api/v1/certificates/{id}` | Full certificate detail |
| PATCH | `/api/v1/certificates/{id}/notes` | Update analyst notes |
| DELETE | `/api/v1/certificates/{id}` | Delete certificate and files |

### Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/reports/export/pdf` | Generate and download PDF report |
| GET | `/api/v1/reports/export/excel` | Generate and download Excel report |
| GET | `/api/v1/reports/export/csv` | Generate and download CSV report |

All report endpoints accept optional query parameters: `cert_ids`, `status`, `country`, `date_from`, `date_to`.

---

## 11. Report Generation

Reports are generated synchronously when requested and streamed back as file downloads.

### PDF Report (`reportlab`)

- Landscape A4 format
- Cover page with ICC branding, generation timestamp, and filter criteria
- Summary table: total counts by status with color coding
- Main data table: one row per certificate with columns for file name, holder, country, status (color-coded cell), confidence score, QR URL, and processing date
- Status colors: green (verified), red (failed), orange (technical issue), grey (pending)

### Excel Report (`openpyxl`)

- One worksheet per report
- Header row with auto-filter and frozen panes
- Conditional cell fill colors matching status
- Auto-sized columns
- Separate columns for all extracted fields

### CSV Report

- Plain UTF-8 CSV with all certificate fields
- Compatible with Excel, Google Sheets, and data analysis tools

---

## 12. Configuration Reference

All configuration is injected via environment variables in `docker-compose.dev.yml`. No `.env` file is required for development — defaults are hardcoded in the compose file.

| Variable | Default (dev) | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB URL for SQLAlchemy |
| `DATABASE_URL_SYNC` | `postgresql://...` | Sync DB URL for Alembic |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `SECRET_KEY` | *(dev key)* | App secret; **change in production** |
| `JWT_SECRET_KEY` | *(dev key)* | JWT signing key; **change in production** |
| `ALLOWED_ORIGINS` | `["http://localhost:3000",...]` | JSON array of allowed CORS origins |
| `ADMIN_EMAIL` | `admin@iccbpo.com` | Seed admin email |
| `ADMIN_PASSWORD` | `Admin@ICCBPO2024!` | Seed admin password |
| `OCR_LANGUAGES` | `eng+spa+por+fra` | Tesseract language string |
| `PLAYWRIGHT_HEADLESS` | `true` | Run Chromium headlessly in Docker |
| `UPLOAD_DIR` | `/app/uploads` | Container path for uploaded PDFs |
| `SCREENSHOT_DIR` | `/app/screenshots` | Container path for Playwright screenshots |
| `MAX_FILE_SIZE_MB` | `50` | Maximum single file upload size |
| `DEBUG` | `true` | Enables debug mode and verbose logging |

---

*Document generated for Interactive Contact Center (ICC) internal technical reference.*
