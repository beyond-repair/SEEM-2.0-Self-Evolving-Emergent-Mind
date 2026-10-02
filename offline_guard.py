"""Offline Claim-0 guards — refuse optional remote-control paths without config.

Telegram / daemon remote control is optional historical tooling. The Claim-0
demo must run with zero network tokens.
"""
from __future__ import annotations

import os
from typing import Optional


PLACEHOLDER_TOKENS = {
    "",
    "YOUR_BOT_TOKEN_HERE",
    "your-secure-vsa-key-123",
}


class OfflineModeError(RuntimeError):
    """Raised when a network/remote helper is used without explicit configuration."""


def telegram_token(env: Optional[dict] = None) -> Optional[str]:
    env = env if env is not None else os.environ
    token = env.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    if token in PLACEHOLDER_TOKENS or token is None:
        return None
    return token


def require_telegram_token(env: Optional[dict] = None) -> str:
    token = telegram_token(env)
    if token is None:
        raise OfflineModeError(
            "Telegram optional remote control disabled offline: "
            "set TELEGRAM_BOT_TOKEN to enable (not required for Claim-0 demo)."
        )
    return token


def refuse_network_helpers(env: Optional[dict] = None) -> None:
    """Claim-0 offline entrypoints call this to document refusal of Telegram."""
    if telegram_token(env) is not None:
        # Token present: still allowed, but Claim-0 demos do not start the bot.
        return
    # No token: explicit offline refusal path used by tests / main.
    raise OfflineModeError(
        "Offline Claim-0 mode: Telegram bot and remote daemon helpers are not started."
    )
