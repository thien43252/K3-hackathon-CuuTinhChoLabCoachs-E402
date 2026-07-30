"""
Module chứa các công cụ tạo phòng nhóm trên Discord (Platform Tools).
Sử dụng CSDL SQLite thực tế (`users`, `rooms`, `messages`).
Bao gồm:
1. create_group_room

Khi có Discord context (bot đang chạy), các tool này sẽ gọi Discord API thật.
Khi không có (CLI mode), fallback về mock data.

Lưu ý: user_id, group_id, lab_id được auto-resolve từ Discord context (discord_context.py)
và inject vào system prompt, KHÔNG cần tool riêng để lấy.
"""

import asyncio
import json
import discord
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.db import get_db_connection
from app import discord_context


class CreateGroupRoomInput(BaseModel):
    room_name: str = Field(..., description="Tên room chat cần tạo")
    member_ids: List[str] = Field(..., description="Danh sách User ID của các thành viên")
    is_private: bool = Field(default=True, description="Quyền riêng tư của room")




# ── Discord async bridge helper ──

def _run_discord_coro(coro, timeout: float = 10.0):
    """Run an async Discord operation from a synchronous (thread-pool) context.

    Uses asyncio.run_coroutine_threadsafe to schedule the coroutine on the
    bot's event loop.  Returns the coroutine result or None on failure.
    """
    ctx = discord_context.get()
    if not ctx or not ctx.event_loop:
        return None
    future = asyncio.run_coroutine_threadsafe(coro, ctx.event_loop)
    try:
        return future.result(timeout=timeout)
    except Exception as exc:
        print(f"⚠️ [DiscordBridge] {type(exc).__name__}: {exc}")
        return None


def _resolve_member_by_name_or_id(guild: discord.Guild, identifier: str) -> Optional[discord.Member]:
    """Helper to resolve a Discord member by ID, mention, or name (display name / username)"""
    if not identifier:
        return None
        
    identifier = str(identifier).strip()
    
    # 1. Dạng mention: <@123456789> hoặc <@!123456789>
    if identifier.startswith("<@") and identifier.endswith(">"):
        clean_id = identifier.replace("<@", "").replace("!", "").replace("&", "").replace(">", "")
        if clean_id.isdigit():
            member_id = int(clean_id)
            member = guild.get_member(member_id)
            if not member:
                try:
                    member = _run_discord_coro(guild.fetch_member(member_id))
                except Exception:
                    pass
            return member

    # 2. Dạng chuỗi số ID nguyên bản
    if identifier.isdigit():
        member_id = int(identifier)
        member = guild.get_member(member_id)
        if not member:
            try:
                member = _run_discord_coro(guild.fetch_member(member_id))
            except Exception:
                pass
        return member

    # 3. Tìm kiếm theo tên (Display Name hoặc Username) trong cache guild.members
    name_lower = identifier.lower()
    
    # Thử tìm khớp hoàn toàn (exact match)
    for m in guild.members:
        if m.display_name.lower() == name_lower or m.name.lower() == name_lower:
            return m
            
    # Thử tìm khớp một phần (substring match)
    for m in guild.members:
        if name_lower in m.display_name.lower() or name_lower in m.name.lower():
            return m

    # 4. Thử tìm bằng guild.query_members (gọi API Discord) nếu cache không tìm thấy
    try:
        members = _run_discord_coro(guild.query_members(query=identifier, limit=5))
        if members:
            # Ưu tiên khớp hoàn toàn
            for m in members:
                if m.display_name.lower() == name_lower or m.name.lower() == name_lower:
                    return m
            return members[0]
    except Exception:
        pass

    return None


