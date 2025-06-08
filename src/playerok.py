import os
import random
import cloudscraper
import logging

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.82 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6585.40 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.55 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6602.22 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6610.28 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6627.14 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.6671.6 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6700.2 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6722.1 Safari/537.36",
]


class Playerok:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {
            "Content-Type": "application/json",
            "Origin": "https://playerok.com",
            "Accept": "application/json",
            "Accept-Language": "ru-RU",
            "User-Agent": self.get_random_user_agent(),
            "Sec-Ch-Ua": '"Google Chrome";v="137", "Chromium";v="137", "Not(A:Brand";v="24"',
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Ch-Ua-Mobile": "?0",
        }
        self.url = "https://playerok.com/graphql"
        self.storage_cookies_path = "src/storage/cookies.txt"

    def get_random_user_agent(self, previous=None):
        if previous is None:
            return random.choice(USER_AGENTS)
        candidates = [ua for ua in USER_AGENTS if ua != previous]
        if not candidates:
            return previous
        return random.choice(candidates)

    def get_email_auth_code(self, email):
        """
        Simulate sending an email to the user with a code.
        In a real application, this would send an email.
        """
        payload = {
            "operationName": "getEmailAuthCode",
            "variables": {"email": email},
            "query": "mutation getEmailAuthCode($email: String!) {\n  getEmailAuthCode(input: {email: $email})\n}",
        }

        logger.info(f"Sending email auth code request for email: {email}")
        response = self.scraper.post(self.url, json=payload, headers=self.headers)
        logger.info(f"Response from getEmailAuthCode: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Response JSON: {data}")
            if "data" in data and "getEmailAuthCode" in data["data"]:
                logger.info("Email auth code sent successfully.")
                return data["data"]["getEmailAuthCode"]
            else:
                logger.warning("Email auth code not found in response.")
                return None
        else:
            logger.error(
                f"Failed to send email auth code. Status code: {response.status_code}"
            )
            return None

    def verify_email_code(self, email, code):
        payload = {
            "operationName": "checkEmailAuthCode",
            "variables": {"input": {"code": code, "email": email}},
            "query": "mutation checkEmailAuthCode($input: CheckEmailAuthCodeInput!) { checkEmailAuthCode(input: $input) { ...Viewer __typename } } fragment Viewer on User { id username email role hasFrozenBalance supportChatId systemChatId unreadChatsCounter isBlocked isBlockedFor createdAt lastItemCreatedAt hasConfirmedPhoneNumber canPublishItems profile { id avatarURL testimonialCounter __typename } __typename }",
        }

        logger.info(f"Verifying email code for email: {email}")
        response = self.scraper.post(self.url, json=payload, headers=self.headers)
        logger.info(f"Response from checkEmailAuthCode: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "checkEmailAuthCode" in data["data"]:
                cookies = response.cookies.get_dict()
                logger.info(f"Saving cookies to {self.storage_cookies_path}")
                with open(self.storage_cookies_path, "w") as f:
                    for key, value in cookies.items():
                        f.write(f"{key}={value}\n")

                logger.info("Saving user data to src/storage/user_data.json")
                with open("src/storage/user_data.json", "w") as f:
                    f.write(
                        str(
                            {
                                "id": data["data"]["checkEmailAuthCode"]["id"],
                                "username": data["data"]["checkEmailAuthCode"][
                                    "username"
                                ],
                            }
                        )
                    )
                logger.info("Email code verified successfully.")
                return data["data"]["checkEmailAuthCode"]
            else:
                logger.warning("checkEmailAuthCode not found in response.")
                return None
        else:
            logger.error(
                f"Failed to verify email code. Status code: {response.status_code}"
            )
            return None

    def get_products(self):
        count = 0
        with open("src/storage/count.txt", "a+") as f:
            f.seek(0)
            content = f.read().strip()
            if content:
                count = int(content)
            else:
                logger.warning("Count file is empty, initializing count to 0.")

        if count >= 30:
            self.scraper = cloudscraper.create_scraper()
            self.headers["User-Agent"] = self.get_random_user_agent(
                self.headers.get("User-Agent")
            )
            with open("src/storage/count.txt", "w") as f:
                f.write("0")
                
            logger.info(f"User-Agent changed to: {self.headers['User-Agent']}")

        logger.info("Attempting to load cookies and user data for get_products.")
        if not self.headers.get("Cookie") and os.path.exists(self.storage_cookies_path):
            with open(self.storage_cookies_path, "r") as f:
                cookies = [line.strip() for line in f if line.strip()]
                self.headers["Cookie"] = "; ".join(cookies)

        if not os.path.exists("src/storage/user_data.json"):
            logger.error("User data file src/storage/user_data.json does not exist.")
            return None

        user_id = None
        with open("src/storage/user_data.json", "r") as f:
            user_data = f.read()
            if not user_data:
                logger.error("User data file is empty.")
                return None
            else:
                user_data = eval(user_data)  # Convert string to dictionary
                user_id = user_data.get("id", None)

        if not user_id:
            logger.error("User ID not found in user data.")
            return None

        logger.info(f"Fetching products for user_id: {user_id}")
        payload = {
            "operationName": "items",
            "variables": {
                "pagination": {"first": 16},
                "filter": {
                    "userId": user_id,
                    "status": ["DECLINED", "BLOCKED", "EXPIRED", "SOLD", "DRAFT"],
                },
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "d79d6e2921fea03c5f1515a8925fbb816eacaa7bcafe03eb47a40425ef49601e",
                }
            },
        }

        headers = self.headers.copy()
        headers["Referer"] = (
            "https://playerok.com/profile/StanicaShop/products/completed"
        )

        with open("src/storage/count.txt", "w") as f:
            count += 1
            f.write(str(count))
            logger.info(f"Incremented count to {count}.")

        response = self.scraper.post(self.url, json=payload, headers=self.headers)
        logger.info(response.request.headers)
        logger.info(f"Response from items query: {response.status_code}")
        if response.status_code == 200:
            logger.info("Successfully fetched products.")
            return response.json()["data"].get("items").get("edges")
        else:
            logger.error(
                f"Failed to fetch products. Status code: {response.status_code}"
            )
            logger.error(f"Response content: {response.text}")
            self.scraper = (
                cloudscraper.create_scraper()
            )  # Recreate scraper to reset headers
            self.headers["User-Agent"] = self.get_random_user_agent(
                self.headers.get("User-Agent")
            )
            logger.info(
                f"Retrying with a new User-Agent - {self.headers['User-Agent']}"
            )
            return None

    def get_priority_status(self, item_id, price):
        payload = {
            "operationName": "itemPriorityStatuses",
            "variables": {
                "itemId": item_id,
                "price": price,
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "b922220c6f979537e1b99de6af8f5c13727daeff66727f679f07f986ce1c025a",
                }
            },
        }

        logger.info(
            f"Requesting priority status for item_id: {item_id} with price: {price}"
        )
        response = self.scraper.post(self.url, json=payload, headers=self.headers)
        logger.info(f"Response from itemPriorityStatuses: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "itemPriorityStatuses" in data["data"]:
                logger.info("Successfully retrieved priority status.")
                return data["data"]["itemPriorityStatuses"][0]
            else:
                logger.warning("itemPriorityStatuses not found in response.")
                return None
        else:
            logger.error(
                f"Failed to get priority status. Status code: {response.status_code}"
            )
            return None

    def make_transaction(self, item_id, priority_status_id):
        logger.info(
            f"Initiating transaction for item_id: {item_id} with priority_status_id: {priority_status_id}"
        )
        payload = {
            "operationName": "publishItem",
            "variables": {
                "input": {
                    "priorityStatuses": [priority_status_id],
                    "transactionProviderId": "LOCAL",
                    "transactionProviderData": {"paymentMethodId": None},
                    "itemId": item_id,
                }
            },
            "query": "mutation publishItem($input: PublishItemInput!) { publishItem(input: $input) { ...RegularItem __typename } } fragment RegularItem on Item { ...RegularMyItem ...RegularForeignItem __typename } fragment RegularMyItem on MyItem { ...ItemFields prevPrice priority sequence priorityPrice statusExpirationDate comment viewsCounter statusDescription editable statusPayment { ...StatusPaymentTransaction __typename } moderator { id username __typename } approvalDate deletedAt createdAt updatedAt mayBePublished prevFeeMultiplier sellerNotifiedAboutFeeChange __typename } fragment ItemFields on Item { id slug name description rawPrice price attributes status priorityPosition sellerType feeMultiplier user { ...ItemUser __typename } buyer { ...ItemUser __typename } attachments { ...PartialFile __typename } category { ...RegularGameCategory __typename } game { ...RegularGameProfile __typename } comment dataFields { ...GameCategoryDataFieldWithValue __typename } obtainingType { ...GameCategoryObtainingType __typename } __typename } fragment ItemUser on UserFragment { ...UserEdgeNode __typename } fragment UserEdgeNode on UserFragment { ...RegularUserFragment __typename } fragment RegularUserFragment on UserFragment { id username role avatarURL isOnline isBlocked rating testimonialCounter createdAt supportChatId systemChatId __typename } fragment PartialFile on File { id url __typename } fragment RegularGameCategory on GameCategory { id slug name categoryId gameId obtaining options { ...RegularGameCategoryOption __typename } props { ...GameCategoryProps __typename } noCommentFromBuyer instructionForBuyer instructionForSeller useCustomObtaining autoConfirmPeriod autoModerationMode agreements { ...RegularGameCategoryAgreement __typename } feeMultiplier __typename } fragment RegularGameCategoryOption on GameCategoryOption { id group label type field value valueRangeLimit { min max __typename } __typename } fragment GameCategoryProps on GameCategoryPropsObjectType { minTestimonials minTestimonialsForSeller __typename } fragment RegularGameCategoryAgreement on GameCategoryAgreement { description gameCategoryId gameCategoryObtainingTypeId iconType id sequence __typename } fragment RegularGameProfile on GameProfile { id name type slug logo { ...PartialFile __typename } __typename } fragment GameCategoryDataFieldWithValue on GameCategoryDataFieldWithValue { id label type inputType copyable hidden required value __typename } fragment GameCategoryObtainingType on GameCategoryObtainingType { id name description gameCategoryId noCommentFromBuyer instructionForBuyer instructionForSeller sequence feeMultiplier agreements { ...MinimalGameCategoryAgreement __typename } props { minTestimonialsForSeller __typename } __typename } fragment MinimalGameCategoryAgreement on GameCategoryAgreement { description iconType id sequence __typename } fragment StatusPaymentTransaction on Transaction { id operation direction providerId status statusDescription statusExpirationDate value props { paymentURL __typename } __typename } fragment RegularForeignItem on ForeignItem { ...ItemFields __typename }",
        }
        response = self.scraper.post(self.url, json=payload, headers=self.headers)
        logger.info(f"Response from publishItem: {response.status_code}")
        if response.status_code == 200:
            logger.info("Transaction completed successfully.")
            return response.json()
        else:
            logger.error(
                f"Failed to complete transaction. Status code: {response.status_code}"
            )
            return None
