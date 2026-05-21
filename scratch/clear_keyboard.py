import asyncio
from telegram import Bot, ReplyKeyboardRemove


async def clear_keyboard():
    token = "8497074584:AAEnlYC1mrYZVs5qqDFV858xPP5tRJkSpvA"
    chat_id = 6838073664
    bot = Bot(token=token)

    try:
        # Send a message that removes the keyboard
        await bot.send_message(
            chat_id=chat_id,
            text="🧹 Curățăm rămășițele rusești... Tastatura a fost eliminată!",
            reply_markup=ReplyKeyboardRemove(),
        )
        print("✅ Keyboard removal message sent.")

        # Try to unpin the Sherlock message
        # Note: Bots can only unpin messages they pinned, or if they are admins.
        # But let's try anyway.
        try:
            await bot.unpin_all_chat_messages(chat_id=chat_id)
            print("✅ Tried to unpin all messages.")
        except Exception as e:
            print(f"⚠️ Could not unpin: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(clear_keyboard())
