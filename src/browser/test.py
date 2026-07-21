import asyncio  # noqa: D100
import sys
import time
from pathlib import Path

import turbohtml
from loguru import logger

sys.path.append(str(Path.cwd()))
from src.browser.site import source as page_source

# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     handlers=[logging.StreamHandler(sys.stderr)],
# )


async def main() -> None:  # noqa: D103
    url = "https://www.wikipedia.com/"  ## Redirect test
    url = "https://bot.sannysoft.com/"  ## AntiBot validator
    url = "https://nopecha.com/demo/cloudflare"  ## Cloudflare Interstitial
    url = "https://nopecha.com/demo/turnstile"  ## Cloudflare Turnstile
    url = "https://pixelscan.net/fingerprint-check"  ## Fingerprint Checker
    url = "https://abrahamjuliot.github.io/creepjs/"  ## Fingerprint Checker
    url = "https://demo.fingerprint.com/playground"  ## Fingerprint Checker
    url = "https://peet.ws/turnstile-test/managed.html"  ## Cloudflare Interstitial
    url = "https://www.apkmirror.com/apk/instagram/instagram-instagram/instagram-401-0-0-48-79-release/"  ## ApkMirror Cloudflare  # noqa: E501

    try:
        r = await page_source(url, 60)
        doc = turbohtml.parse(r.text)
        element = doc.select_one("title")
        if element:
            print(element.text)  # noqa: T201
    except BaseException as e:
        logger.error(e)
        raise


async def _looper() -> None:
    for _ in range(1):
        await main()


if __name__ == "__main__":
    start = time.perf_counter()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_looper())
    stop = time.perf_counter()
    print("Elapsed time during the whole program in seconds:", stop - start)  # noqa: T201
