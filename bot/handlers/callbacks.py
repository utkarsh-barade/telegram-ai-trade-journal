"""
Inline keyboard callback handler.

Handles button presses from inline keyboards sent by the bot,
e.g. duplicate trade resolution: [UPDATE existing] / [CREATE NEW].

Phase 1 uses text-based resolution ("UPDATE 1" / "NEW") handled in messages.py.
This module is the correct place to add InlineKeyboardButton callbacks
if you prefer a button-based UX in a future iteration.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Placeholder callback query handler.

    Extend this with specific callback_data patterns as needed, e.g.:
        dupe_update:<trade_id>
        dupe_new
    """
    query = update.callback_query
    if query:
        await query.answer()
        logger.debug("Callback query received: %s", query.data)
        await query.edit_message_text("ℹ️ Inline buttons not yet configured.")
