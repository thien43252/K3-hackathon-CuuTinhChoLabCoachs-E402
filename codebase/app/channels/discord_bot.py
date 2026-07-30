import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

# Lấy Discord Token từ biến môi trường
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

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

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ Lỗi: Thiếu DISCORD_BOT_TOKEN trong biến môi trường (.env).")
    else:
        print("⚡ Đang khởi động Discord Bot...")
        bot.run(DISCORD_BOT_TOKEN)
