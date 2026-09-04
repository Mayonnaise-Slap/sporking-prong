import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import RestoreConfirm, RestoreRequest, Token, UserLogin, UserPublic, UserRegister
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.auth")

RESTORE_CODE_TTL_MINUTES = 15


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.exec(select(User).where(User.email == payload.email))
    if existing.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_ta=payload.is_ta,
        is_supervisor=payload.is_supervisor,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    result = await db.exec(select(User).where(User.email == payload.email))
    user = result.first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/restore", status_code=status.HTTP_202_ACCEPTED)
async def restore(payload: RestoreRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.exec(select(User).where(User.email == payload.email))
    user = result.first()

    if user is not None:
        code = f"{secrets.randbelow(1_000_000):06d}"
        user.restore_code = code
        user.restore_code_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            minutes=RESTORE_CODE_TTL_MINUTES
        )
        db.add(user)
        await db.commit()

        # TODO: send this via email once we have an email provider wired up.
        print(f"[restore] password restoration code for {user.email}: {code}")
        logger.info("Generated restoration code for %s", user.email)

    return {"detail": "If that email is registered, a restoration code has been generated."}


@router.post("/restore/confirm")
async def restore_confirm(payload: RestoreConfirm, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.exec(select(User).where(User.email == payload.email))
    user = result.first()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    code_is_valid = (
        user is not None
        and user.restore_code is not None
        and secrets.compare_digest(user.restore_code, payload.code)
        and user.restore_code_expires_at is not None
        and user.restore_code_expires_at >= now
    )
    if not code_is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired restoration code")

    user.hashed_password = hash_password(payload.new_password)
    user.restore_code = None
    user.restore_code_expires_at = None
    db.add(user)
    await db.commit()

    return {"detail": "Password has been reset."}
