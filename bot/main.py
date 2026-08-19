"""
Main application entry point.

Starts the Telegram bot (polling mode by default) as a background task
alongside a FastAPI health-check server.

Run with:
    python -m bot.main

Or via uvicorn (webhook mode — set WEBHOOK_URL in .env):
    uvicorn bot.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers.callbacks import handle_callback
from bot.handlers.commands import (
    cmd_capital,
    cmd_close,
    cmd_dashboard,
    cmd_delete,
    cmd_eos,
    cmd_excel,
    cmd_help,
    cmd_report,
    cmd_start,
    cmd_today,
    cmd_trades,
)
from bot.handlers.messages import handle_message
from db.session import init_db

# ──────────────────────────────────────────────────────────────────────────────
# Environment + Logging
# ──────────────────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "123456789:MockBotTokenForDashboardLocalDev")
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")

# ──────────────────────────────────────────────────────────────────────────────
# FastAPI app (health check + optional webhook endpoint)
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Telegram AI Trade Journal Agent API",
    description="Backend & Dashboard API for the Telegram AI Trade Journal Agent — Phase 1 & 2",
    version="2.0.0",
)

# Add CORS Middleware to allow requests from Vite dev server (e.g. port 3000 or 5173)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
from api import auth, dashboard
app.include_router(auth.router)
app.include_router(dashboard.router)

# Mount static frontend build if present
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/")
    @app.get("/dashboard")
    async def serve_dashboard():
        return FileResponse(os.path.join(frontend_dist, "index.html"))

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Ignore API and docs paths
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json") or full_path == "health":
            return
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

# Will be set during startup
_telegram_app: Application | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "bot_running": _telegram_app is not None}


@app.post(f"/webhook/{BOT_TOKEN}")
async def webhook(update: dict) -> dict:
    """Receive Telegram updates via webhook."""
    if _telegram_app is None:
        return {"ok": False}
    tg_update = Update.de_json(update, _telegram_app.bot)
    await _telegram_app.process_update(tg_update)
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────────
# Build the Telegram Application
# ──────────────────────────────────────────────────────────────────────────────

def build_application() -> Application:
    """Construct and configure the Telegram Application."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("trades", cmd_trades))
    application.add_handler(CommandHandler("today", cmd_today))
    application.add_handler(CommandHandler("capital", cmd_capital))
    application.add_handler(CommandHandler("close", cmd_close))
    application.add_handler(CommandHandler("delete", cmd_delete))
    application.add_handler(CommandHandler("excel", cmd_excel))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CommandHandler("eos", cmd_eos))
    application.add_handler(CommandHandler("dashboard", cmd_dashboard))

    # Free-text messages (non-command)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Inline keyboard callbacks
    application.add_handler(CallbackQueryHandler(handle_callback))

    return application


# ──────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown lifecycle
# ──────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    global _telegram_app

    # Initialise database (create tables if not exist)
    init_db()
    logger.info("Database initialised.")

    try:
        _telegram_app = build_application()
        await _telegram_app.initialize()

        if WEBHOOK_URL:
            # Webhook mode
            webhook_url = f"{WEBHOOK_URL.rstrip('/')}/webhook/{BOT_TOKEN}"
            await _telegram_app.bot.set_webhook(webhook_url)
            logger.info("Webhook registered at %s", webhook_url)
            await _telegram_app.start()
        else:
            # Polling mode — run as a background task
            logger.info("Starting bot in polling mode…")
            await _telegram_app.start()
            asyncio.create_task(_polling_loop(_telegram_app))
    except Exception as e:
        logger.warning("Telegram Bot initialisation skipped or failed (Dashboard remains 100%% active): %s", e)

    # Start Phase 3 Background Market Data Monitoring Loop
    asyncio.create_task(_monitoring_task())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _telegram_app
    if _telegram_app:
        try:
            await _telegram_app.stop()
            await _telegram_app.shutdown()
            logger.info("Bot stopped.")
        except Exception:
            pass


async def _polling_loop(application: Application) -> None:
    """Long-poll for updates and process them."""
    try:
        logger.info("Polling for Telegram updates…")
        await application.updater.start_polling(drop_pending_updates=True)
    except Exception as e:
        logger.warning("Telegram polling stopped: %s", e)


async def _monitoring_task() -> None:
    """Background loop polling open trades against live market prices."""
    from db.session import db_session
    from services import monitoring_service

    poll_interval = float(os.getenv("POLL_INTERVAL_SECONDS", "30.0"))
    logger.info("Starting background market monitoring loop (interval: %ss)…", poll_interval)
    while True:
        try:
            with db_session() as db:
                await monitoring_service.run_monitoring_cycle(db, telegram_app=_telegram_app)
        except Exception as e:
            logger.error("Error in market monitoring cycle: %s", e)
        await asyncio.sleep(poll_interval)


# ──────────────────────────────────────────────────────────────────────────────
# Direct-run entry point (python -m bot.main)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bot.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
