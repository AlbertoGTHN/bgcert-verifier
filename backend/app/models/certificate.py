"""Certificate model."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, Enum, Float, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class ValidationStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    VERIFIED_AUTHENTIC = "verified_authentic"
    VERIFIED_INTERNAL = "verified_internal"   # approved by internal document analysis
    FAILED_FRAUDULENT = "failed_fraudulent"
    TECHNICAL_ISSUE = "technical_issue"
    ERROR = "error"


class CertificateType(str, PyEnum):
    CRIMINAL_BACKGROUND = "criminal_background"
    POLICE_CLEARANCE = "police_clearance"
    GOVERNMENT_CLEARANCE = "government_clearance"
    COURT_RECORD = "court_record"
    UNKNOWN = "unknown"


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # File info
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    # Document analysis
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language_detected: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cert_type: Mapped[CertificateType] = mapped_column(
        Enum(CertificateType, values_callable=lambda x: [e.value for e in x], create_type=False),
        default=CertificateType.UNKNOWN
    )

    # Person info extracted by OCR
    holder_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    holder_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cert_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # OCR results
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # QR code
    qr_code_found: Mapped[bool] = mapped_column(Boolean, default=False)
    qr_code_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Verification
    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, values_callable=lambda x: [e.value for e in x], create_type=False),
        default=ValidationStatus.PENDING, index=True
    )
    validation_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    verification_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_domain: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_official_domain: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verification_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    screenshot_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Error details
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Fraud detection
    fraud_indicators: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_potentially_fraudulent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Processing metadata
    processing_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Analyst notes
    analyst_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Foreign keys
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    uploader: Mapped["User | None"] = relationship("User", back_populates="certificates")

    def __repr__(self) -> str:
        return f"<Certificate {self.original_filename} ({self.status})>"

    @property
    def status_color(self) -> str:
        color_map = {
            ValidationStatus.VERIFIED_AUTHENTIC: "green",
            ValidationStatus.VERIFIED_INTERNAL: "teal",
            ValidationStatus.FAILED_FRAUDULENT: "red",
            ValidationStatus.TECHNICAL_ISSUE: "yellow",
            ValidationStatus.PENDING: "gray",
            ValidationStatus.PROCESSING: "blue",
            ValidationStatus.ERROR: "red",
        }
        return color_map.get(self.status, "gray")
