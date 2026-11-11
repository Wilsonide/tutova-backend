import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.security import decode_access_token
from app.domain.authentication.models.user import (
    User,
    UserRole,
    UserStatus,
)
from app.domain.authentication.repositories.user_repository import UserRepository

security = HTTPBearer()

# =====================================================
# COMMON DEPENDENCIES
# =====================================================

DBSession = Annotated[AsyncSession, Depends(get_db)]


# =====================================================
# AUTHENTICATION
# =====================================================


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(security),
    ],
    db: DBSession,
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])

    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise AuthenticationError("Invalid or expired access token.")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if user is None or user.status != UserStatus.ACTIVE:
        raise AuthenticationError("Account is unavailable.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# =====================================================
# ROLE-BASED ACCESS CONTROL
# =====================================================


def require_roles(*roles: UserRole):
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError()

        return user

    return dependency


# =====================================================
# ROLE-SPECIFIC DEPENDENCIES
# =====================================================

RequireParent = Annotated[
    User,
    Depends(require_roles(UserRole.PARENT)),
]

RequireAdultLearner = Annotated[
    User,
    Depends(require_roles(UserRole.ADULT_LEARNER)),
]

RequireTutor = Annotated[
    User,
    Depends(require_roles(UserRole.TUTOR)),
]

RequireAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN)),
]

RequireSuperAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.SUPER_ADMIN)),
]


# =====================================================
# COMBINED ROLE DEPENDENCIES
# =====================================================

RequireRequester = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.PARENT,
            UserRole.ADULT_LEARNER,
        )
    ),
]

RequireBookingParticipant = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.PARENT,
            UserRole.ADULT_LEARNER,
            UserRole.TUTOR,
        )
    ),
]

RequireBookingAdmin = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
]

RequireAnyAdmin = RequireBookingAdmin
