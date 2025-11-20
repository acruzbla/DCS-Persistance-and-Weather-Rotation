# app/discord_notifier.py
# -*- coding: utf-8 -*-
"""
Discord notifier module.
Uses discord-webhook embed messages.
Webhook URL and enable flag are read from config JSON.
"""

import json
from pathlib import Path
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

from logger_setup import get_logger

logger = get_logger()


# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------

CONFIG_PATH = Path("../dcs_persistence_config.json")


# -------------------------------------------------------
# INTERNAL HELPERS
# -------------------------------------------------------

def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"[Notifier] Failed to load config: {e}")
        return None


def _send_embed_to_webhook(webhook_url: str, title: str, description: str, color: int):
    """Low-level function to send embed via discord-webhook."""
    try:
        embed = DiscordEmbed(
            title=title,
            description=f"{description}\n\n**Time:** {_now_iso()}",
            color=color,
        )

        webhook = DiscordWebhook(url=webhook_url, rate_limit_retry=True)
        webhook.add_embed(embed)
        webhook.execute()

    except Exception as e:
        logger.error(f"[Notifier] Discord send error: {e}")


# -------------------------------------------------------
# PUBLIC FUNCTIONS
# -------------------------------------------------------

def notify_discord_error(message: str):
    """
    Sends an error embed IF enabled in config.
    """
    cfg = _load_config()
    if not cfg:
        logger.error("[Notifier] Config unavailable, cannot notify Discord.")
        return

    enabled = cfg.get("send_errors_to_discord", False)
    webhook = cfg.get("error_discord_webhook", "").strip()

    if not enabled:
        logger.info("[Notifier] Discord error notifications disabled.")
        return

    if not webhook:
        logger.error("[Notifier] Error webhook enabled but URL missing.")
        return

    logger.info("[Notifier] Sending ERROR notification to Discord...")

    _send_embed_to_webhook(
        webhook,
        title="❌ DCS Persistence Error",
        description=message,
        color=0xD32F2F,
    )


def notify_discord_warning(message: str):
    """
    Sends a yellow warning embed IF enabled.
    """
    cfg = _load_config()
    if not cfg:
        return

    enabled = cfg.get("send_errors_to_discord", False)
    webhook = cfg.get("error_discord_webhook", "").strip()

    if enabled and webhook:
        logger.info("[Notifier] Sending WARNING notification to Discord...")
        _send_embed_to_webhook(
            webhook,
            title="⚠️ Warning",
            description=message,
            color=0xFFA000,
        )


def notify_discord_info(message: str):
    """
    Sends a blue info embed IF enabled.
    """
    cfg = _load_config()
    if not cfg:
        return

    enabled = cfg.get("send_errors_to_discord", False)
    webhook = cfg.get("error_discord_webhook", "").strip()

    if enabled and webhook:
        logger.info("[Notifier] Sending INFO notification to Discord...")
        _send_embed_to_webhook(
            webhook,
            title="ℹ️ Info",
            description=message,
            color=0x2196F3,
        )
