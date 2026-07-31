import asyncio
import json
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from app.core.config import settings
from app.services.repo_service import LabContentService

import os
from typing import Any
from pathlib import Path
from app.agent.providers import make_provider
from app.tools import load_tool_declarations, to_openai_tools
from app.chat import run_model_tool_loop
from app import discord_context
from app.core.db import get_db_connection

# Khởi tạo LabContentService (dùng chung toàn bot)
lab_service = LabContentService()

# Cấu hình Agent
ROOT_DIR = Path(__file__).resolve().parent.parent
system_prompt_path = ROOT_DIR / "prompt" / "system_prompt.md"
tools_path = ROOT_DIR / "prompt" / "tools.yaml"

system_prompt = ""
if system_prompt_path.exists():
    system_prompt = system_prompt_path.read_text(encoding="utf-8")

openai_tools = []
if tools_path.exists():
    tool_declarations = load_tool_declarations(tools_path)
    openai_tools = to_openai_tools(tool_declarations)

# Khởi tạo provider mặc định (nạp từ .env, fallback về openai)
default_provider_name = os.getenv("DEFAULT_PROVIDER", "openai")
AGENT_PROVIDER = make_provider(default_provider_name)

# Store lưu lịch sử hội thoại cho từng user trên Discord
user_histories = {}

# Cấu hình Intents cho Bot (Bật thêm Members Intent để quản lý user dễ dàng)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Đảm bảo đã bật Server Members Intent trên Discord Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot Discord đã kết nối thành công với tên: {bot.user}")

    # Inject bot instance vào shared context để platform_tools có thể gọi Discord API thật
    discord_context.set_bot(bot)
    discord_context.set_event_loop(bot.loop)
    print("🔗 Đã inject Discord bot context vào shared bridge.")

    try:
        # Đồng bộ Slash Commands tới từng Server (Guild) đang tham gia để lệnh xuất hiện NGAY LẬP TỨC
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"🔄 Đã đồng bộ slash commands thành công cho server: {guild.name} (ID: {guild.id})")

        await bot.tree.sync()
        print("🌍 Đã đồng bộ global slash commands.")
    except Exception as e:
        print(f"❌ Lỗi đồng bộ slash commands: {e}")
    print("--------------------------------------------------")

