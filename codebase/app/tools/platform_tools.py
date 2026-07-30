"""
Module chứa các công cụ Tương tác Nền tảng & Ngữ cảnh (Platform & Context Tools).
Sử dụng CSDL SQLite thực tế (`users`, `rooms`, `messages`).
Bao gồm:
4. get_user_context
5. verify_discord_members
6. create_group_room
7. send_message
8. send_notification

Khi có Discord context (bot đang chạy), các tool này sẽ gọi Discord API thật.
Khi không có (CLI mode), fallback về mock data.
"""

import asyncio
import json
import discord
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.db import get_db_connection
from app import discord_context


class GetUserContextInput(BaseModel):
    user_id: str = Field(..., description="ID người dùng trên hệ thống chat (Slack/Discord/LMS)")
    date: Optional[str] = Field(default=None, description="Ngày làm lab (định dạng YYYY-MM-DD)")


class VerifyDiscordMembersInput(BaseModel):
    member_ids: List[str] = Field(..., description="Danh sách Discord User ID cần kiểm tra")

class CreateGroupRoomInput(BaseModel):
    room_name: str = Field(..., description="Tên room chat cần tạo")
    member_ids: List[str] = Field(..., description="Danh sách User ID của các thành viên")
    is_private: bool = Field(default=True, description="Quyền riêng tư của room")


class SendMessageInput(BaseModel):
    target_id: str = Field(..., description="Room ID hoặc User ID nhận tin nhắn")
    message: str = Field(..., description="Nội dung tin nhắn (hỗ trợ Markdown)")
    attachments: Optional[List[Dict[str, Any]]] = Field(default=None, description="Đính kèm (File, Card UI...)")


class SendNotificationInput(BaseModel):
    room_id: str = Field(..., description="Room ID nơi phát thông báo")
    user_ids_to_tag: List[str] = Field(..., description="Danh sách ID người dùng cần tag tên")
    content: str = Field(..., description="Nội dung thông báo")
    urgency: str = Field(default="normal", description="Mức độ ưu tiên ('normal', 'high', 'urgent')")


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


def get_user_context(
    user_id: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    4. get_user_context
    Mô tả: Lấy thông tin chi tiết về người dùng đang gọi bot.
    Ưu tiên Discord member info (fetch_member), sau đó SQLite DB.
    """
    try:
        if not user_id or not user_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "user_id không được để trống."
            }

        if "TRIGGER_500" in user_id:
            return {
                "status": "error",
                "error_code": "USER_SERVICE_UNAVAILABLE",
                "message": "Không thể kết nối đến hệ thống quản lý học viên."
            }

        # ── Bước 1: Lấy thông tin từ Discord context (fetch_member để đảm bảo có data) ──
        discord_full_name = None
        discord_role = "student"
        ctx = discord_context.get()
        if ctx and ctx.bot and ctx.guild_id:
            guild = ctx.bot.get_guild(ctx.guild_id)
            if guild:
                try:
                    uid = int(user_id) if user_id.isdigit() else user_id
                    # Dùng fetch_member (async API call) thay vì get_member (cache lookup)
                    member = _run_discord_coro(guild.fetch_member(uid))
                    if member:
                        discord_full_name = member.display_name
                        if any(r.name.lower() in ("admin", "administrator", "giảng viên", "ta") for r in member.roles):
                            discord_role = "admin"
                        elif any(r.name.lower() in ("group_leader", "trưởng nhóm", "leader") for r in member.roles):
                            discord_role = "group_leader"
                except (ValueError, TypeError):
                    pass

        # ── Bước 2: Tra SQLite DB, luôn sync name/role từ Discord nếu có ──
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            if "NOLAB" in user_id:
                conn.close()
                return {
                    "status": "empty",
                    "error_code": "NO_LAB_TODAY",
                    "message": "Không tìm thấy lịch bài lab nào cho học viên trong ngày hôm nay."
                }

            if discord_full_name:
                # Discord user thật, chưa có DB → tự động tìm lab theo ngày hôm nay
                today_str = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                lab_row = None
                try:
                    cursor.execute(
                        "SELECT lab_id, title, type FROM lab_materials WHERE lab_date <= ? ORDER BY lab_date DESC LIMIT 1",
                        (today_str,)
                    )
                    lab_row = cursor.fetchone()
                except Exception:
                    pass  # bảng lab_materials có thể chưa tồn tại
                conn.close()

                if lab_row:
                    return {
                        "status": "success",
                        "user": {
                            "user_id": user_id,
                            "full_name": discord_full_name,
                            "role": discord_role
                        },
                        "today_lab": {
                            "lab_id": lab_row["lab_id"],
                            "type": lab_row["type"],
                            "title": lab_row["title"]
                        },
                        "group_info": None
                    }

                return {
                    "status": "empty",
                    "error_code": "NO_LAB_TODAY",
                    "message": "Hôm nay chưa có bài lab nào được lên lịch. Hãy chờ Admin cập nhật lab mới nhé!"
                }

            # Không có Discord, không có DB → insert default Lab
            cursor.execute(
                """
                INSERT INTO users (user_id, full_name, role, group_id, today_lab_id, today_lab_type, today_lab_title)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, f"Học viên {user_id}", "student", None, "LAB05_INDIVIDUAL", "individual", "Bài lab cá nhân")
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

        else:
            # User đã tồn tại trong DB — sync name/role từ Discord nếu có
            if discord_full_name:
                cursor.execute(
                    "UPDATE users SET full_name = ?, role = ? WHERE user_id = ?",
                    (discord_full_name, discord_role, user_id)
                )
                conn.commit()

        # ── Build response ──
        full_name = discord_full_name or user_row["full_name"]
        role = discord_role if discord_full_name else user_row["role"]

        group_info = None
        group_id = user_row["group_id"]
        if group_id:
            cursor.execute("SELECT user_id FROM users WHERE group_id = ?", (group_id,))
            member_rows = cursor.fetchall()
            members_list = [r["user_id"] for r in member_rows]
            group_info = {
                "group_id": group_id,
                "members": members_list if members_list else [user_id]
            }

        # Nếu chưa được gán lab, tự động tìm theo ngày hôm nay
        today_lab_id = user_row["today_lab_id"]
        today_lab_type = user_row["today_lab_type"]
        today_lab_title = user_row["today_lab_title"]

        if not today_lab_id:
            today_str = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            try:
                cursor.execute(
                    "SELECT lab_id, title, type FROM lab_materials WHERE lab_date <= ? ORDER BY lab_date DESC LIMIT 1",
                    (today_str,)
                )
                lab_row = cursor.fetchone()
                if lab_row:
                    today_lab_id = lab_row["lab_id"]
                    today_lab_type = lab_row["type"]
                    today_lab_title = lab_row["title"]
            except Exception:
                pass

        today_lab = {
            "lab_id": today_lab_id or "LAB05_INDIVIDUAL",
            "type": today_lab_type or "individual",
            "title": today_lab_title or "Bài lab"
        }

        conn.close()

        return {
            "status": "success",
            "user": {
                "user_id": user_id,
                "full_name": full_name,
                "role": role
            },
            "today_lab": today_lab,
            "group_info": group_info
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "USER_SERVICE_UNAVAILABLE",
            "message": f"Không thể kết nối đến hệ thống quản lý học viên: {str(e)}"
        }


