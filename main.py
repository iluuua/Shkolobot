from bot.telegram_bot import dp, bot
from config.config import logger
from database.database import init_db
import asyncio

async def main():
    logger.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    init_db()

    asyncio.run(main())