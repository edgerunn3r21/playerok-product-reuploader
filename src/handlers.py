import json
import asyncio
import os
import traceback
import logging

import database as db

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from filters import IsAdmin
from keyboards import get_callback_btns
from playerok import Playerok
from utils import reupload_products

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdmin())

playerok = Playerok()

parser_taks = None


def panel_keyboard() -> dict:
    panel_buttons = {
        "🔐 Авторизація 🔐": "auth",
        "✏️ Редагувати ключові слова ✏️": "edit_keywords",
    }

    if parser_taks and not parser_taks.done():
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
        if parser_taks and not parser_taks.done():
            await callback.answer(
                "❌ Парсер вже запущено. Вимкніть його перед авторизацією."
            )
            return

        if os.path.exists(playerok.storage_state_path):
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
        if os.path.exists(playerok.storage_state_path):
            os.remove(playerok.storage_state_path)

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

        await playerok.initialize_browser()
        result = await playerok.auth_first(email)

        if result == "email":
            await message.answer("❌ Помилка при авторизації. Перевірте email.")
            return
        elif result == "repeat":
            await message.answer(
                "❌ Занадто частий запит на авторизаційний код. Спробуйте пізніше."
            )
            return

        if not playerok.page:
            await message.answer("❌ Помилка при ініціалізації браузера.")
            return

        await message.answer("🔐 Введіть код з SMS для завершення авторизації:")
        await state.set_state(AuthState.code)
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")


@router.message(AuthState.code)
async def auth_code(message: Message, state: FSMContext, session: AsyncSession):
    try:
        code = message.text.strip()
        if not code:
            await message.answer("❌ Код не може бути порожнім.")
            return

        await playerok.auth_second(code)
        if not playerok.page:
            await message.answer("❌ Помилка при авторизації.")
            return

        await playerok.initialize_browser()
        if await playerok.check_auth():
            await message.answer("✅ Авторизація успішна!")
            await panel(message, state, session)
        else:
            await message.answer("❌ Авторизація не вдалася. Перевірте дані.")
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")


@router.callback_query(F.data == "enable_parser")
async def enable_parser(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        global parser_taks

        if parser_taks and not parser_taks.done():
            await callback.answer("❌ Парсер вже запущено.")
            return
        else:
            await callback.message.edit_text("🔐 Провіряю авторизацію...")
            if not os.path.exists(playerok.storage_state_path):
                await callback.message.answer(
                    "❌ Ви не авторизовані. Будь ласка, спочатку авторизуйтесь."
                )
                return
            
            await playerok.initialize_browser()
            if not await playerok.check_auth():
                await callback.message.answer(
                    "❌ Ви не авторизовані. Будь ласка, спочатку авторизуйтесь."
                )
                return
            await callback.message.answer("✅ Авторизація є, продовжую...")

            await callback.message.answer("🔄 Виконую фіксування наявних карт...")
            if os.path.exists("src/storage/fix_cards.json"):
                os.remove("src/storage/fix_cards.json")

            await playerok.initialize_browser()
            fix_cards = await playerok.get_cards()
            fix_cards_urls = [url for _, url in fix_cards]

            with open("src/storage/fix_cards.json", "w", encoding="utf-8") as f:
                json.dump(fix_cards_urls, f, ensure_ascii=False, indent=4)

            await callback.message.answer("✅ Фіксування карт виконано")
            await callback.message.answer("🚀 Запускаю парсер...")

            parser_taks = asyncio.create_task(
                reupload_products(playerok, session, callback.message)
            )
            await callback.message.edit_text("✅ Парсер увімкнено")

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
        global parser_taks
        if not parser_taks or parser_taks.done():
            await callback.answer("❌ Парсер вже вимкнено.")
            return
        else:
            parser_taks.cancel()
            parser_taks = None

            await callback.message.edit_text("Парсер вимкнено ❌")

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


@router.message(Command("cards"))
async def get_cards(message: Message, state: FSMContext, session: AsyncSession):
    try:
        await playerok.initialize_browser()
        cards = await playerok.get_cards()
        if not cards:
            await message.answer("❌ Не вдалося отримати карти.")
            return

        keywords = await db.orm_read(session, db.Keyword, as_iterable=True)

        if keywords:
            cards = [
                card
                for card in cards
                if any(keyword.keyword in card for keyword in keywords)
            ]
            if not cards:
                await message.answer(
                    "❌ Не знайдено карт, що відповідають ключовим словам."
                )
                return

    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())
        await message.answer("Виникла помилка 😞...")
