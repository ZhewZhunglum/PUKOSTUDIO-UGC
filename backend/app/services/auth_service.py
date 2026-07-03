from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import Team, User


async def register_user(
    db: AsyncSession, email: str, password: str, name: str, team_name: str | None = None
) -> tuple[User, dict]:
    # Check if email exists
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise BadRequestException("Email already registered")

    # Create team
    team = Team(name=team_name or f"{name}'s Team")
    db.add(team)
    await db.flush()

    # Create user
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        name=name,
        team_id=team.id,
    )
    db.add(user)
    await db.flush()

    tokens = _create_tokens(user)
    return user, tokens


async def authenticate_user(db: AsyncSession, email: str, password: str) -> tuple[User, dict]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password")

    tokens = _create_tokens(user)
    return user, tokens


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise UnauthorizedException("Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedException("User not found")

    return _create_tokens(user)


def _create_tokens(user: User) -> dict:
    token_data = {"sub": str(user.id), "team_id": str(user.team_id)}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }
