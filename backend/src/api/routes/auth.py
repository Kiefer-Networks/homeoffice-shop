import asyncio
import logging
import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.audit.service import log_admin_action
from src.core.config import settings
from src.core.exceptions import BadRequestError, UnauthorizedError
from src.models.dto.auth import TokenResponse
from src.models.orm.user import User
from src.core.security import decode_token
from src.notifications.email import mask_email
from src.notifications.service import notify_user_email
from src.services.auth_service import issue_tokens, logout, refresh_tokens, validate_oauth_user

logger = logging.getLogger(__name__)

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



async def _send_welcome_email(email: str, display_name: str) -> None:
    try:
        await notify_user_email(
            email,
            subject="Welcome to the Home Office Shop",
            template_name="welcome.html",
            context={"display_name": display_name},
        )
    except Exception:
        logger.exception("Failed to send welcome email to %s", mask_email(email))


async def _handle_oauth_callback(
    request: Request,
    response: Response,
    db: AsyncSession,
    provider: str,
    email: str,
    name: str,
    provider_id: str,
) -> TokenResponse:
    try:
        user, is_first_login = await validate_oauth_user(db, email, provider, provider_id)
    except UnauthorizedError:
        await log_admin_action(
            db, request, uuid.UUID(int=0), "auth.login_blocked",
            resource_type="user",
            details={"email": email, "provider": provider},
        )
        raise
    except BadRequestError:
        await log_admin_action(
            db, request, uuid.UUID(int=0), "auth.login_blocked_probation",
            resource_type="user",
            details={"email": email, "provider": provider},
        )
        raise

    tokens = await issue_tokens(db, user.id, user.email, user.role)

    if is_first_login:
        asyncio.create_task(_send_welcome_email(user.email, user.display_name))

    await log_admin_action(
        db, request, user.id, "auth.login",
        resource_type="user",
        details={"provider": provider, "email": user.email},
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

    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/google/login")
async def google_login(request: Request):
    if not settings.google_client_id:
        raise BadRequestError("Google OAuth not configured")
    redirect_uri = settings.google_redirect_uri or f"{settings.backend_url}/api/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    email = userinfo.get("email", "")
    sub = userinfo.get("sub", "")
    name = userinfo.get("name", email)

    if not email or not sub:
        raise BadRequestError("Invalid OAuth response: missing email or user ID")

    response = RedirectResponse(url=f"{settings.frontend_url}/callback")
    await _handle_oauth_callback(
        request, response, db, "google", email, name, sub
    )
    return response


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

    payload = {}
    try:
        payload = decode_token(tokens.access_token)
    except Exception:
        pass

    if payload.get("sub"):
        await log_admin_action(
            db, request, uuid.UUID(payload["sub"]),
            "auth.token_refresh",
            resource_type="user",
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

    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=204)
async def logout_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await logout(db, user.id)

    await log_admin_action(
        db, request, user.id, "auth.logout",
        resource_type="user",
    )

    response = Response(status_code=204)
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return response
