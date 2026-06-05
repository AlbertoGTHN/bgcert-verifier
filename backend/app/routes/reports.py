"""Report generation and download routes."""
import uuid
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models.certificate import Certificate, ValidationStatus
from app.models.user import User, UserRole
from app.services.report_generator import ReportGenerator
from app.utils.security import get_current_user

router = APIRouter()
generator = ReportGenerator()


async def _get_certs_for_export(
    db: AsyncSession,
    current_user: User,
    cert_ids: Optional[List[uuid.UUID]],
    status: Optional[ValidationStatus],
    country: Optional[str],
) -> List[Certificate]:
    """Fetch certificates for export based on filters."""
    query = select(Certificate)

    if current_user.role not in (UserRole.ADMIN, UserRole.COMPLIANCE):
        query = query.where(Certificate.uploaded_by_id == current_user.id)

    if cert_ids:
        query = query.where(Certificate.id.in_(cert_ids))
    if status:
        query = query.where(Certificate.status == status)
    if country:
        query = query.where(Certificate.country.ilike(f"%{country}%"))

    result = await db.execute(query.order_by(Certificate.uploaded_at.desc()))
    return list(result.scalars().all())


@router.get("/export/pdf")
async def export_pdf(
    cert_ids: Optional[str] = Query(None, description="Comma-separated certificate IDs"),
    status: Optional[ValidationStatus] = Query(None),
    country: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export validation report as PDF."""
    ids = _parse_ids(cert_ids)
    certificates = await _get_certs_for_export(db, current_user, ids, status, country)

    if not certificates:
        raise HTTPException(status_code=404, detail="No certificates found matching filters")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"iccbpo_report_{timestamp}.pdf"

    try:
        filepath = generator.generate_pdf(certificates, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/excel")
async def export_excel(
    cert_ids: Optional[str] = Query(None),
    status: Optional[ValidationStatus] = Query(None),
    country: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export validation report as Excel."""
    ids = _parse_ids(cert_ids)
    certificates = await _get_certs_for_export(db, current_user, ids, status, country)

    if not certificates:
        raise HTTPException(status_code=404, detail="No certificates found matching filters")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"iccbpo_report_{timestamp}.xlsx"

    try:
        filepath = generator.generate_excel(certificates, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}")

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@router.get("/export/csv")
async def export_csv(
    cert_ids: Optional[str] = Query(None),
    status: Optional[ValidationStatus] = Query(None),
    country: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export validation report as CSV."""
    ids = _parse_ids(cert_ids)
    certificates = await _get_certs_for_export(db, current_user, ids, status, country)

    if not certificates:
        raise HTTPException(status_code=404, detail="No certificates found matching filters")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"iccbpo_report_{timestamp}.csv"

    try:
        filepath = generator.generate_csv(certificates, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV generation failed: {e}")

    return FileResponse(
        filepath,
        media_type="text/csv",
        filename=filename,
    )


def _parse_ids(cert_ids_str: Optional[str]) -> Optional[List[uuid.UUID]]:
    if not cert_ids_str:
        return None
    try:
        return [uuid.UUID(id.strip()) for id in cert_ids_str.split(",") if id.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid certificate ID format")
