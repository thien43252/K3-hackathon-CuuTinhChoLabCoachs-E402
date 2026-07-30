"""
Thread-safe shared context bridge between Discord bot and Agent tool functions.

Allows platform_tools (run in thread pool via run_in_executor) to call Discord API
asynchronously via asyncio.run_coroutine_threadsafe().

Also provides auto-resolved context values (user_id, group_id, members, lab_id, etc.)
so tools don't need these as parameters — code detects them from the Discord environment.

Usage (discord_bot.py):
    on_ready():  discord_context.set_bot(bot); discord_context.set_event_loop(bot.loop)
    on_message(): discord_context.set_current_channel(guild.id, channel.id)
                   discord_context.set_context(user_id=..., group_id=..., lab_id=...)
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _DiscordContext:
    """Holds the live Discord bot reference + current interaction context."""
    bot: Any = None                     # discord.ext.commands.Bot instance
    event_loop: asyncio.AbstractEventLoop | None = None
    guild_id: int | None = None
    channel_id: int | None = None

    # ── Auto-resolved context (set on every message) ──
    user_id: str | None = None          # from message.author.id
    channel_type: str | None = None     # "general" | "group_room"
    group_id: str | None = None         # from rooms table (group rooms only)
    members: list[dict] | None = None   # [{"id": "...", "name": "..."}, ...] (group rooms only)
    lab_id: str | None = None           # auto-resolved from lab_date <= today


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


def set_context(
    user_id: str | None = None,
    channel_type: str | None = None,
    group_id: str | None = None,
    members: list[dict] | None = None,
    lab_id: str | None = None,
) -> None:
    """Bulk-set all auto-resolved context values (called from discord_bot.py on each message)."""
    with _lock:
        if user_id is not None:
            _dc.user_id = user_id
        if channel_type is not None:
            _dc.channel_type = channel_type
        if group_id is not None:
            _dc.group_id = group_id
        if members is not None:
            _dc.members = members
        if lab_id is not None:
            _dc.lab_id = lab_id


def clear_context() -> None:
    """Reset all auto-resolved context (use when leaving a channel / session ends)."""
    with _lock:
        _dc.user_id = None
        _dc.channel_type = None
        _dc.group_id = None
        _dc.members = None
        _dc.lab_id = None


# ── Reader helpers (called from tool functions) ──

def get() -> _DiscordContext:
    """Return a snapshot of the current context (thread-safe)."""
    with _lock:
        return _DiscordContext(
            bot=_dc.bot,
            event_loop=_dc.event_loop,
            guild_id=_dc.guild_id,
            channel_id=_dc.channel_id,
            user_id=_dc.user_id,
            channel_type=_dc.channel_type,
            group_id=_dc.group_id,
            members=_dc.members,
            lab_id=_dc.lab_id,
        )


def is_available() -> bool:
    """Quick check: is the Discord bot connected and ready?"""
    with _lock:
        return _dc.bot is not None and _dc.event_loop is not None
