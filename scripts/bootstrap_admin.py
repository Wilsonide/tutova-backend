import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionFactory, engine
from app.core.security import hash_password
from app.domain.authentication.models.user import (
    AccountType,
    User,
    UserRole,
    UserStatus,
)


async def main() -> None:
    email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    password = settings.BOOTSTRAP_ADMIN_PASSWORD

    if not email or not password:
        raise SystemExit(
            "Set BOOTSTRAP_ADMIN_EMAIL and "
            "BOOTSTRAP_ADMIN_PASSWORD before running this command."
        )

    if len(password) < 12:
        raise SystemExit(
            "Bootstrap administrator password must contain at least 12 characters."
        )

    try:
        async with AsyncSessionFactory() as db:
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                raise SystemExit(
                    "An account with this email already exists. "
                    "Bootstrap will not modify existing accounts, "
                    "roles, or passwords."
                )

            admin = User(
                email=email,
                password_hash=hash_password(password),
                first_name="Tutova",
                last_name="Administrator",
                role=UserRole.SUPER_ADMIN,
                account_type=AccountType.ADMIN,
                status=UserStatus.ACTIVE,
                is_email_verified=True,
                is_phone_verified=False,
                must_change_password=True,
            )

            db.add(admin)
            await db.commit()

            print("Super administrator created successfully.")
            print(f"Email: {email}")
            print("Role: SUPER_ADMIN")
            print("Status: ACTIVE")
            print("Password change required at first login.")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
