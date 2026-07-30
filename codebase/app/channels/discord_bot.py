import discord
from discord.ext import commands
from discord import app_commands
from app.core.config import settings

# Cấu hình Intents cho Bot (Bật thêm Members Intent để quản lý user dễ dàng)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Đảm bảo đã bật Server Members Intent trên Discord Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot Discord đã kết nối thành công với tên: {bot.user}")
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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Log tin nhắn để debug
    print(f"📩 Nhận tin nhắn từ {message.author} tại kênh #{message.channel}: '{message.content}'")

    await bot.process_commands(message)

    # Chỉ trả lời tin nhắn thường nếu KHÔNG bắt đầu bằng dấu command !
    if not message.content.startswith("!"):
        mock_reply = (
            f"👋 Xin chào {message.author.mention}! Cảm ơn bạn đã nhắn tin.\n"
            f"🤖 [MOCK DATA] Tôi đã nhận được yêu cầu của bạn: '{message.content}'.\n"
            f"💡 Phân hệ AI xử lý logic sẽ sớm được tích hợp ở đây."
        )
        await message.channel.send(mock_reply)

# ==========================================
# SLASH COMMAND: /make-plan
# ==========================================

@bot.tree.command(name="make-plan", description="Tạo bản kế hoạch nháp (Draft Plan) cho một bài Lab")
@app_commands.describe(lab_number="Số thứ tự của bài Lab (ví dụ: 1, 2, 3...)")
async def make_plan(interaction: discord.Interaction, lab_number: int):
    plan_content = (
        f"📋 **BẢN KẾ HOẠCH DRAFT - HỌC PHẦN LAB {lab_number}**\n"
        f"*Dựa trên tài liệu hướng dẫn và lịch trình dự án (README.md)*\n"
        f"--------------------------------------------------\n"
        f"🏆 **Mục tiêu chính:** Hoàn thành bài toán thực chiến Lab {lab_number} theo quy trình 6 mốc Checkpoint.\n\n"
        f"⏱️ **Lịch trình và Các cột mốc quan trọng:**\n"
        f"1️⃣ **CP1 (09:00 - 10:00 Ngày 1) - Chốt Canvas:**\n"
        f"   - Xác định rõ Job Executor, Job Story.\n"
        f"   - Tìm ra Painpoint có bằng chứng (Khảo sát ≥20 người / Mining data).\n"
        f"   - Chọn lát cắt 1 câu: *1 user · 1 việc · 1 quyết định AI · 1 kết quả*.\n\n"
        f"2️⃣ **CP2 (10:00 - 12:00 Ngày 1) - Interactive Flow:**\n"
        f"   - Dựng khung UI/UX cơ bản (có thể mock data, flow bấm đi hết được).\n"
        f"   - Phân chia nhiệm vụ cụ thể cho từng thành viên trong nhóm.\n\n"
        f"3️⃣ **CP3 (12:00 - 16:00 Ngày 1) - AI Integration & First Eval:**\n"
        f"   - Tích hợp ít nhất 1 lệnh gọi AI chạy thực tế.\n"
        f"   - Thiết lập bộ dữ liệu kiểm thử (Golden Set ≥20 cases) và thực hiện đo lường lượt 1.\n\n"
        f"4️⃣ **CP4 (16:00 - 17:30 Ngày 1) - Đo đạc & Khóa Spec:**\n"
        f"   - Xác định 4 lớp chỗ khó & 8 kịch bản lỗi tiềm năng.\n"
        f"   - Chốt chất lượng (Quality Bar) và nộp tài liệu `spec.md` trước hạn chót 23:59.\n\n"
        f"5️⃣ **CP5 (09:00 Ngày 2) - Validation & Dry Run:**\n"
        f"   - Kiểm thử thực tế với ít nhất 5 người dùng ngoài nhóm, ghi log phản hồi.\n"
        f"   - Chạy thử Demo (Dry Run) canh thời gian chính xác trong 5 phút.\n\n"
        f"6️⃣ **CP6 (10:00 Ngày 2) - Final Demo:**\n"
        f"   - Trình bày Slide 6 trang và chạy live demo (bao gồm cả trường hợp lỗi được xử lý).\n\n"
        f"📝 *Lời khuyên:* Hãy bám sát rubric chấm điểm (04-rubric.md) để tối ưu hóa điểm số của nhóm!"
    )
    await interaction.response.send_message(plan_content)

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