def call_agent_loop(messages: list[dict[str, str]]) -> dict[str, Any]:
    # Lấy model mặc định từ .env, fallback về gpt-4o-mini
    default_model_name = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    return run_model_tool_loop(
        provider=AGENT_PROVIDER,
        messages=messages,
        tools=openai_tools,
        model=default_model_name,
        max_tool_rounds=4
    )


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Log tin nhắn để debug
    print(f"📩 Nhận tin nhắn từ {message.author} tại kênh #{message.channel}: '{message.content}'")

    await bot.process_commands(message)

    # Chỉ trả lời khi bot được @mention
    if bot.user not in message.mentions:
        return

    # Cập nhật context Discord
    if message.guild:
        discord_context.set_current_channel(message.guild.id, message.channel.id)

    async with message.channel.typing():
        user_id = str(message.author.id)
        if user_id not in user_histories:
            user_histories[user_id] = []

        user_histories[user_id].append({"role": "user", "content": message.content})

        # Giới hạn lịch sử hội thoại ở mức 10 tin nhắn gần nhất (5 lượt trao đổi)
        if len(user_histories[user_id]) > 10:
            user_histories[user_id] = user_histories[user_id][-10:]

        # Xác định loại kênh: general hay group_room
        channel_type = "general"
        group_id = None
        members_info = []
        room = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rooms WHERE discord_channel_id = ?", (str(message.channel.id),))
            room = cursor.fetchone()
            conn.close()
        except Exception:
            pass

        if room:
            channel_type = "group_room"
            group_id = room["room_name"]
            # Resolve members (ID + display name)
            member_ids = []
            try:
                raw_members = room["added_members"]
                member_ids = json.loads(raw_members) if raw_members else []
            except (json.JSONDecodeError, TypeError):
                member_ids = []
            for mid in member_ids:
                try:
                    member = message.guild.get_member(int(mid))
                    if member:
                        members_info.append({"id": str(member.id), "name": member.display_name})
                    else:
                        members_info.append({"id": mid, "name": mid})
                except (ValueError, TypeError, AttributeError):
                    members_info.append({"id": mid, "name": mid})

        # Resolve lab_id từ lab_materials — dùng local date (không UTC)
        lab_id = None
        try:
            from datetime import date as dt_date
            today_local = dt_date.today().isoformat()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT lab_id FROM lab_materials WHERE lab_date <= ? ORDER BY lab_date DESC LIMIT 1",
                (today_local,)
            )
            row = cursor.fetchone()
            if row:
                lab_id = row["lab_id"]
            conn.close()
        except Exception:
            pass

        # Set context cho tools dùng (user_id, group_id, members, lab_id tự động resolve)
        discord_context.set_context(
            user_id=user_id,
            channel_type=channel_type,
            group_id=group_id,
            members=members_info,
            lab_id=lab_id,
        )

        # Build context string cho agent system prompt
        discord_ctx_str = (
            f"\n\n[Discord Context]\n"
            f"Current User: {message.author.name} (ID: {user_id})\n"
            f"Channel: {message.channel.name} (ID: {message.channel.id})\n"
            f"Channel Type: {channel_type}\n"
        )
        if lab_id:
            discord_ctx_str += f"Today Lab: {lab_id}\n"
        if group_id and members_info:
            discord_ctx_str += f"Group ID: {group_id}\n"
            discord_ctx_str += "Members in this room:\n"
            for m in members_info:
                discord_ctx_str += f"- {m['name']} (ID: {m['id']})\n"

        messages_to_send = [
            {"role": "system", "content": f"{system_prompt}{discord_ctx_str}"},
            *user_histories[user_id]
        ]

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: call_agent_loop(messages_to_send)
            )

            assistant_text = result.get("assistant_text", "Không có phản hồi từ Agent.")
            user_histories[user_id].append({"role": "assistant", "content": assistant_text})

            # Discord giới hạn tin nhắn tối đa 2000 ký tự
            if len(assistant_text) > 2000:
                for i in range(0, len(assistant_text), 1900):
                    await message.channel.send(assistant_text[i:i+1900])
            else:
                await message.channel.send(assistant_text)
        except Exception as e:
            print(f"❌ Lỗi Agent xử lý tin nhắn: {e}")
            await message.channel.send(f"❌ Trợ lý AI đang gặp sự cố khi xử lý yêu cầu của bạn: {e}")

# ==========================================
# SLASH COMMAND: /make-plan
# ==========================================

