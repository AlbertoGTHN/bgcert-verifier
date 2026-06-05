"""Authentication routes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.schemas.auth import (
    LoginRequest, TokenResponse, UserCreate, UserUpdate,
    UserResponse, PasswordChange, RefreshTokenRequest,
    MFASetupResponse, MFAVerifyRequest,
)
from app.utils.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user, require_role,
    generate_mfa_secret, verify_mfa_code, get_mfa_qr_url,
)
from app.config import settings

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        await _log_audit(db, None, "LOGIN_FAILED", "auth", None,
                        request.client.host if request.client else None,
                        {"email": body.email, "reason": "invalid credentials"}, "failure")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(status_code=200, detail="MFA_REQUIRED", headers={"X-MFA-Required": "true"})
        if not verify_mfa_code(user.mfa_secret, body.mfa_code):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    # Update last login
    await db.execute(
        update(User).where(User.id == user.id).values(last_login=datetime.now(timezone.utc))
    )

    access_token = create_access_token(str(user.id), user.email, user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    await _log_audit(db, str(user.id), "LOGIN_SUCCESS", "auth", str(user.id),
                    request.client.host if request.client else None, {})
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    import uuid
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token(str(user.id), user.email, user.role.value)
    new_refresh = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        current_user.name = body.name
    if body.department is not None:
        current_user.department = body.department
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/change-password")
async def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = generate_mfa_secret()
    current_user.mfa_secret = secret
    await db.commit()

    qr_url = get_mfa_qr_url(current_user.email, secret)
    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_url,
        backup_codes=["ICCB-" + "".join([str(i) for i in range(8)]) for _ in range(6)],
    )


@router.post("/mfa/verify")
async def verify_mfa_setup(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not set up yet")
    if not verify_mfa_code(current_user.mfa_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    current_user.mfa_enabled = True
    await db.commit()
    return {"message": "MFA enabled successfully"}


async def _log_audit(
    db: AsyncSession, user_id, action, resource_type, resource_id, ip, details, audit_status="success"
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
        details=details,
        status=audit_status,
    )
    db.add(log)
