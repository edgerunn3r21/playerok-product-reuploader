import asyncio
from playerok import Playerok

async def main():
    playerok = Playerok()
    await playerok.initialize_browser(headless=False)
    await playerok.test()

asyncio.run(main())