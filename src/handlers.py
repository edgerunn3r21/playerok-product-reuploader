import json
import asyncio
import os
import traceback
import logging

import database as db

from aiogram import Bot, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from filters import IsAdmin
from keyboards import get_callback_btns
from playerok import Playerok
from utils import reupload_products
from config import admin_list
from cron import scheduler

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdmin())

playerok = Playerok()


def panel_keyboard() -> dict:
    panel_buttons = {
        "🔐 Авторизація 🔐": "auth",
        "✏️ Редагувати ключові слова ✏️": "edit_keywords",
    }

    if scheduler.get_job("reupload_products_job"):
        panel_buttons.update({"⛔ Вимкнути парсер ⛔": "disable_parser"})
    else:
        panel_buttons.update({"▶️ Увімкнути парсер ▶️": "enable_parser"})

    return panel_buttons


@router.message(CommandStart())
async def panel(message: Message, state: FSMContext, session: AsyncSession):
    try:
        await state.clear()

        # Check if the user exists in the database
        tg_id = str(message.from_user.id)
        username = message.from_user.username
        user = await db.orm_read(session, db.User, as_iterable=False, tg_id=tg_id)

        if not user:
            result = await db.orm_create(
                session, db.User, {"tg_id": tg_id, "username": username}
            )

            if result:
                user = await db.orm_read(
                    session, db.User, as_iterable=False, tg_id=tg_id
                )

        await message.answer(
            "⚙️ Панель управління",
            reply_markup=get_callback_btns(btns=panel_keyboard(), sizes=(1,)),
        )
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "panel")
async def callback_panel(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.edit_text(
            "⚙️ Панель управління",
            reply_markup=get_callback_btns(btns=panel_keyboard(), sizes=(1,)),
        )
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.answer("Виникла помилка 😞...")


class AuthState(StatesGroup):
    email = State()
    code = State()


@router.callback_query(F.data == "auth")
async def auth(callback: CallbackQuery, state: FSMContext):
    try:
        if scheduler.get_job("reupload_products_job"):
            await callback.answer(
                "❌ Парсер вже запущено. Вимкніть його перед авторизацією."
            )
            return

        if os.path.exists(playerok.storage_cookies_path):
            btns = {
                "✅ Так": "auth_update",
                "❌ Ні": "panel",
            }
            await callback.message.edit_text(
                "❌ Ви вже авторизовані. Хочете оновити аккаунт?",
                reply_markup=get_callback_btns(btns=btns, sizes=(1,)),
            )
        else:
            await callback.message.edit_text(
                "🔐 Введіть email для авторизації на Playerok:"
            )
            await state.set_state(AuthState.email)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "auth_update")
async def auth_update(callback: CallbackQuery, state: FSMContext):
    try:
        if os.path.exists(playerok.storage_cookies_path):
            os.remove(playerok.storage_cookies_path)

        await callback.message.edit_text(
            "🔐 Введіть email для авторизації на Playerok:"
        )
        await state.set_state(AuthState.email)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


@router.message(AuthState.email)
async def auth_email(message: Message, state: FSMContext):
    try:
        email = message.text.strip()
        if not email:
            await message.answer("❌ Email не може бути порожнім.")
            return

        result = playerok.get_email_auth_code(email)

        if not result:
            await message.answer("❌ Помилка при авторизації. Спробуйте пізніше.")
            return

        await message.answer("🔐 Введіть код з SMS для завершення авторизації:")
        await state.update_data(email=email)
        await state.set_state(AuthState.code)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")


@router.message(AuthState.code)
async def auth_code(message: Message, state: FSMContext, session: AsyncSession):
    try:
        code = message.text.strip()
        data = await state.get_data()
        email = data.get("email", None)

        if not code:
            await message.answer("❌ Код не може бути порожнім.")
            return

        print(f"Email: {email}, Code: {code}")  # Debugging line
        result = playerok.verify_email_code(email, code)

        if not result:
            await message.answer("❌ Помилка при авторизації. Перевірте код.")
            return
        else:
            await message.answer("✅ Авторизація успішна!")
            await panel(message, state, session)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "enable_parser")
