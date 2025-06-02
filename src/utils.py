import asyncio
import logging
import traceback
import json
import database as db

from aiogram.types import BufferedInputFile
from aiogram import Bot
from playerok import Playerok


logger = logging.getLogger(__name__)


async def reupload_products(
    playerok: Playerok, keywords: list, bot: Bot, admin_ids: list,
):
    """
    Asynchronously reuploads products by retrieving cards from the Playerok service, filtering them based on keywords from the database,
    and updating the corresponding products. Skips cards listed in the fix_cards.json file. Sends update notifications via the provided message object.
    Retries the process up to 10 times in case of errors, with a 180-second delay between attempts.
    Args:
        playerok (Playerok): An instance of the Playerok class used to interact with the product service.
        session (AsyncSession): The asynchronous database session for ORM operations.
        message (Message): The message object used to send notifications and updates.
    Raises:
        Exception: Logs any exceptions encountered during the process. After 10 consecutive errors, notifies the user to check server logs.
    Side Effects:
        - Reads from 'src/storage/fix_cards.json'.
        - Sends photo messages with update results.
        - Logs process details and errors.
        - Initializes and closes a browser instance as needed.
    """
    fix_cards = None
    with open("src/storage/fix_cards.json", "r") as file:
        fix_cards = file.read().strip()

    if fix_cards:
        fix_cards = json.loads(fix_cards)

    while True:
        try:
            logger.info("Initializing browser for card retrieval...")
            await playerok.initialize_browser()

            cards = await playerok.get_cards()
            logger.info(f"Retrieved {len(cards) if cards else 0} cards.")

            if not cards:
                logger.warning("No cards retrieved from playerok.")
                return

            logger.info(f"Loaded {len(keywords) if keywords else 0} keywords from DB.")

            if keywords:
                filtered_cards = []
                for card in cards:
                    card_lower = card[0].lower()
                    if any(
                        keyword.lower() in card_lower for keyword in keywords
                    ):
                        filtered_cards.append(card[1])
                logger.info(f"Filtered cards count: {len(filtered_cards)}")
                cards = filtered_cards

            for card in cards:
                if fix_cards and card in fix_cards:
                    logger.info(f"Card {card} is in fix_cards, skipping update.")
                    cards.remove(card)

            if cards:
                logger.info("Processing cards for update...")
                await playerok.initialize_browser()
                for card in cards:
                    logger.info(f"Updating product for card: {card}")
                    result = await playerok.update_product(card)
                    if result:
                        logger.info(f"Product updated successfully: {result[1]}")
                        photo = BufferedInputFile(result[0], filename="result.png")

                        for admin_id in admin_ids:
                            try:
                                await bot.send_photo(
                                    chat_id=admin_id,
                                    photo=photo,
                                    caption=f'✅ Товар оновлений 👉 <a href="{result[1]}">link</a>',
                                )
                            except Exception as e:
                                logger.error(f"Failed to send photo to admin {admin_id}: {e}")
                    else:
                        logger.warning(f"Failed to update product for card: {card}")
                
                await playerok.browser.close()
            else:
                logger.info("No cards found matching the keywords.")

            if playerok.browser:
                logger.info("Closing browser...")
                await playerok.browser.close()
            logger.info("Reupload process completed successfully.")
        except Exception as e:
            logger.error(f"Error during reuploading products: {e}")
            logger.error(traceback.format_exc())
            error_count += 1

            if playerok.browser:
                logger.info("Closing browser...")
                await playerok.browser.close()
            logger.info("Reupload process completed.")

        await asyncio.sleep(180)  # Wait before retrying

    await message.answer(
        "❗️ Накопичилось 10 помилок при оновленні товарів. Провірьте логи на сервері."
    )
