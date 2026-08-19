"""
Telegram user ID whitelist middleware.

Reads ALLOWED_USER_IDS from the environment (comma-separated integers).
Any message from an unauthorised user is silently dropped — the bot
gives no response, leaving no attack surface.

Usage (in bot/main.py):
    application.add_handler(
        MessageHandler(filters.ALL, auth_middleware), group=-1
    )
Or use as a pre-process function in each handler.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Load whitelist at module import time (so it's read once from env)
# ──────────────────────────────────────────────────────────────────────────────

def _load_whitelist() -> set[int]:
    raw = os.getenv("ALLOWED_USER_IDS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                logger.warning("Invalid user ID in ALLOWED_USER_IDS: %r", part)
    if not ids:
        logger.warning(
            "ALLOWED_USER_IDS is empty — the bot will reject ALL messages. "
            "Set ALLOWED_USER_IDS in your .env file."
        )
    return ids


ALLOWED_USER_IDS: set[int] = _load_whitelist()


# ──────────────────────────────────────────────────────────────────────────────
# Check function (used by handlers)
# ──────────────────────────────────────────────────────────────────────────────

def is_authorised(user_id: Optional[int]) -> bool:
    """Return True if *user_id* is in the whitelist."""
    if user_id is None:
        return False
    return user_id in ALLOWED_USER_IDS


async def reject_unauthorised(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    Check if the sender is authorised.

    Returns True (and sends nothing) if the sender is NOT authorised,
    so the caller can do `if await reject_unauthorised(...): return`.

    Returns False if the sender IS authorised (continue processing).
    """
    user = update.effective_user
    if user is None or not is_authorised(user.id):
        uid = user.id if user else "unknown"
        logger.warning("Rejected unauthorised user %s", uid)
        return True   # drop the update silently
    return False      # authorised — continue
