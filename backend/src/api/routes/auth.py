import uuid
from datetime import date

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, UnauthorizedError
from src.models.dto.auth import TokenResponse
from src.models.orm.user import User
from src.repositories import user_repo
from src.services.auth_service import issue_tokens, logout, refresh_tokens
from src.services.budget_service import calculate_total_budget_cents
from src.services.settings_service import get_setting_int

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()

if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )



def _is_probation_passed(start_date: date | None) -> bool:
    if start_date is None:
        return False
    from dateutil.relativedelta import relativedelta
    probation_months = get_setting_int("probation_months")
    probation_end = start_date + relativedelta(months=probation_months)
    return date.today() >= probation_end


async def _handle_oauth_callback(
    request: Request,
    response: Response,
    db: AsyncSession,
    provider: str,
    email: str,
    name: str,
    provider_id: str,
) -> TokenResponse:
    ip = request.client.host if request.client else None

    domain = email.split("@")[-1] if "@" in email else ""
    if domain not in settings.allowed_domains_list:
        await write_audit_log(
            db, user_id=uuid.UUID(int=0), action="auth.login_blocked_unknown",
            resource_type="user", details={"email": email}, ip_address=ip,
        )
        raise UnauthorizedError("Email domain not allowed")

    user = await user_repo.get_by_email(db, email)
    if not user:
        await write_audit_log(
            db, user_id=uuid.UUID(int=0), action="auth.login_blocked_unknown",
            resource_type="user", details={"email": email}, ip_address=ip,
        )
        raise UnauthorizedError(
            "User not found. Please contact your administrator."
        )

    if not user.is_active:
        await write_audit_log(
            db, user_id=user.id, action="auth.login_blocked_inactive",
            resource_type="user", ip_address=ip,
        )
        raise UnauthorizedError("Account is inactive")

    if not user.probation_override and not _is_probation_passed(user.start_date):
        await write_audit_log(
            db, user_id=user.id, action="auth.login_blocked_probation",
            resource_type="user", ip_address=ip,
        )
        raise BadRequestError("PROBATION_NOT_PASSED")

    if not user.provider:
        user.provider = provider
        user.provider_id = provider_id

    user.total_budget_cents = calculate_total_budget_cents(user.start_date)

    tokens = await issue_tokens(db, user.id, user.email, user.role)

    await write_audit_log(
        db, user_id=user.id, action="auth.login",
        resource_type="user", ip_address=ip,
        details={"provider": provider},
    )

    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=tokens.access_token)


@router.get("/google/login")
async def google_login(request: Request):
    if not settings.google_client_id:
        raise BadRequestError("Google OAuth not configured")
    redirect_uri = settings.google_redirect_uri or f"{settings.backend_url}/api/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    email = userinfo.get("email", "")
    name = userinfo.get("name", email)
    sub = userinfo.get("sub", "")

    return await _handle_oauth_callback(
        request, response, db, "google", email, name, sub
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise UnauthorizedError("No refresh token")

    tokens = await refresh_tokens(db, refresh_token_cookie)

    ip = request.client.host if request.client else None
    payload = {}
    try:
        from src.core.security import decode_token
        payload = decode_token(tokens.access_token)
    except Exception:
        pass

    if payload.get("sub"):
        await write_audit_log(
            db, user_id=uuid.UUID(payload["sub"]),
            action="auth.token_refresh",
            resource_type="user", ip_address=ip,
        )

    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=tokens.access_token)


@router.post("/logout")
async def logout_user(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await logout(db, user.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="auth.logout",
        resource_type="user", ip_address=ip,
    )

    response.delete_cookie(key="refresh_token", path="/api/auth")
    return {"detail": "Logged out"}
