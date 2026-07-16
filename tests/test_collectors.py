import asyncio
import logging
from dr3.collectors.api_collectors.telegram_collector import TelegramCollector
from dr3.collectors.api_collectors.instagram_collector import InstagramCollector
from dr3.collectors.api_collectors.facebook_collector import FacebookCollector
from dr3.collectors.api_collectors.twitter_collector import TwitterCollector

logging.basicConfig(level=logging.DEBUG)

async def test_all():
    username = "zuck" # A well known user across platforms
    print("Testing Telegram...")
    tc = TelegramCollector()
    res = await tc.collect("durov")
    print("Telegram:", res.status, getattr(res, 'display_name', '').encode('utf-8'))
    await tc.close()

    print("\nTesting Instagram...")
    ic = InstagramCollector()
    res = await ic.collect("zuck")
    print("Instagram:", res.status, getattr(res, 'display_name', '').encode('utf-8'))
    await ic.close()

    print("\nTesting Facebook...")
    fc = FacebookCollector()
    res = await fc.collect("zuck")
    print("Facebook:", res.status, getattr(res, 'display_name', '').encode('utf-8'))
    await fc.close()

    print("\nTesting Twitter...")
    twc = TwitterCollector()
    res = await twc.collect("elonmusk")
    print("Twitter:", res.status, getattr(res, 'display_name', '').encode('utf-8'))
    await twc.close()

if __name__ == "__main__":
    asyncio.run(test_all())
