"""
Certificate Processing Orchestrator
Coordinates the full pipeline: PDF → OCR → QR → Web Verify → Fraud Detect
"""
import os
import time
import asyncio
import hashlib
import shutil
from datetime import datetime
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.certificate import Certificate, ValidationStatus
from app.services.pdf_processor import PDFProcessor
from app.services.qr_extractor import QRExtractor
from app.services.web_verifier import WebVerifier
from app.services.fraud_detector import FraudDetector
from app.services.internal_analyzer import InternalAnalyzer

# Error codes that indicate the remote site was simply unreachable (not a
# content issue).  For these we activate the internal analysis fallback.
CONNECTIVITY_ERRORS = frozenset({
    "DNS_ERROR", "TIMEOUT", "CONNECTION_ERROR",
    "SSL_ERROR", "BROWSER_ERROR", "NAVIGATION_ERROR",
})


class CertificateProcessor:
    """Orchestrates the complete certificate verification pipeline."""

    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.qr_extractor = QRExtractor()
        self.web_verifier = WebVerifier()
        self.fraud_detector = FraudDetector()
        self.internal_analyzer = InternalAnalyzer()

    async def process(self, cert_id: UUID, file_path: str, db: AsyncSession):
        """Full async processing pipeline."""
        start_time = time.time()
        temp_dir = os.path.join(settings.TEMP_DIR, str(cert_id))
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # Update status to PROCESSING
            cert = await db.get(Certificate, cert_id)
            if not cert:
                logger.error(f"Certificate {cert_id} not found")
                return

            cert.status = ValidationStatus.PROCESSING
            await db.commit()

            logger.info(f"Processing certificate {cert_id}: {cert.original_filename}")

            # ── Step 1: PDF Processing & OCR ────────────────────────────
            logger.info(f"[{cert_id}] Step 1: PDF processing and OCR")
            pdf_result = self.pdf_processor.process(file_path, temp_dir)

            if pdf_result.error:
                cert.status = ValidationStatus.ERROR
                cert.error_details = f"PDF processing failed: {pdf_result.error}"
                cert.error_code = "PDF_ERROR"
                await db.commit()
                return

            # Update certificate with OCR results
            cert.page_count = pdf_result.page_count
            cert.ocr_text = pdf_result.full_text[:50000] if pdf_result.full_text else None
            cert.ocr_confidence = pdf_result.avg_ocr_confidence
            cert.language_detected = pdf_result.language
            cert.country = pdf_result.country
            cert.cert_type = pdf_result.cert_type
            cert.holder_name = pdf_result.holder_name
            cert.holder_id = pdf_result.holder_id
            cert.cert_number = pdf_result.cert_number
            cert.issue_date = pdf_result.issue_date
            cert.expiry_date = pdf_result.expiry_date
            cert.issuing_authority = pdf_result.issuing_authority
            cert.metadata = pdf_result.metadata

            # ── Step 2: QR Code Extraction ───────────────────────────────
            logger.info(f"[{cert_id}] Step 2: QR code extraction")
            page_images = [p.image_path for p in pdf_result.pages]
            qr_result = self.qr_extractor.extract_from_images(page_images)

            if qr_result:
                cert.qr_code_found = True
                cert.qr_code_data = qr_result.data
                cert.qr_url = qr_result.url
                cert.qr_page_number = qr_result.page_num
            else:
                cert.qr_code_found = False

            # ── Step 3: Web Verification ─────────────────────────────────
            if cert.qr_code_found and cert.qr_url:
                logger.info(f"[{cert_id}] Step 3: Web verification of {cert.qr_url[:60]}")
                verification = await self.web_verifier.verify(
                    cert.qr_url,
                    str(cert_id),
                    holder_name=cert.holder_name,
                    holder_id=cert.holder_id,
                )

                cert.status = self._map_status(verification.status)
                cert.confidence_score = verification.confidence
                cert.verification_url = verification.final_url or cert.qr_url
                cert.verification_domain = verification.domain
                cert.is_official_domain = verification.is_official_domain
                cert.verification_text = verification.page_text[:5000] if verification.page_text else None
                cert.validation_result = verification.validation_summary
                cert.screenshot_path = verification.screenshot_path
                cert.screenshot_url = verification.screenshot_url
                cert.error_details = verification.error
                cert.error_code = verification.error_code

                # ── Country fallback from verification domain ─────────────
                if not cert.country and verification.domain:
                    inferred = self.pdf_processor.detect_country_from_domain(
                        verification.domain
                    )
                    if inferred:
                        cert.country = inferred
                        logger.info(
                            f"[{cert_id}] Country inferred from domain "
                            f"'{verification.domain}' → {inferred}"
                        )

                # ── Internal Analysis fallback ────────────────────────────
                # If the site was unreachable, run an offline document check
                # and potentially upgrade TECHNICAL_ISSUE → VERIFIED_INTERNAL.
                if (cert.status == ValidationStatus.TECHNICAL_ISSUE and
                        verification.error_code in CONNECTIVITY_ERRORS):
                    logger.info(
                        f"[{cert_id}] External site unreachable "
                        f"({verification.error_code}), running internal analysis"
                    )
                    analysis = self.internal_analyzer.analyze(
                        holder_name=cert.holder_name,
                        holder_id=cert.holder_id,
                        cert_number=cert.cert_number,
                        issue_date=cert.issue_date,
                        expiry_date=cert.expiry_date,
                        issuing_authority=cert.issuing_authority,
                        country=cert.country,
                        language_detected=cert.language_detected,
                        ocr_confidence=cert.ocr_confidence,
                        ocr_text=cert.ocr_text,
                        fraud_score=cert.fraud_score if cert.fraud_score else 0.0,
                        qr_url=cert.qr_url,
                        error_code=verification.error_code,
                    )
                    logger.info(
                        f"[{cert_id}] Internal analysis: "
                        f"{analysis.status} (score={analysis.weighted_score:.3f})"
                    )
                    if analysis.status == "VERIFIED_INTERNAL":
                        cert.status = ValidationStatus.VERIFIED_INTERNAL
                        cert.confidence_score = analysis.confidence
                    elif analysis.status == "FAILED_FRAUDULENT":
                        cert.status = ValidationStatus.FAILED_FRAUDULENT
                        cert.confidence_score = analysis.confidence
                    # Append internal analysis summary to validation_result
                    cert.validation_result = (
                        f"{cert.validation_result or ''}\n\n"
                        f"[Internal Analysis] {analysis.summary}"
                    ).strip()
            else:
                # No QR code found — this could mean the document has no QR or it couldn't be read
                if pdf_result.full_text and len(pdf_result.full_text.strip()) > 50:
                    cert.status = ValidationStatus.TECHNICAL_ISSUE
                    cert.confidence_score = 0.0
                    cert.validation_result = "No QR code found in document. Unable to verify authenticity automatically."
                    cert.error_code = "NO_QR_CODE"
                else:
                    cert.status = ValidationStatus.TECHNICAL_ISSUE
                    cert.confidence_score = 0.0
                    cert.validation_result = "Could not extract text or QR code from document. File may be corrupt or image quality too low."
                    cert.error_code = "EXTRACTION_FAILED"

            # ── Step 4: Fraud Detection ──────────────────────────────────
            logger.info(f"[{cert_id}] Step 4: Fraud detection")
            fraud_result = self.fraud_detector.analyze(file_path, page_images)

            cert.fraud_indicators = fraud_result.indicators
            cert.fraud_score = fraud_result.fraud_score
            cert.is_potentially_fraudulent = fraud_result.is_potentially_fraudulent

            # If fraud detected and status was going to be VERIFIED, downgrade to TECHNICAL_ISSUE
            if (cert.is_potentially_fraudulent and
                    cert.status in (ValidationStatus.VERIFIED_AUTHENTIC,
                                    ValidationStatus.VERIFIED_INTERNAL) and
                    cert.confidence_score < 0.9):
                cert.status = ValidationStatus.TECHNICAL_ISSUE
                cert.validation_result = (
                    f"{cert.validation_result or ''} "
                    f"WARNING: Document tampering indicators detected. Manual review required."
                ).strip()
                cert.confidence_score = max(0.0, cert.confidence_score - 0.3)

            # ── Finalize ─────────────────────────────────────────────────
            cert.processed_at = datetime.utcnow()
            cert.processing_time_seconds = time.time() - start_time

            await db.commit()
            logger.info(
                f"[{cert_id}] Processing complete in {cert.processing_time_seconds:.2f}s "
                f"→ {cert.status.value} (confidence: {cert.confidence_score:.2f})"
            )

        except Exception as e:
            logger.error(f"Processing error for cert {cert_id}: {e}", exc_info=True)
            try:
                cert = await db.get(Certificate, cert_id)
                if cert:
                    cert.status = ValidationStatus.ERROR
                    cert.error_details = str(e)
                    cert.error_code = "INTERNAL_ERROR"
                    cert.processed_at = datetime.utcnow()
                    cert.processing_time_seconds = time.time() - start_time
                    await db.commit()
            except Exception:
                pass
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _map_status(verification_status: str) -> ValidationStatus:
        mapping = {
            "VERIFIED_AUTHENTIC": ValidationStatus.VERIFIED_AUTHENTIC,
            "VERIFIED_INTERNAL": ValidationStatus.VERIFIED_INTERNAL,
            "FAILED_FRAUDULENT": ValidationStatus.FAILED_FRAUDULENT,
            "TECHNICAL_ISSUE": ValidationStatus.TECHNICAL_ISSUE,
        }
        return mapping.get(verification_status, ValidationStatus.TECHNICAL_ISSUE)
