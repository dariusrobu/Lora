import asyncio
from telegram import Bot

TELEGRAM_BOT_TOKEN = "8497074584:AAGtpjl_1ftfTIFIw0X5jSDN03kF6y7kSTs"


async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    text = r"Nu ai niciun task activ în acest moment\! 🎉\nPoți adăuga unul nou prin limbaj natural sau folosind butonul de mai jos\."
    try:
        await bot.send_message(chat_id=6838073664, text=text, parse_mode="MarkdownV2")
        print("Empty text SUCCESS")
    except Exception as e:
        print(f"Empty text ERROR: {e}")

    total = 5
    projects_list = ["Work", "Personal"]
    overdue = 1

    lines = ["📋 *Tasks Overview*\n"]
    lines.append(r"🔴 *Task restant:* Buy oat milk")
    lines.append(rf"✅ *{total}* task\-uri active pe *{len(projects_list)}* proiecte\.")
    lines.append(rf"🔴 *{overdue}* sunt restante\!")
    lines.append("\n*Repartiție pe proiecte:*")
    for proj in projects_list:
        lines.append(f"• {proj}: 1")

    full_text = "\n".join(lines)
    try:
        await bot.send_message(
            chat_id=6838073664, text=full_text, parse_mode="MarkdownV2"
        )
        print("Full text SUCCESS")
    except Exception as e:
        print(f"Full text ERROR: {e}")


asyncio.run(main())