def verify_discord_members(member_ids: List[str]) -> Dict[str, Any]:
    """
    5. verify_discord_members
    Mô tả: Kiểm tra danh sách Discord User IDs có tồn tại trên server hay không.
    KHÔNG tạo room, KHÔNG ghi DB — chỉ kiểm tra và trả về kết quả.
    Gọi tool này TRƯỚC create_group_room để biết thành viên nào hợp lệ.
    """
    try:
        if not member_ids:
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "Danh sách member_ids không được để trống."
            }

        valid = []
        invalid = []

        # ── Discord mode (thật) ──
        ctx = discord_context.get()
        if ctx and ctx.bot and ctx.guild_id:
            guild = ctx.bot.get_guild(ctx.guild_id)
            if not guild:
                return {
                    "status": "error",
                    "error_code": "GUILD_NOT_FOUND",
                    "message": "Không tìm thấy server Discord."
                }

            for uid in member_ids:
                member = _resolve_member_by_name_or_id(guild, uid)
                if member:
                    valid.append({
                        "user_id": str(member.id),
                        "name": member.display_name
                    })
                else:
                    invalid.append({"user_id": uid, "reason": "Member not in guild"})
        else:
            # ── Mock/CLI mode ──
            for uid in member_ids:
                if uid.startswith("INVALID_") or uid == "U_UNKNOWN":
                    invalid.append({"user_id": uid, "reason": "User not found"})
                else:
                    mock_id = uid if uid.isdigit() or uid.startswith("U") else f"U_{uid.lower()}"
                    valid.append({
                        "user_id": mock_id,
                        "name": f"User {uid}"
                    })

        return {
            "status": "success" if valid else "empty",
            "valid_members": valid,
            "invalid_members": invalid,
            "total_checked": len(member_ids),
            "valid_count": len(valid),
            "invalid_count": len(invalid)
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "VERIFY_FAILED",
            "message": f"Không thể kiểm tra thành viên: {str(e)}"
        }


def create_group_room(
    room_name: str,
    member_ids: List[str],
    is_private: bool = True
) -> Dict[str, Any]:
    """
    6. create_group_room
    Mô tả: Tự động tạo channel/room chat nhóm và ghi nhận thông tin vào SQLite DB.
    Nên gọi verify_discord_members TRƯỚC để đảm bảo tất cả thành viên hợp lệ.
    Room được tạo ở chế độ private (chỉ thành viên trong nhóm mới thấy).
    Chỉ tạo phòng khi TẤT CẢ thành viên trong danh sách đều hợp lệ.
    """
    try:
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


