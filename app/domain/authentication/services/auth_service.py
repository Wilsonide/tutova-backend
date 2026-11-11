import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.domain.authentication.models import (
    AccountType,
    RefreshSession,
    User,
    UserRole,
    UserStatus,
)
from app.domain.authentication.repositories.refresh_session_repository import (
    RefreshSessionRepository,
)
from app.domain.authentication.repositories.user_repository import UserRepository
from app.domain.authentication.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
)


class AuthenticationError(Exception):
    pass


class AccountConflictError(Exception):
    pass


class AccountUnavailableError(Exception):
    pass


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.sessions = RefreshSessionRepository(db)

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        role = user.role.value if isinstance(user.role, UserRole) else str(user.role)

        access_token = create_access_token(
            subject=str(user.id),
            role=role,
        )

        refresh_token = new_refresh_token()

        refresh_expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_DAYS
        )

        session = RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_expires_at,
        )

        await self.sessions.create(session)

        return access_token, refresh_token

    async def register(
        self,
        payload: RegisterRequest,
    ) -> tuple[User, str, str]:
        email = str(payload.email).strip().lower()

        existing_user = await self.users.get_by_email(email)

        if existing_user:
            raise AccountConflictError("An account with this email already exists.")

        phone_number = payload.phone_number.strip() if payload.phone_number else None

        if phone_number:
            existing_phone = await self.users.get_by_phone(phone_number)

            if existing_phone:
                raise AccountConflictError(
                    "An account with this phone number already exists."
                )

        role_map = {
            AccountType.PARENT: UserRole.PARENT,
            AccountType.ADULT_LEARNER: UserRole.ADULT_LEARNER,
            AccountType.TUTOR: UserRole.TUTOR,
        }

        # Public registration must never create an administrator account.
        if payload.account_type not in role_map:
            raise AuthenticationError(
                "This account type cannot be registered publicly."
            )

        user = User(
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=email,
            phone_number=phone_number,
            password_hash=hash_password(payload.password),
            role=role_map[payload.account_type],
            account_type=payload.account_type,
            status=UserStatus.ACTIVE,
        )

        try:
            await self.users.create(user)

            access_token, refresh_token = await self._issue_tokens(user)

            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

        await self.db.refresh(user)

        return user, access_token, refresh_token

    async def login(
        self,
        payload: LoginRequest,
    ) -> tuple[User, str, str]:
        email = str(payload.email).strip().lower()

        user = await self.users.get_by_email(email)

        if not user or not verify_password(
            payload.password,
            user.password_hash,
        ):
            raise AuthenticationError("Invalid email or password.")

        if user.status != UserStatus.ACTIVE:
            raise AccountUnavailableError(
                "This account is not currently available for login."
            )

        try:
            access_token, refresh_token = await self._issue_tokens(user)

            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

        return user, access_token, refresh_token

    async def refresh(
        self,
        refresh_token: str,
    ) -> tuple[User, str, str]:
        token_hash = hash_refresh_token(refresh_token)

        session = await self.sessions.get_valid_session(token_hash)

        if not session:
            raise AuthenticationError("Invalid or expired refresh token.")

        user = await self.users.get_by_id(session.user_id)

        if not user or user.status != UserStatus.ACTIVE:
            await self.db.rollback()
            raise AccountUnavailableError("This account is not available.")

        try:
            # Rotate the refresh token: the old one becomes unusable.
            await self.sessions.revoke(session)

            access_token, new_token = await self._issue_tokens(user)

            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

        return user, access_token, new_token

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        session = await self.sessions.get_valid_session(
            hash_refresh_token(refresh_token)
        )

        if session:
            try:
                await self.sessions.revoke(session)
                await self.db.commit()

            except Exception:
                await self.db.rollback()
                raise

    async def authenticate_access_token(self, token: str) -> User:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            if payload.get("type") != "access":
                raise AuthenticationError("Invalid access token.")

            subject = payload.get("sub")

            if not subject:
                raise AuthenticationError("Invalid access token.")

            user_id = uuid.UUID(subject)

        except AuthenticationError:
            raise

        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise AuthenticationError("Invalid or expired access token.")

        user = await self.users.get_by_id(user_id)

        if not user or user.status != UserStatus.ACTIVE:
            raise AccountUnavailableError("This account is not available.")

        return user

    async def change_password(
        self,
        user: User,
        payload: ChangePasswordRequest,
    ) -> None:
        if not verify_password(
            payload.current_password,
            user.password_hash,
        ):
            raise AuthenticationError("Current password is incorrect.")

        if payload.current_password == payload.new_password:
            raise AuthenticationError(
                "Your new password must be different from your current password."
            )

        try:
            user.password_hash = hash_password(payload.new_password)
            user.must_change_password = False

            # Changing a password invalidates every existing refresh session.
            await self.sessions.revoke_all_for_user(user.id)

            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

    async def update_phone_number(
        self,
        user: User,
        phone_number: str | None,
    ) -> User:
        cleaned_phone = phone_number.strip() if phone_number else None

        if cleaned_phone == user.phone_number:
            return user

        if cleaned_phone:
            existing_phone = await self.users.get_by_phone(cleaned_phone)

            if existing_phone and existing_phone.id != user.id:
                raise AccountConflictError(
                    "An account with this phone number already exists."
                )

        try:
            user.phone_number = cleaned_phone

            # A changed phone number must be verified again.
            user.is_phone_verified = False

            await self.db.commit()
            await self.db.refresh(user)

            return user

        except Exception:
            await self.db.rollback()
            raise
