from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram import Bot

private = [
    BotCommand(command="start", description="Панель"),
]


async def set_admin_commands(admin_list: list, bot: Bot):
    for admin in admin_list:
        scope = BotCommandScopeChat(chat_id=admin)
        await bot.set_my_commands(private, scope=scope)