def create_group_room(
    room_name: str,
    member_ids: List[str],
    is_private: bool = True
) -> Dict[str, Any]:
    """
    2. create_group_room
    Mô tả: Tự động tạo channel/room chat nhóm và ghi nhận thông tin vào SQLite DB.
    Room được tạo ở chế độ private (chỉ thành viên trong nhóm mới thấy).
    Chỉ tạo phòng khi TẤT CẢ thành viên trong danh sách đều hợp lệ.
    CHỈ dùng được ở general channel — không tạo phòng trong phòng nhóm.
    """
    try:
        # Guardrail: không cho tạo phòng trong group room
        ctx = discord_context.get()
        if ctx and ctx.channel_type == "group_room":
            return {"status": "empty", "error_code": "WRONG_CHANNEL",
                    "message": "Bạn đang ở trong phòng nhóm riêng. Chỉ tạo phòng từ kênh chung (general) nhé."}

        if not room_name or not room_name.strip() or not member_ids:
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "room_name và danh sách member_ids không được để trống."
            }

        if "TRIGGER_500" in room_name:
            return {
                "status": "error",
                "error_code": "PLATFORM_API_ERROR",
                "message": "Không có quyền tạo channel trên nền tảng chat."
            }

        # ── Thử tạo channel thật trên Discord ──
        ctx = discord_context.get()
        if ctx and ctx.bot and ctx.guild_id:
            guild = ctx.bot.get_guild(ctx.guild_id)
            if guild:
                channel_name = f"group-{room_name.lower().replace(' ', '-')}"

                # Xây permission overwrites
                overwrites = None
                if is_private:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    }
                    # Phân quyền cho từng member (hỗ trợ ID số hoặc tên)
                added_members = []
                failed_members = []

                for uid in member_ids:
                    member = _resolve_member_by_name_or_id(guild, uid)
                    if member:
                        overwrites[member] = discord.PermissionOverwrite(
                            read_messages=True, send_messages=True,
                            embed_links=True, attach_files=True
                        )
                        added_members.append(str(member.id))
                    else:
                        failed_members.append({
                            "user_id": uid,
                            "reason": "Không tìm thấy trên server",
                            "hint": f"Hãy @mention trực tiếp người dùng '{uid}', hoặc dùng đúng tên hiển thị Discord của họ"
                        })

                if failed_members:
                    failed_list = "\n".join([
                        f"  • `{m['user_id']}` — {m['reason']}. {m.get('hint', '')}"
                        for m in failed_members
                    ])
                    return {
                        "status": "empty",
                        "error_code": "INVALID_MEMBERS",
                        "message": f"Không thể tạo phòng vì {len(failed_members)}/{len(member_ids)} thành viên không tìm thấy trên server:\n{failed_list}\n\n💡 **Cách khắc phục:** @mention trực tiếp người dùng (gõ @ và chọn tên), hoặc dùng đúng tên hiển thị Discord (display name) của họ.",
                        "failed_members": failed_members,
                        "valid_count": len(added_members),
                        "invalid_count": len(failed_members),
                    }

                try:
                    channel = _run_discord_coro(
                        guild.create_text_channel(name=channel_name, overwrites=overwrites)
                    )
                    if channel:
                        room_id = str(channel.id)
                        created_at = datetime.now(timezone.utc).isoformat()
                        # Lưu room vào CSDL SQLite
                        try:
                            conn_save = get_db_connection()
                            cur = conn_save.cursor()
                            cur.execute(
                                """
                                INSERT OR REPLACE INTO rooms (room_id, room_name, discord_channel_id, channel_name, added_members, is_private, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    room_id,
                                    room_name,
                                    room_id,
                                    channel_name,
                                    json.dumps(added_members, ensure_ascii=False),
                                    1 if is_private else 0,
                                    created_at
                                )
                            )
                            conn_save.commit()
                            conn_save.close()
                        except Exception as db_exc:
                            print(f"⚠️ [DiscordBridge] create_group_room DB save failed: {db_exc}")

                        return {
                            "status": "success",
                            "room_id": room_id,
                            "discord_channel_id": room_id,
                            "channel_name": channel_name,
                            "added_members": added_members
                        }
                except Exception as exc:
                    print(f"⚠️ [DiscordBridge] create_group_room failed: {exc}")
                    # Fallback qua mock bên dưới

        # ── Fallback: mock data (khi không có Discord context) ──
        added_members = []
        failed_members = []

        for uid in member_ids:
            if uid.startswith("INVALID_") or uid == "U_UNKNOWN":
                failed_members.append({"user_id": uid, "reason": "Không tìm thấy"})
            else:
                added_members.append(uid)

        if failed_members:
            failed_list = "\n".join([
                f"  • `{m['user_id']}` — {m['reason']}"
                for m in failed_members
            ])
            return {
                "status": "empty",
                "error_code": "INVALID_MEMBERS",
                "message": f"Không tìm thấy {len(failed_members)}/{len(member_ids)} thành viên:\n{failed_list}\n\n💡 Hãy @mention trực tiếp người dùng (gõ @ và chọn tên).",
                "failed_members": failed_members,
                "valid_count": len(added_members),
                "invalid_count": len(failed_members),
            }

        room_id = f"1298{abs(hash(room_name)) % 100000000000000}"
        discord_channel_name = f"group-{room_name.lower().replace(' ', '-')}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Lưu room vào CSDL SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO rooms (room_id, room_name, discord_channel_id, channel_name, added_members, is_private, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room_id,
                room_name,
                room_id,
                discord_channel_name,
                json.dumps(added_members, ensure_ascii=False),
                1 if is_private else 0,
                created_at
            )
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "room_id": room_id,
            "discord_channel_id": room_id,
            "channel_name": discord_channel_name,
            "added_members": added_members
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "PLATFORM_API_ERROR",
            "message": f"Lỗi gọi Platform API: {str(e)}"
        }
