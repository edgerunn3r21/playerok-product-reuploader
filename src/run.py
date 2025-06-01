import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommandScopeAllPrivateChats
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from middlewares import DataBaseSession
from database import create_db, drop_db, session_maker
from handlers import router
from common import set_admin_commands
from config import token, admin_list

# Create directories if they don't exist
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

admin_list = admin_list.replace(" ", "").split(",") if admin_list else None
bot.my_admins_list = admin_list if admin_list else []

dp = Dispatcher()
dp.include_router(router)


async def on_startup():
    # if you want to clear your database, delete the comment await drop_dp()
    # await drop_db()
    await create_db()


async def on_shutdown():
    logger.info("Bot down")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)

    if admin_list:
        await set_admin_commands(admin_list, bot)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.error("Bot stopped!")