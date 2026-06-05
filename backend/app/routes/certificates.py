"""Certificate management routes."""
import uuid
import math
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.certificate import Certificate, ValidationStatus
from app.models.user import User
from app.schemas.certificate import (
    CertificateResponse, CertificateListResponse,
    CertificateUpdate, ValidationSummary,
)
from app.utils.security import get_current_user

router = APIRouter()


@router.get("", response_model=CertificateListResponse)
async def list_certificates(
    status: Optional[ValidationStatus] = Query(None),
    country: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List certificates with filtering and pagination."""
    query = select(Certificate)

    # Non-admin users only see their own uploads
    from app.models.user import UserRole
    if current_user.role not in (UserRole.ADMIN, UserRole.COMPLIANCE):
        query = query.where(Certificate.uploaded_by_id == current_user.id)

    # Filters
    if status:
        query = query.where(Certificate.status == status)
    if country:
        query = query.where(Certificate.country.ilike(f"%{country}%"))
    if date_from:
        query = query.where(Certificate.uploaded_at >= date_from)
    if date_to:
        query = query.where(Certificate.uploaded_at <= date_to)
    if search:
        query = query.where(or_(
            Certificate.original_filename.ilike(f"%{search}%"),
            Certificate.holder_name.ilike(f"%{search}%"),
            Certificate.cert_number.ilike(f"%{search}%"),
            Certificate.country.ilike(f"%{search}%"),
        ))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * size
    query = query.order_by(Certificate.uploaded_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    certificates = result.scalars().all()

    items = [_to_response(cert) for cert in certificates]

    return CertificateListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get("/summary", response_model=ValidationSummary)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get validation statistics summary."""
    from app.models.user import UserRole
    base = select(Certificate)
    if current_user.role not in (UserRole.ADMIN, UserRole.COMPLIANCE):
        base = base.where(Certificate.uploaded_by_id == current_user.id)

    result = await db.execute(base)
    certs = result.scalars().all()

    total = len(certs)
    scores = [c.confidence_score for c in certs if c.confidence_score and c.confidence_score > 0]
    countries = list(set(c.country for c in certs if c.country))

    return ValidationSummary(
        total=total,
        verified_authentic=sum(1 for c in certs if c.status == ValidationStatus.VERIFIED_AUTHENTIC),
        verified_internal=sum(1 for c in certs if c.status == ValidationStatus.VERIFIED_INTERNAL),
        failed_fraudulent=sum(1 for c in certs if c.status == ValidationStatus.FAILED_FRAUDULENT),
        technical_issue=sum(1 for c in certs if c.status == ValidationStatus.TECHNICAL_ISSUE),
        pending=sum(1 for c in certs if c.status == ValidationStatus.PENDING),
        processing=sum(1 for c in certs if c.status == ValidationStatus.PROCESSING),
        error=sum(1 for c in certs if c.status == ValidationStatus.ERROR),
        avg_confidence=sum(scores) / len(scores) if scores else 0.0,
        countries=sorted(countries),
    )


@router.get("/{cert_id}", response_model=CertificateResponse)
async def get_certificate(
    cert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cert = await _get_cert_or_404(cert_id, current_user, db)
    return _to_response(cert)


@router.patch("/{cert_id}", response_model=CertificateResponse)
async def update_certificate(
    cert_id: uuid.UUID,
    body: CertificateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cert = await _get_cert_or_404(cert_id, current_user, db)

    if body.analyst_notes is not None:
        cert.analyst_notes = body.analyst_notes

    from app.models.user import UserRole
    if body.status is not None and current_user.role in (UserRole.ADMIN, UserRole.COMPLIANCE):
        cert.status = body.status

    await db.commit()
    await db.refresh(cert)
    return _to_response(cert)


@router.delete("/{cert_id}", status_code=204)
async def delete_certificate(
    cert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import UserRole
    cert = await _get_cert_or_404(cert_id, current_user, db)

    if current_user.role not in (UserRole.ADMIN, UserRole.COMPLIANCE):
        raise HTTPException(status_code=403, detail="Insufficient permissions to delete certificates")

    # Delete associated files
    import os
    from app.utils.file_utils import safe_delete
    safe_delete(cert.file_path)
    if cert.screenshot_path:
        safe_delete(cert.screenshot_path)

    await db.delete(cert)
    await db.commit()


@router.post("/{cert_id}/reprocess", response_model=CertificateResponse)
async def reprocess_certificate(
    cert_id: uuid.UUID,
    background_tasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run verification on a certificate."""
    from fastapi import BackgroundTasks
    cert = await _get_cert_or_404(cert_id, current_user, db)

    if not os.path.exists(cert.file_path):
        raise HTTPException(status_code=404, detail="Original file no longer available")

    cert.status = ValidationStatus.PENDING
    await db.commit()

    from app.routes.upload import _process_in_background
    background_tasks.add_task(_process_in_background, cert.id, cert.file_path)

    return _to_response(cert)


async def _get_cert_or_404(cert_id, current_user, db) -> Certificate:
    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    from app.models.user import UserRole
    if (current_user.role not in (UserRole.ADMIN, UserRole.COMPLIANCE) and
            cert.uploaded_by_id != current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return cert


def _to_response(cert: Certificate) -> CertificateResponse:
    uploader_name = None
    if cert.uploader:
        uploader_name = cert.uploader.name

    return CertificateResponse(
        id=cert.id,
        filename=cert.filename,
        original_filename=cert.original_filename,
        file_size=cert.file_size,
        page_count=cert.page_count,
        country=cert.country,
        language_detected=cert.language_detected,
        cert_type=cert.cert_type,
        holder_name=cert.holder_name,
        holder_id=cert.holder_id,
        cert_number=cert.cert_number,
        issue_date=cert.issue_date,
        expiry_date=cert.expiry_date,
        issuing_authority=cert.issuing_authority,
        qr_code_found=cert.qr_code_found,
        qr_code_data=cert.qr_code_data,
        qr_url=cert.qr_url,
        status=cert.status,
        validation_result=cert.validation_result,
        confidence_score=cert.confidence_score,
        verification_url=cert.verification_url,
        verification_domain=cert.verification_domain,
        is_official_domain=cert.is_official_domain,
        verification_text=cert.verification_text,
        screenshot_url=cert.screenshot_url,
        error_details=cert.error_details,
        error_code=cert.error_code,
        fraud_indicators=cert.fraud_indicators,
        fraud_score=cert.fraud_score,
        is_potentially_fraudulent=cert.is_potentially_fraudulent,
        processing_time_seconds=cert.processing_time_seconds,
        analyst_notes=cert.analyst_notes,
        uploaded_at=cert.uploaded_at,
        processed_at=cert.processed_at,
        uploaded_by_id=cert.uploaded_by_id,
        uploader_name=uploader_name,
    )