@bot.tree.command(name="make-plan", description="Tạo bản kế hoạch nháp (Draft Plan) cho một bài Lab")
@app_commands.describe(
    lab_number="Số thứ tự của bài Lab (ví dụ: 1, 2, 3...)",
    requirement="Yêu cầu cụ thể của bạn cho bản kế hoạch này (ví dụ: công nghệ sử dụng, phân công...)"
)
async def make_plan(interaction: discord.Interaction, lab_number: int, requirement: str):
    # 1. Kiểm tra xem lệnh có được chạy trong kênh nhóm riêng tư (room) đã được tạo hay không
    channel_id = str(interaction.channel.id)
    
    def check_room_exists():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT room_name, added_members FROM rooms WHERE discord_channel_id = ?", (channel_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    loop = asyncio.get_event_loop()
    room_row = await loop.run_in_executor(None, check_room_exists)
    
    if not room_row:
        await interaction.response.send_message(
            "🚫 **Lệnh không hợp lệ:** Lệnh `/make-plan` chỉ có thể được sử dụng bên trong các kênh nhóm riêng tư (Group Room) đã được Bot tạo thành công.\n"
            "Vui lòng tạo phòng nhóm trước bằng cách nhắn tin yêu cầu Bot (ví dụ: *'tạo nhóm tên là Team A gồm U123456, U789012'*).",
            ephemeral=True
        )
        return

    # Defer để chờ gọi AI
    await interaction.response.defer(ephemeral=False)

    try:
        # Gọi AI Agent complete để sinh kế hoạch dựa trên đề bài và yêu cầu cụ thể
        default_model_name = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
        
        system_prompt_text = (
            "Bạn là chuyên gia phân tích và xây dựng kế hoạch học tập cho sinh viên. "
            "Hãy lập một bản kế hoạch nháp (Draft Plan) chi tiết cho bài Lab dựa trên số thứ tự bài Lab và yêu cầu cụ thể của học viên. "
            "Phân tích lộ trình 6 Checkpoint (CP1 đến CP6) dựa trên yêu cầu đặc thù của người dùng. "
            "Định dạng Markdown rõ ràng, chuyên nghiệp, hấp dẫn."
        )
        user_prompt_text = (
            f"Lập kế hoạch nháp cho bài Lab {lab_number}.\n"
            f"Yêu cầu đặc thù của học viên: {requirement}"
        )
        
        response = await loop.run_in_executor(
            None,
            lambda: AGENT_PROVIDER.complete(
                messages=[
                    {"role": "system", "content": system_prompt_text},
                    {"role": "user", "content": user_prompt_text}
                ],
                model=default_model_name
            )
        )
        
        plan_content = response.text or "Không thể khởi tạo kế hoạch nháp từ AI."
        
        await interaction.followup.send(
            f"📋 **BẢN KẾ HOẠCH DRAFT - HỌC PHẦN LAB {lab_number}**\n"
            f"*Dành cho phòng nhóm: **{room_row['room_name']}***\n"
            f"--------------------------------------------------\n"
            f"{plan_content}"
        )
    except Exception as e:
        print(f"❌ Lỗi khi sinh kế hoạch /make-plan: {e}")
        await interaction.followup.send(f"❌ Lỗi hệ thống khi khởi tạo kế hoạch nháp: {str(e)}")

# ==========================================
# ADMIN SLASH COMMANDS: Quản lý Lab Repository
# ==========================================