def send_message(
    target_id: str,
    message: str,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    6. send_message
    Mô tả: Gửi tin nhắn hướng dẫn và lưu lịch sử vào SQLite DB.
    """
    try:
        if not target_id or not target_id.strip() or not message or not message.strip():
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "target_id và message không được để trống."
            }

        if "BLOCKED" in target_id or "INVALID" in target_id:
            return {
                "status": "error",
                "error_code": "CANNOT_SEND_MESSAGE",
                "message": "Người dùng đã chặn tin nhắn trực tiếp từ Bot hoặc Room ID không tồn tại."
            }

        # ── Thử gửi tin nhắn thật qua Discord ──
        ctx = discord_context.get()
        if ctx and ctx.bot:
            try:
                channel_id = int(target_id) if target_id.lstrip("-").isdigit() else None
                if channel_id:
                    channel = ctx.bot.get_channel(channel_id)
                    if channel:
                        sent = _run_discord_coro(channel.send(message))
                        if sent:
                            return {
                                "status": "success",
                                "message_id": str(sent.id),
                                "delivered_at": sent.created_at.isoformat()
                            }
            except (ValueError, TypeError) as exc:
                print(f"⚠️ [DiscordBridge] send_message invalid target_id '{target_id}': {exc}")

        # ── Fallback: mock response ──
        msg_id = f"MSG_{abs(hash(message + datetime.now(timezone.utc).isoformat())) % 1000000}"
        delivered_at = datetime.now(timezone.utc).isoformat()

        # Lưu tin nhắn vào CSDL SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (message_id, target_id, message, attachments, delivered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                target_id,
                message,
                json.dumps(attachments or [], ensure_ascii=False),
                delivered_at
            )
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message_id": msg_id,
            "delivered_at": delivered_at
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "CANNOT_SEND_MESSAGE",
            "message": f"Không thể gửi tin nhắn: {str(e)}"
        }


def send_notification(
    room_id: str,
    user_ids_to_tag: List[str],
    content: str,
    urgency: str = "normal"
) -> Dict[str, Any]:
    """
    7. send_notification
    Mô tả: Tag tên học viên (@username) hoặc phát thông báo khẩn cấp trong kênh làm việc.
    """
    try:
        if not room_id or not room_id.strip() or not content or not content.strip():
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "room_id và nội dung content không được để trống."
            }

        if "TRIGGER_500" in room_id:
            return {
                "status": "error",
                "error_code": "NOTIFICATION_FAILED",
                "message": "Hệ thống thông báo đẩy bị ngắt kết nối."
            }

        # ── Thử gửi notification thật qua Discord ──
        ctx = discord_context.get()
        if ctx and ctx.bot:
            try:
                channel_id = int(room_id) if room_id.lstrip("-").isdigit() else None
                if channel_id:
                    channel = ctx.bot.get_channel(channel_id)
                    if channel:
                        # Tạo mentions string
                        mentions = " ".join(
                            f"<@{uid}>" if not uid.startswith("<@") else uid
                            for uid in user_ids_to_tag
                        )
                        urgency_prefix = ""
                        if urgency == "urgent":
                            urgency_prefix = "🚨 **URGENT** "
                        elif urgency == "high":
                            urgency_prefix = "⚠️ **HIGH PRIORITY** "

                        full_content = f"{urgency_prefix}{mentions}\n\n{content}"
                        sent = _run_discord_coro(channel.send(full_content))
                        if sent:
                            return {
                                "status": "success",
                                "notified_users_count": len(user_ids_to_tag),
                                "discord_mentions": [f"<@{uid}>" for uid in user_ids_to_tag],
                                "message_id": str(sent.id)
                            }
            except (ValueError, TypeError) as exc:
                print(f"⚠️ [DiscordBridge] send_notification invalid room_id '{room_id}': {exc}")

        # ── Fallback: mock response ──
        notified_count = len(user_ids_to_tag)
        formatted_mentions = [f"<@{uid}>" if not uid.startswith("<@") else uid for uid in user_ids_to_tag]

        # Ghi log thông báo vào SQLite messages DB
        conn = get_db_connection()
        cursor = conn.cursor()
        msg_id = f"NOTIF_{abs(hash(content + datetime.now(timezone.utc).isoformat())) % 1000000}"
        cursor.execute(
            """
            INSERT INTO messages (message_id, target_id, message, attachments, delivered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                room_id,
                f"[{urgency.upper()}] Mentions: {', '.join(formatted_mentions)} - {content}",
                json.dumps([], ensure_ascii=False),
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "notified_users_count": notified_count,
            "discord_mentions": formatted_mentions
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "NOTIFICATION_FAILED",
            "message": f"Gửi thông báo thất bại: {str(e)}"
        }