async def enable_parser(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
):
    try:
        if scheduler.get_job("reupload_products_job"):
            await callback.answer("❌ Парсер вже запущено.")
            return
        else:
            await callback.message.edit_text("🔐 Провіряю авторизацію...")
            if not os.path.exists(playerok.storage_cookies_path):
                await callback.message.answer(
                    "❌ Ви не авторизовані. Будь ласка, спочатку авторизуйтесь."
                )
                return

            await callback.message.answer("🚀 Парсер запущений")

            keywords = await db.orm_read(session, db.Keyword, as_iterable=True)
            if not keywords:
                await callback.message.answer(
                    "❌ Немає ключових слів для парсингу. Будь ласка, додайте їх."
                )
                return

            keywords = [keyword.keyword for keyword in keywords]
            admin_ids = admin_list.split(",")

            scheduler.add_job(
                reupload_products,
                "interval",
                minutes=3,
                id="reupload_products_job",
                args=[playerok, keywords, bot, admin_ids],
                replace_existing=True,
            )

        await panel(callback.message, state, session)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "disable_parser")
async def disable_parser(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        job = scheduler.get_job("reupload_products_job")
        if not job:
            await callback.answer("❌ Парсер вже вимкнено.")
            return
        else:
            scheduler.remove_job("reupload_products_job")
            await callback.answer("Парсер вимкнено ❌")

        await panel(callback.message, state, session)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "edit_keywords")
async def edit_keywords(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        keyword_list = await db.orm_read(session, db.Keyword, as_iterable=True)
        keyword_buttons = {
            "➕ Додати ключові слова": "add_keywords",
            "➖ Видалити ключові слова": "delete_keywords",
            "⬅️ Назад": "panel",
        }
        message_text = "🔑 Ключові слова 🔑\n\n"

        if keyword_list:
            for keyword in keyword_list:
                message_text += f"{keyword.keyword}\n"

        await callback.message.edit_text(
            message_text,
            reply_markup=get_callback_btns(btns=keyword_buttons, sizes=(1,)),
        )
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


class EditKeywordsState(StatesGroup):
    keyword = State()


@router.callback_query(F.data == "add_keywords")
async def edit_keywords(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(
            "🔑 Введіть ключові слова для парсингу (через кому):"
        )
        await state.set_state(EditKeywordsState.keyword)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


@router.message(EditKeywordsState.keyword)
async def set_keywords(message: Message, state: FSMContext, session: AsyncSession):
    try:
        keywords = message.text.split(",")
        keywords = [keyword.strip() for keyword in keywords if keyword.strip()]

        if not keywords:
            await message.answer("❌ Ключові слова не можуть бути порожніми.")
            return

        for keyword in keywords:
            result = await db.orm_create(session, db.Keyword, {"keyword": keyword})
            if not result:
                await message.answer(
                    f"❌ Помилка при додаванні ключового слова: {keyword}"
                )
                return

        await message.answer(f"✅ Ключові слова встановлено: {', '.join(keywords)}")

        await state.clear()
        await panel(message, state, session)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "delete_keywords")
async def delete_keywords(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        keyword_list = await db.orm_read(session, db.Keyword, as_iterable=True)
        if not keyword_list:
            await callback.answer("❌ Немає ключових слів для видалення ❌")
            return

        btns = {
            "⬅️ Назад": "edit_keywords",
        }

        for keyword in keyword_list:
            btns[keyword.keyword] = f"delete_keyword_{keyword.pk}"

        await callback.message.edit_text(
            "👇 Виберіть ключові слова для видалення 👇",
            reply_markup=get_callback_btns(
                btns=btns,
                sizes=(1,),
            ),
        )
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")


@router.callback_query(F.data.startswith("delete_keyword_"))
async def delete_keyword(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        pk = int(callback.data.split("_")[-1])
        result = await db.orm_delete(session, db.Keyword, pk)
        if result:
            await callback.answer("✅ Ключове слово видалено")
        else:
            await callback.answer("❌ Помилка при видаленні ключового слова")

        await delete_keywords(callback, state, session)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await callback.message.answer("Виникла помилка 😞...")