@bot.tree.command(name="admin-add-lab", description="[ADMIN] Đăng ký một repo GitHub Lab mới vào hệ thống")
@app_commands.describe(
    lab_id="Mã định danh bài Lab (ví dụ: lab5, DAY05)",
    repo_url="Link GitHub của bài Lab (ví dụ: https://github.com/org/repo)",
    lab_date="Ngày của bài Lab (định dạng YYYY-MM-DD)",
    branch="Nhánh git cần clone (để trống = nhánh mặc định)"
)
@app_commands.checks.has_permissions(administrator=True)
async def admin_add_lab(interaction: discord.Interaction, lab_id: str, repo_url: str, lab_date: str, branch: str = None):
    """Chỉ Admin mới được dùng. Phân tích tài liệu 1 lần duy nhất và lưu vào cache."""
    # Defer để tránh timeout khi clone repo lâu
    await interaction.response.defer(ephemeral=True)

    try:
        # Chạy blocking I/O trong thread pool để không block event loop Discord
        loop = asyncio.get_event_loop()
        lab_data = await loop.run_in_executor(
            None,
            lambda: lab_service.register_lab(repo_url=repo_url, lab_id=lab_id, branch=branch)
        )

        # Thêm/Cập nhật thông tin vào bảng lab_materials trong SQLite
        # để agent có thể resolve lab hôm nay theo lab_date
        title = lab_data["sitemap"][0]["title"] if lab_data.get("sitemap") else f"Bài lab {lab_id}"
        description = lab_data.get("insights", {}).get("lab_objective", f"Nội dung bài lab {lab_id}")
        lab_type = "group" if "group" in lab_id.lower() or "group" in repo_url.lower() else "individual"
        created_at = datetime.now(timezone.utc).isoformat()

        def save_to_db():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM lab_materials WHERE lab_id = ?", (lab_id,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute(
                    """
                    UPDATE lab_materials 
                    SET title = ?, type = ?, description = ?, codebase_repo_url = ?, lab_date = ?, created_at = ?
                    WHERE lab_id = ?
                    """,
                    (title, lab_type, description, repo_url, lab_date, created_at, lab_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO lab_materials (lab_id, title, type, description, lecture_files, codebase_repo_url, created_at, lab_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (lab_id, title, lab_type, description, json.dumps([]), repo_url, created_at, lab_date)
                )
            conn.commit()
            conn.close()

        await loop.run_in_executor(None, save_to_db)

        # Tạo danh sách file tài liệu tìm được
        sitemap_text = "\n".join(
            [f"  • `{doc['relative_path']}` — {doc['title']}" for doc in lab_data["sitemap"]]
        )

        await interaction.followup.send(
            f"✅ **Đã đăng ký thành công Lab `{lab_id}`!**\n"
            f"📅 Ngày bắt đầu: {lab_date}\n"
            f"🔗 Repo: {repo_url}\n"
            f"📚 Tìm thấy **{lab_data['total_documents']}** tài liệu hướng dẫn:\n"
            f"{sitemap_text}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Lỗi khi đăng ký Lab `{lab_id}`:\n```{str(e)}```",
            ephemeral=True
        )

@admin_add_lab.error
async def admin_add_lab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "🚫 Bạn không có quyền dùng lệnh này. Chỉ Admin mới được phép đăng ký Lab.",
            ephemeral=True
        )

@bot.tree.command(name="admin-list-labs", description="[ADMIN] Xem danh sách toàn bộ Lab đã được đăng ký")
@app_commands.checks.has_permissions(administrator=True)
async def admin_list_labs(interaction: discord.Interaction):
    """Liệt kê toàn bộ các Lab đã được đăng ký trong hệ thống."""
    registered_labs = lab_service.list_registered_labs()

    if not registered_labs:
        await interaction.response.send_message(
            "📭 Chưa có Lab nào được đăng ký. Hãy dùng `/admin-add-lab` để thêm mới.",
            ephemeral=True
        )
        return

    lab_list_text = "\n".join(
        [f"  `{lab['lab_id']}` — {lab['repo_url']} ({lab['total_documents']} tài liệu)" for lab in registered_labs]
    )
    await interaction.response.send_message(
        f"📋 **Danh sách Lab đã đăng ký ({len(registered_labs)}):**\n{lab_list_text}",
        ephemeral=True
    )

@admin_list_labs.error
async def admin_list_labs_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "🚫 Bạn không có quyền dùng lệnh này. Chỉ Admin mới được xem danh sách Lab.",
            ephemeral=True
        )


# ==========================================
# ADMIN SLASH COMMANDS: Gán Lab cho User
# ==========================================

@bot.tree.command(name="admin-assign-lab", description="[ADMIN] Gán một bài lab cho user (để user có lab khi hỏi bot)")
@app_commands.describe(
    user_id="Discord User ID của học viên",
    lab_id="Mã bài lab cần gán (ví dụ: 01, DAY05, LAB05_GROUP)",
    lab_type="Loại lab: individual hoặc group (mặc định individual)",
    lab_title="Tiêu đề lab (để trống tự lấy từ lab_materials)"
)
@app_commands.checks.has_permissions(administrator=True)
async def admin_assign_lab(interaction: discord.Interaction, user_id: str, lab_id: str, lab_type: str = "individual", lab_title: str = ""):
    await interaction.response.defer(ephemeral=True)
    try:
        from app.tools.admin_tools import assign_lab_to_user
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: assign_lab_to_user(user_id=user_id, lab_id=lab_id, lab_type=lab_type, lab_title=lab_title)
        )
        if result["status"] == "success":
            await interaction.followup.send(
                f"✅ {result['message']}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ {result['message']}",
                ephemeral=True
            )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Lỗi: {str(e)}",
            ephemeral=True
        )

