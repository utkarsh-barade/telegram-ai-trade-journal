"""
Capital service: manage per-user capital settings.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from db.models import UserCapital


def get_user_capital(db: Session, user_id: int) -> Optional[float]:
    """Return the user's current capital setting, or None if not set."""
    record = db.query(UserCapital).filter(UserCapital.user_id == user_id).first()
    return record.capital if record else None


def set_user_capital(
    db: Session,
    user_id: int,
    capital: float,
    username: Optional[str] = None,
) -> UserCapital:
    """Create or update the user's capital setting."""
    record = db.query(UserCapital).filter(UserCapital.user_id == user_id).first()
    if record is None:
        record = UserCapital(user_id=user_id, username=username, capital=capital)
        db.add(record)
    else:
        record.capital = capital
        if username:
            record.username = username

    db.commit()
    db.refresh(record)
    return record
