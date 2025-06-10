import asyncio
from playerok import Playerok
from utils import autolift_products
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)
playerok = Playerok()
keywords = [
    {"keyword": "test1", "position": 250},
    {"keyword": "bobr", "position": 20},
    {"keyword": "обычный", "position": 20},
    {"keyword": "points", "position": 300},
]


async def main():
    test = playerok.get_product("5b57d577f1b2-ezhednevnyy-usilitel-b-vypolnyayu-bystro")
    
    # print(test["sequence"])
    await autolift_products(playerok, keywords)


if __name__ == "__main__":
    asyncio.run(main())