@admin_assign_lab.error
async def admin_assign_lab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "🚫 Bạn không có quyền dùng lệnh này. Chỉ Admin mới được gán lab.",
            ephemeral=True
        )


# ==========================================
# SLASH COMMAND: Cập nhật tiến độ (không qua LLM)
# ==========================================

@bot.tree.command(name="update-progress", description="Cập nhật tiến độ task của bạn (không cần AI)")
@app_commands.describe(
    task_id="Mã task cần cập nhật (ví dụ: T1, T2, CT1)",
    status="Trạng thái mới: in_progress hoặc completed (mặc định: completed)",
    checklist_done="Số checklist đã hoàn thành (tùy chọn, mặc định = tổng nếu status=completed)",
)
async def update_progress(
    interaction: discord.Interaction,
    task_id: str,
    status: str = "completed",
    checklist_done: int = None,
):
    """Tự động cập nhật tiến độ — không gọi AI, không chờ LLM."""
    # Kiểm tra channel có phải group room không
    channel_id = str(interaction.channel.id)

    def check_room_and_update():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT room_name FROM rooms WHERE discord_channel_id = ?", (channel_id,))
        room = cursor.fetchone()
        if not room:
            conn.close()
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Lệnh này chỉ dùng được trong group room."}
        group_id = room["room_name"]
        user_id = str(interaction.user.id)
        conn.close()

        # Gọi trực tiếp update_group_progress (không qua LLM)
        from app.tools.task_tools import update_group_progress as ugp
        return ugp(
            task_id=task_id,
            status=status if status in ("in_progress", "completed") else None,
            completed_checklist=checklist_done,
        )

    await interaction.response.defer(ephemeral=True)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, check_room_and_update)

        if result["status"] == "success":
            msg = (
                f"✅ **Đã cập nhật tiến độ!**\n"
                f"• Task: `{task_id}` → **{result.get('new_status', status)}**\n"
                f"• Checklist: {result.get('completed_checklist', '?')}/{result.get('total_checklist', '?')}\n"
                f"• Team progress: **{result.get('overall_team_progress_pct', 0)}%**"
            )
        elif result.get("error_code") == "NO_CONTEXT":
            msg = "🚫 Bạn chỉ có thể dùng lệnh này trong group room do bot tạo."
        elif result.get("error_code") == "NO_ASSIGNMENT_FOUND":
            msg = f"❌ Không tìm thấy task `{task_id}` cho bạn. Hãy kiểm tra lại mã task hoặc nhờ leader tạo plan."
        else:
            msg = f"❌ Lỗi: {result.get('message', 'Không xác định')}"

        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi hệ thống: {str(e)}", ephemeral=True)


# ==========================================
# SLASH COMMAND: Xem tiến độ (không qua LLM)
# ==========================================

