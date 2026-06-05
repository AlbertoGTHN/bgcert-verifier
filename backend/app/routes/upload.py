"""Upload routes — handle single and bulk PDF uploads."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.models.certificate import Certificate, ValidationStatus
from app.models.user import User
from app.schemas.certificate import CertificateResponse
from app.utils.security import get_current_user
from app.utils.file_utils import save_upload
from app.config import settings

router = APIRouter()


async def _process_in_background(cert_id: uuid.UUID, file_path: str):
    """Launch certificate processing as a background task."""
    from app.services.certificate_processor import CertificateProcessor
    from app.database import AsyncSessionLocal

    processor = CertificateProcessor()
    async with AsyncSessionLocal() as db:
        await processor.process(cert_id, file_path, db)


@router.post("/single", response_model=CertificateResponse, status_code=202)
async def upload_single(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single PDF certificate for verification."""
    file_meta = await save_upload(file, settings.UPLOAD_DIR)

    cert = Certificate(
        filename=file_meta["filename"],
        original_filename=file_meta["original_filename"],
        file_path=file_meta["file_path"],
        file_size=file_meta["file_size"],
        file_hash=file_meta["file_hash"],
        status=ValidationStatus.PENDING,
        uploaded_by_id=current_user.id,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)

    # Queue background processing
    background_tasks.add_task(
        _process_in_background,
        cert.id,
        cert.file_path,
    )

    logger.info(f"Certificate queued: {cert.id} ({cert.original_filename}) by {current_user.email}")

    return _to_response(cert, current_user)


@router.post("/bulk", response_model=List[CertificateResponse], status_code=202)
async def upload_bulk(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple PDF certificates for bulk verification."""
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch")

    responses = []
    for file in files:
        try:
            file_meta = await save_upload(file, settings.UPLOAD_DIR)
            cert = Certificate(
                filename=file_meta["filename"],
                original_filename=file_meta["original_filename"],
                file_path=file_meta["file_path"],
                file_size=file_meta["file_size"],
                file_hash=file_meta["file_hash"],
                status=ValidationStatus.PENDING,
                uploaded_by_id=current_user.id,
            )
            db.add(cert)
            await db.flush()

            background_tasks.add_task(
                _process_in_background,
                cert.id,
                cert.file_path,
            )

            responses.append(_to_response(cert, current_user))
            logger.info(f"Bulk: queued {cert.id} ({cert.original_filename})")

        except HTTPException as e:
            logger.warning(f"Skipping {file.filename}: {e.detail}")
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")

    await db.commit()
    return responses


def _to_response(cert: Certificate, user: User) -> CertificateResponse:
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
        uploader_name=user.name,
    )
