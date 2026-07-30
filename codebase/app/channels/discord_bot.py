import discord
from discord.ext import commands
from app.core.config import settings

# Cấu hình Intents cho Bot (cần bật Message Content Intent trên Discord Developer Portal)
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot Discord đã kết nối thành công với tên: {bot.user}")
    print("--------------------------------------------------")

@bot.event
async def on_message(message):
    # Tránh trường hợp bot tự trả lời tin nhắn của chính nó
    if message.author == bot.user:
        return

    # Log tin nhắn nhận được để tiện theo dõi/debug
    print(f"📩 Nhận tin nhắn từ {message.author} tại kênh #{message.channel}: '{message.content}'")

    # TODO: Tích hợp logic AI xử lý intent (chào hỏi / hỏi logistics / hỏi bài)
    # Hiện tại đang trả về dữ liệu mock
    mock_reply = (
        f"👋 Xin chào {message.author.mention}! Cảm ơn bạn đã nhắn tin.\n"
        f"🤖 [MOCK DATA] Tôi đã nhận được yêu cầu của bạn: '{message.content}'.\n"
        f"💡 Phân hệ AI xử lý logic sẽ sớm được tích hợp ở đây."
    )

    # Gửi phản hồi mock lại kênh chat
    await message.channel.send(mock_reply)

    # Xử lý các command khác nếu có
    await bot.process_commands(message)

def start_bot():
    if not settings.discord_bot_token:
        print("❌ Lỗi: Thiếu DISCORD_BOT_TOKEN trong file .env hoặc cấu hình config.py.")
    else:
        print("⚡ Đang khởi động Discord Bot...")
        bot.run(settings.discord_bot_token)

if __name__ == "__main__":
    start_bot()