@bot.tree.command(name="view-progress", description="Xem tiến độ làm lab của nhóm (không cần AI)")
async def view_progress(interaction: discord.Interaction):
    """Xem tiến độ nhóm — không gọi AI, không chờ LLM."""
    channel_id = str(interaction.channel.id)

    def check_room_and_track():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT room_name FROM rooms WHERE discord_channel_id = ?", (channel_id,))
        room = cursor.fetchone()
        conn.close()
        if not room:
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Lệnh này chỉ dùng được trong group room."}

        # Set context + call track_group_progress
        from app import discord_context
        from app.tools.task_tools import track_group_progress as tgp
        discord_context.set_context(group_id=room["room_name"], channel_type="group_room")
        try:
            return tgp()
        finally:
            discord_context.clear_context()

    await interaction.response.defer(ephemeral=True)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, check_room_and_track)

        if result["status"] == "success":
            bar = result.get("progress_bar", "")
            pct = result.get("overall_completion_percent", 0)
            done = result.get("completed_tasks", 0)
            total = result.get("total_tasks", 0)
            msg = (
                f"📊 **Tiến độ nhóm**\n"
                f"{bar}\n"
                f"• Hoàn thành: **{done}/{total}** task ({pct}%)\n"
            )
            # Thêm breakdown từng member
            members = result.get("members_progress", [])
            if members:
                by_user = {}
                for m in members:
                    uid = m["user_id"]
                    if uid not in by_user:
                        by_user[uid] = {"done": 0, "total": 0}
                    by_user[uid]["done"] += 1 if m["status"] == "completed" else 0
                    by_user[uid]["total"] += 1
                msg += "\n**Thành viên:**\n"
                for uid, st in by_user.items():
                    msg += f"• <@{uid}>: {st['done']}/{st['total']} tasks\n"
        elif result.get("error_code") == "NO_CONTEXT":
            msg = "🚫 Bạn chỉ có thể dùng lệnh này trong group room do bot tạo."
        elif result.get("error_code") == "NO_PLAN":
            msg = "📭 Nhóm chưa chốt kế hoạch. Hãy nhờ leader tạo plan trước."
        else:
            msg = f"❌ {result.get('message', 'Không xác định')}"

        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi hệ thống: {str(e)}", ephemeral=True)


# ==========================================
# CÁC HÀM HELPER XỬ LÝ KÊNH (CHANNELS)
# ==========================================

async def create_discord_channel(guild: discord.Guild, channel_name: str, category_name: str = None) -> discord.TextChannel:
    category = None
    if category_name:
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            print(f"📁 Đã tạo Category mới: '{category_name}'")
            
    channel = await guild.create_text_channel(name=channel_name, category=category)
    print(f"💬 Đã tạo Text Channel mới: '{channel_name}'")
    return channel

async def create_private_channel_for_user(guild: discord.Guild, channel_name: str, member: discord.Member, category_name: str = None) -> discord.TextChannel:
    category = None
    if category_name:
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True)
    }

    channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)
    print(f"🔒 Đã tạo kênh riêng tư '{channel_name}' cho user {member.name}")
    return channel

# ==========================================
# CÁC TEST COMMANDS (Prefix: test-xxx)
# ==========================================

@bot.command(name="test-create-room")
@commands.has_permissions(manage_channels=True)
async def test_create_room(ctx, room_name: str, category_name: str = None):
    """
    Test: !test-create-room <tên_phòng> <tên_category_nếu_có>
    """
    try:
        channel = await create_discord_channel(ctx.guild, room_name, category_name)
        await ctx.send(f"🧪 [TEST CREATE] Đã tạo kênh thành công: {channel.mention}")
    except Exception as e:
        await ctx.send(f"❌ [TEST CREATE] Lỗi: {e}")

@bot.command(name="test-private-room")
@commands.has_permissions(manage_channels=True)
async def test_private_room(ctx, room_name: str, member: discord.Member, category_name: str = None):
    """
    Test: !test-private-room <tên_phòng> <mention_hoặc_id_user> <tên_category_nếu_có>
    """
    try:
        channel = await create_private_channel_for_user(ctx.guild, room_name, member, category_name)
        await ctx.send(f"🧪 [TEST PRIVATE] Đã tạo phòng riêng tư cho {member.mention}: {channel.mention}")
        await channel.send(f"👋 Xin chào {member.mention}! Đây là kênh test được tạo riêng cho bạn.")
    except Exception as e:
        await ctx.send(f"❌ [TEST PRIVATE] Lỗi: {e}")

def start_bot():
    if not settings.discord_bot_token:
        print("❌ Lỗi: Thiếu DISCORD_BOT_TOKEN trong file .env hoặc cấu hình config.py.")
    else:
        print("⚡ Đang khởi động Discord Bot...")
        bot.run(settings.discord_bot_token)

if __name__ == "__main__":
    start_bot()
