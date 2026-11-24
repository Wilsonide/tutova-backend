from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.domain.authentication.models import User
from app.domain.authentication.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.domain.authentication.schemas.phone_number import PhoneNumberUpdateRequest
from app.domain.authentication.services.auth_service import (
    AccountConflictError,
    AccountUnavailableError,
    AuthenticationError,
    AuthService,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

REFRESH_COOKIE_NAME = "tutova_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    is_production = settings.ENVIRONMENT == "production"

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=settings.REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    is_production = settings.ENVIRONMENT == "production"

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=is_production,
        httponly=True,
        samesite="none" if is_production else "lax",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = AuthService(db)

    try:
        _, access_token, refresh_token = await service.register(payload)
    except AccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = AuthService(db)

    try:
        _, access_token, refresh_token = await service.login(payload)
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    except AccountUnavailableError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token is missing.")

    service = AuthService(db)

    try:
        _, access_token, new_refresh_token = await service.refresh(refresh_token)
    except (AuthenticationError, AccountUnavailableError):
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    await AuthService(db).logout(refresh_token)
    clear_refresh_cookie(response)

    return MessageResponse(message="You have been logged out.")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await AuthService(db).change_password(current_user, payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return MessageResponse(
        message="Password changed successfully. Please sign in again."
    )



@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await AuthService(db).request_password_reset(payload)
    return MessageResponse(
        message=(
            "If an account exists for that email address, and email delivery is "
            "available, password reset instructions will be sent shortly."
        )
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await AuthService(db).reset_password(payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return MessageResponse(
        message="Your password has been reset. Please sign in with your new password."
    )


@router.patch("/phone-number", response_model=UserResponse)
async def update_phone_number(
    payload: PhoneNumberUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        return await AuthService(db).update_phone_number(
            current_user,
            payload.phone_number,
        )
    except AccountConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
