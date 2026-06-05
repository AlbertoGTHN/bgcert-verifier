"""Certificate schemas."""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.certificate import ValidationStatus, CertificateType


class CertificateBase(BaseModel):
    original_filename: str
    analyst_notes: Optional[str] = None


class CertificateCreate(CertificateBase):
    pass


class CertificateUpdate(BaseModel):
    analyst_notes: Optional[str] = None
    status: Optional[ValidationStatus] = None


class FraudIndicators(BaseModel):
    pdf_metadata_tampered: bool = False
    font_inconsistency: bool = False
    image_tampering: bool = False
    duplicate_qr: bool = False
    suspicious_formatting: bool = False
    qr_country_mismatch: bool = False
    edited_pdf: bool = False
    details: Dict[str, Any] = {}


class CertificateResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    page_count: int

    # Document info
    country: Optional[str] = None
    language_detected: Optional[str] = None
    cert_type: CertificateType

    # Person info
    holder_name: Optional[str] = None
    holder_id: Optional[str] = None
    cert_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None

    # QR
    qr_code_found: bool
    qr_code_data: Optional[str] = None
    qr_url: Optional[str] = None

    # Verification
    status: ValidationStatus
    validation_result: Optional[str] = None
    confidence_score: float
    verification_url: Optional[str] = None
    verification_domain: Optional[str] = None
    is_official_domain: Optional[bool] = None
    verification_text: Optional[str] = None
    screenshot_url: Optional[str] = None

    # Errors
    error_details: Optional[str] = None
    error_code: Optional[str] = None

    # Fraud
    fraud_indicators: Optional[Dict[str, Any]] = None
    fraud_score: float
    is_potentially_fraudulent: bool

    # Processing
    processing_time_seconds: Optional[float] = None

    # Notes
    analyst_notes: Optional[str] = None

    # Timestamps
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    # Uploader
    uploaded_by_id: Optional[uuid.UUID] = None
    uploader_name: Optional[str] = None

    model_config = {"from_attributes": True}


class CertificateListResponse(BaseModel):
    items: List[CertificateResponse]
    total: int
    page: int
    size: int
    pages: int


class CertificateFilterParams(BaseModel):
    status: Optional[ValidationStatus] = None
    country: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class ValidationSummary(BaseModel):
    total: int
    verified_authentic: int
    verified_internal: int = 0
    failed_fraudulent: int
    technical_issue: int
    pending: int
    processing: int
    error: int
    avg_confidence: float
    countries: List[str]
