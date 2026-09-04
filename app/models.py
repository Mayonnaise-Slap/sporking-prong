from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_ta: bool = Field(default=False)
    is_supervisor: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)

    restore_code: Optional[str] = Field(default=None)
    restore_code_expires_at: Optional[datetime] = Field(default=None)
