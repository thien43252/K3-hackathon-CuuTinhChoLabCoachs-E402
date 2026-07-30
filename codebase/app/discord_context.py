"""
Thread-safe shared context bridge between Discord bot and Agent tool functions.

Allows platform_tools (run in thread pool via run_in_executor) to call Discord API
asynchronously via asyncio.run_coroutine_threadsafe().

Usage (discord_bot.py):
    on_ready():  discord_context.set_bot(bot); discord_context.set_event_loop(bot.loop)
    on_message(): discord_context.set_current_channel(guild.id, channel.id)
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class _DiscordContext:
    """Holds the live Discord bot reference + current interaction context."""
    bot: Any = None                     # discord.ext.commands.Bot instance
    event_loop: asyncio.AbstractEventLoop | None = None
    guild_id: int | None = None
    channel_id: int | None = None


_dc = _DiscordContext()
_lock = threading.Lock()


# ── Writer helpers (called from discord_bot.py) ──

def set_bot(bot: Any) -> None:
    with _lock:
        _dc.bot = bot


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    with _lock:
        _dc.event_loop = loop


def set_current_channel(guild_id: int, channel_id: int) -> None:
    with _lock:
        _dc.guild_id = guild_id
        _dc.channel_id = channel_id


# ── Reader helpers (called from platform_tools.py) ──

def get() -> _DiscordContext:
    """Return a snapshot of the current context (thread-safe)."""
    with _lock:
        return _DiscordContext(
            bot=_dc.bot,
            event_loop=_dc.event_loop,
            guild_id=_dc.guild_id,
            channel_id=_dc.channel_id,
        )


def is_available() -> bool:
    """Quick check: is the Discord bot connected and ready?"""
    with _lock:
        return _dc.bot is not None and _dc.event_loop is not None
