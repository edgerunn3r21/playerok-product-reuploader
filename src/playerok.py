import asyncio
import traceback
import logging
import os

from patchright.async_api import async_playwright
from config import auth_url, profile_url, site_url

logger = logging.getLogger(__name__)


class Playerok:
    """
    Class for working with Playwright and automating actions on the Playerok website.

    Main features:
    - Browser and context initialization
    - User authentication (email + code)
    - Authentication check
    - Retrieving a list of cards
    - Product update (card update)
    - Closing the browser
    """

    def __init__(self):
        """
        Initializes browser parameters, user-agent, storage path, and internal variables.
        """
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        self.launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-popup-blocking",
            "--disable-default-apps",
        ]
        self.storage_state_path = "src/storage/storage.json"
        self.page = None
        self.browser = None
        self.context = None

    async def initialize_browser(self, headless=True):
        """
        Starts Playwright, launches the browser, and creates a new context.
        :param headless: Whether to run the browser in headless mode
        :return: None or Exception
        """
        try:
            os.makedirs(os.path.dirname(self.storage_state_path), exist_ok=True)

            logger.info("Starting Playwright and launching browser...")
            p = await async_playwright().start()
            self.browser = await p.chromium.launch(
                headless=headless,
                args=self.launch_args,
                channel="chrome",
            )
            logger.info("Browser launched successfully.")

            storage_state_exists = os.path.exists(self.storage_state_path)

            logger.info(f"Storage state path exists: {storage_state_exists}")

            self.context = await self.browser.new_context(
                locale="ru-RU",
                user_agent=self.user_agent,
                viewport={"width": 1920, "height": 1080},
                storage_state=(
                    self.storage_state_path if storage_state_exists else None
                ),
            )
            logger.info("Browser context created successfully.")
        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            logger.error(traceback.format_exc())

            if self.browser:
                await self.browser.close()

            return None

    async def close(self):
        """
        Closes the browser if it is open.
        """
        if self.browser:
            await self.browser.close()

    async def auth_first(self, email):
        """
        First step of authentication: enters email, clicks the button, checks for errors.
        :param email: User's email
        :return: 'email' if email not found, 'repeat' if request is too frequent, True if successful
        """
        try:
            self.page = await self.context.new_page()
            await self.page.goto(auth_url)

            await asyncio.sleep(2)
            await self.page.locator('input[name="email"]').fill(email)
            await self.page.locator("button[type='submit']").click()

            await asyncio.sleep(3)

            if await self.page.locator(
                "p", has_text="Такой почты не существует"
            ).is_visible():
                logger.error("Email not found during authentication.")
                return "email"
            elif await self.page.locator(
                "p",
                has_text="Авторизационный код нельзя запрашивать чаще одного раза в 60 секунд",
            ).is_visible():
                logger.error("Authorization code request too frequent.")
                return "repeat"
            else:
                logger.info("First authentication step completed successfully.")
                return True
        except Exception as e:
            logger.error(f"Error during first authentication step: {e}")
            logger.error(traceback.format_exc())

            if self.browser:
                await self.browser.close()

            return None

    async def auth_second(self, code):
        """
        Second step of authentication: enters the code, saves storage state.
        :param code: Code from SMS
        :return: None
        """
        try:
            code_inputs = await self.page.locator('input[type="number"]').all()

            for code_input in code_inputs:
                await code_input.fill(code)

            await asyncio.sleep(3)
            await self.context.storage_state(path=self.storage_state_path)
        except Exception as e:
            logger.error(f"Error during second authentication step: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            if self.browser:
                await self.browser.close()

    async def check_auth(self):
        """
        Checks if authentication was successful (if the profile page opens).
        :return: True if authentication is successful, False otherwise
        """
        try:
            logger.info("Starting authentication check...")
            self.page = await self.context.new_page()
            await self.page.goto(profile_url)
            logger.info(f"Navigated to {profile_url}")

            await asyncio.sleep(2)

            if auth_url != self.page.url:
                logger.info(
                    "Authentication successful, saving storage state and closing browser."
                )
                await self.context.storage_state(path=self.storage_state_path)
                return True
            else:
                logger.warning(
                    "Authentication failed: profile_url not in current page URL."
                )
                return False
        except Exception as e:
            logger.error(f"Error during authentication check: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            if self.browser:
                await self.browser.close()
                logger.info("Browser closed after authentication check.")

    async def get_cards(self) -> list:
        """
        Retrieves a list of cards (up to 10) from the user's profile.
        :return: List of cards (title, url) or None
        """
        try:
            logger.info("Opening new page for card retrieval.")
            self.page = await self.context.new_page()
            await self.page.goto(profile_url)
            logger.info(f"Navigated to {profile_url}")

            active_btn_count = 0

            while active_btn_count <= 5:
                logger.debug(
                    "Attempting to click 'Завершённые' button (attempt %d).",
                    active_btn_count + 1,
                )
                done_btn = self.page.locator("a:has-text('Завершённые')")
                await done_btn.click()
                done_btn_attr = await done_btn.get_attribute("class")

                if "active" in done_btn_attr:
                    logger.info("'Завершённые' button is active.")
                    break
                else:
                    active_btn_count += 1

                    if active_btn_count == 5:
                        logger.warning(
                            "Button is not active after 5 attempts, exiting test."
                        )
                        return None

                    await asyncio.sleep(1)

            logger.info("Waiting for cards container selector.")
            await self.page.wait_for_selector("div.MuiBox-root.mui-style-vbsxzt")

            cards = (await self.page.locator("div.MuiBox-root.mui-style-4g6ai3").all())[
                :10
            ]
            logger.info("Found %d cards.", len(cards))
            card_list = []

            if cards:
                for idx, card in enumerate(cards):
                    links = await card.locator("a").all()
                    if len(links) > 1:
                        title = await links[1].inner_text()
                        url = await links[1].get_attribute("href")
                        logger.debug("Card %d title: %s", idx + 1, title)
                        card_list.append([title, url])

            logger.info("Returning list of card titles.")
            return card_list
        except Exception as e:
            logger.error(f"Error during test: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            if self.browser:
                await self.browser.close()

    async def update_product(self, product_url):
        """
        Updates a product (card) by URL, returns a screenshot and url.
        :param product_url: Relative product url
        :return: [screenshot_bytes, url] or None
        """
        try:
            logger.info("Opening new page for product update.")
            self.page = await self.context.new_page()

            logger.info(f"Navigating to {product_url}")
            await self.page.goto(site_url + product_url)

            logger.info("Waiting for and clicking the first button.")
            first_btn = await self.page.wait_for_selector(
                "button.MuiBox-root.mui-style-3mvi7t"
            )
            await first_btn.click()

            logger.info("Waiting for and clicking the second button.")
            second_btn = await self.page.wait_for_selector(
                "button.MuiBox-root.mui-style-1ljgpjy"
            )
            await second_btn.click()

            logger.info("Waiting for and clicking the third button.")
            third_btn = await self.page.wait_for_selector(
                "button.MuiBox-root.mui-style-p0ojd3"
            )
            await third_btn.click()

            logger.info("Waiting for the result element to appear.")
            element = await self.page.wait_for_selector(
                "div.MuiBox-root.mui-style-10vt5r9"
            )
            if element:
                await asyncio.sleep(3)
                logger.info("Element found, taking screenshot.")
                return [await element.screenshot(), site_url + product_url]
            else:
                logger.warning("Element not found, returning None.")
                return None

        except Exception as e:
            logger.error(f"Error during product update: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            if self.browser:
                await self.browser.close()

    async def test(self):
        """
        Test function for manual authentication and navigation check.
        """
        try:
            self.page = await self.context.new_page()
            await self.page.goto(profile_url)
            input("Press Enter to continue...")
        except Exception as e:
            logger.error(f"Error during authentication check: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            if self.browser:
                await self.browser.close()
