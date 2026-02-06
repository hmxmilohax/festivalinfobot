import asyncio
from playwright.async_api import async_playwright

from bot import constants

async def capture_renderer_screenshot(cols: int = 2, width: int = 1920, height: int = 1080, paddingverticalpx: int = 20) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page()
        
        render_complete = asyncio.Event()

        async def on_ready(msg):
            print(f"JS Signal received: {msg}")
            render_complete.set()

        # inject callback into page
        await page.expose_function("snapshot_ready", on_ready)

        url = f"https://festivaltracker.org/5604c25f39614cbb_do_not_index-bestsellers-img-generator?gridcols={cols}&width={width}&height={height}&paddingvertical={paddingverticalpx}&stopalerts=1"
        await page.goto(url)

        try:
            # now we wait
            await asyncio.wait_for(render_complete.wait(), timeout=15.0)
            
            # catch in 4k
            output_path = constants.TEMP_FOLDER + "bestsellers_renderer.png"
            await page.locator("#container").screenshot(path=output_path)
            return output_path
            
        except asyncio.TimeoutError:
            raise Exception("Timed out.")
        finally:
            # always pull out kids
            await browser.close()