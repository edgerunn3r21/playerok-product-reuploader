import logging
import random
import time
import traceback
import asyncio

from aiogram import Bot
from playerok import Playerok
from datetime import datetime, timezone, timedelta
from keyboards import get_url_btns
from config import site_url

logger = logging.getLogger(__name__)


async def reupload_products(
    playerok: Playerok,
    keywords: list,
    bot: Bot,
    admin_ids: list,
):
    try:
        await random_sleep(20, 60)
        products = playerok.get_products()

        if not products:
            logger.warning("No products retrieved from playerok.")
            return

        logger.info("Starting reupload process for %d products.", len(products))
        for product in products:
            created_at = datetime.fromisoformat(
                product["node"]["createdAt"].replace("Z", "+00:00")
            )
            product_name = product["node"]["name"]
            product_id = product["node"]["id"]

            if created_at > datetime.now(timezone.utc) - timedelta(hours=48):
                logging.info(created_at)
                if any(keyword.lower() in product_name.lower() for keyword in keywords):
                    priority_status = playerok.get_priority_status(
                        product_id,
                        product["node"]["rawPrice"],
                    )
                    if not priority_status:
                        logger.info(
                            "Product '%s' (ID: %s) is not in priority status. Skipping.",
                            product_name,
                            product_id,
                        )
                        continue

                    transaction = playerok.make_transaction(
                        product_id,
                        priority_status["id"],
                    )

                    if transaction:
                        logger.info(
                            "Product '%s' (ID: %s) reuploaded successfully.",
                            product_name,
                            product_id,
                        )
                        for admin_id in admin_ids:
                            try:
                                await bot.send_photo(
                                    chat_id=admin_id,
                                    photo=product["node"]["attachment"]["url"],
                                    reply_markup=get_url_btns(
                                        btns={
                                            "ТОВАР ВИСТАВЛЕНИЙ": f"{site_url}/products/{product['node']['slug']}"
                                        },
                                        sizes=(1,),
                                    ),
                                )
                                logger.info(
                                    "Notification sent to admin %s for product '%s' (ID: %s).",
                                    admin_id,
                                    product_name,
                                    product_id,
                                )
                            except Exception as e:
                                logger.warning(
                                    "Failed to notify admin %s for product '%s' (ID: %s): %s",
                                    admin_id,
                                    product_name,
                                    product_id,
                                    e,
                                )
                    else:
                        logger.warning(
                            "Failed to reupload product '%s' (ID: %s).",
                            product_name,
                            product_id,
                        )
                else:
                    logger.info(
                        "Product '%s' (ID: %s) does not match keywords. Skipping.",
                        product_name,
                        product_id,
                    )
                await random_sleep()
        logger.info("Reupload process completed.")

    except Exception as e:
        logger.error("Exception during reupload_products: %s", e, exc_info=True)


async def autolift_products(
    playerok: Playerok,
    keywords: list,
    bot: Bot,
    admin_ids: list,
):
    try:
        await random_sleep(20, 60)
        products = playerok.get_products(status_type="active")

        if not products:
            logger.warning("No products retrieved from playerok.")
            return

        logger.info("Starting autolift process for %d products.", len(products))
        for product in products:
            created_at = datetime.fromisoformat(
                product["node"]["createdAt"].replace("Z", "+00:00")
            )
            product_name = product["node"]["name"]
            product_id = product["node"]["id"]
            product_slug = product["node"]["slug"]

            if created_at > datetime.now(timezone.utc) - timedelta(hours=72):
                logging.info(created_at)

                for keyword in keywords:
                    if keyword["keyword"].lower() in product_name.lower():
                        product_data = playerok.get_product(product_slug)

                        if not product_data:
                            logger.warning(
                                "Product '%s' (ID: %s) not found in playerok. Skipping.",
                                product_name,
                                product_id,
                            )
                            continue

                        product_sequence = product_data.get("sequence", None)

                        if not product_sequence:
                            logger.warning(
                                f"Product '{product_name}' (ID: {product_id}) has no sequence data. Skipping."
                            )
                            continue

                        logger.info(f"Keyword position {keyword['position']} - current sequence {product_sequence}")

                        if product_sequence > keyword["position"]:
                            priority_status = playerok.get_priority_status(
                                product_id,
                                product["node"]["rawPrice"],
                            )

                            if not priority_status:
                                logger.info(
                                    "Product '%s' (ID: %s) is not in priority status. Skipping.",
                                    product_name,
                                    product_id,
                                )
                                continue

                            transaction = playerok.make_autolift(
                                product_id,
                                priority_status["id"],
                            )

                            if transaction:
                                logger.info(
                                    "Product '%s' (ID: %s) autolifted successfully.",
                                    product_name,
                                    product_id,
                                )
                                for admin_id in admin_ids:
                                    try:
                                        await bot.send_photo(
                                            chat_id=admin_id,
                                            photo=product["node"]["attachment"]["url"],
                                            reply_markup=get_url_btns(
                                                btns={
                                                    "ТОВАР ПІДНЯТИЙ В ТОП": f"{site_url}/products/{product['node']['slug']}"
                                                },
                                                sizes=(1,),
                                            ),
                                        )
                                        logger.info(
                                            "Notification sent to admin %s for product '%s' (ID: %s).",
                                            admin_id,
                                            product_name,
                                            product_id,
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            "Failed to notify admin %s for product '%s' (ID: %s): %s",
                                            admin_id,
                                            product_name,
                                            product_id,
                                            e,
                                        )
                            else:
                                logger.warning(
                                    "Failed to autolift product '%s' (ID: %s).",
                                    product_name,
                                )
    except Exception as e:
        logger.error("Exception during autolift_products: %s", e, exc_info=True)


async def random_sleep(min_seconds=5, max_seconds=10):
    """
    Sleep for a random duration between min_seconds and max_seconds.
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    logger.info(f"Sleeping for {sleep_time:.2f} seconds.")
    await asyncio.sleep(sleep_time)
