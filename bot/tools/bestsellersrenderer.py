import asyncio
from datetime import datetime, timezone
import hashlib
import logging
import discord
from playwright.async_api import async_playwright
import requests

from bot import constants

def get_track_number_config_url(total_tracks: int):
    host = "festivaltracker.org"
    base_url = f"https://{host}/5604c25f39614cbb_do_not_index-bestsellers-img-generator"
    params: str = ""

    if total_tracks == 1:
        params = "?gridcols=1&paddinghorizontal=300&paddingvertical=100&textsize=50&infopadding=30"
    elif total_tracks == 2:
        params = "?gridcols=2&textsize=40&infopadding=30&paddingvertical=50"
    elif total_tracks == 3:
        params = "?gridcols=2&textsize=40&infopadding=30&paddingvertical=70&height=1300"
    elif total_tracks == 4:
        params = "?gridcols=2&textsize=40&infopadding=30&height=1300&paddingvertical=70"
    elif total_tracks == 5 or total_tracks == 6:
        params = "?gridcols=3&textsize=30&infopadding=20&height=1080&paddingvertical=70"
    elif total_tracks == 7 or total_tracks == 8 or total_tracks == 9:
        params = "?gridcols=3&textsize=30&infopadding=20&height=1300&paddingvertical=40"

    return base_url + params

async def capture_renderer_screenshot(auto: bool = True, cols: int = 2, width: int = 1920, height: int = 1080, paddingverticalpx: int = 20) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page()
            
        total_tracks_number = 0
        total_tracks_received = asyncio.Event()
        async def total_tracks_received_callback(msg, total_tracks):
            print(f"Signal: {msg} {total_tracks} {type(total_tracks)}")
            nonlocal total_tracks_number
            total_tracks_number = total_tracks
            total_tracks_received.set()

        initial_cbtype = "numbers"
        if not auto:
            initial_cbtype = "image"

        await page.expose_function("snapshot_ready", total_tracks_received_callback)
        url = f"https://festivaltracker.org/5604c25f39614cbb_do_not_index-bestsellers-img-generator?gridcols={cols}&width={width}&height={height}&paddingvertical={paddingverticalpx}&stopalerts=1&callbacktype={initial_cbtype}"
        await page.goto(url)

        try:
            # now we wait
            await asyncio.wait_for(total_tracks_received.wait(), timeout=15.0)
            total_tracks_received.clear()

            if auto:
                url = get_track_number_config_url(total_tracks_number)
                await page.goto(url + "&callbacktype=image")

                # wait again
                await asyncio.wait_for(total_tracks_received.wait(), timeout=15.0)
            
            output_path = constants.CACHE_FOLDER + "bestsellers.png"
            await page.locator("#container").screenshot(path=output_path)
            open(constants.CACHE_FOLDER + "BestsellersTimestamp.dat", "w").write(str(int(datetime.now().timestamp())))

            return output_path
            
        except asyncio.TimeoutError:
            raise Exception("Timed out.")
        finally:
            # always pull out kids
            await browser.close()

async def handle_cacher():
    # this function is ran every minute
    # it should check the hash of the bestsellers response and if it has changed, capture a new screenshot
    # bestsellers hash is also saved locally

    # this code should only run at hour 0, 1 and 2 utc

    current_utc_hour = datetime.now(timezone.utc).hour
    if current_utc_hour not in [0, 1, 2]:
        return
    
    url = "https://cdn2.unrealengine.com/fn_bsdata/ebb74910-dd35-44b8-b826-d58dc16c6456.json"
    req = requests.get(url)
    
    response_hash = hashlib.sha256(req.content).hexdigest()
    try:
        saved_hash = open(constants.CACHE_FOLDER + "BestsellersHash.dat", "r").read()
    except Exception as e:
        logging.warning(f"Error reading hash cache: {e}")
        saved_hash = ""

    if response_hash != saved_hash:
        logging.info("Bestsellers data has changed, capturing new screenshot.")
        try:
            await capture_renderer_screenshot(auto=True)
            open(constants.CACHE_FOLDER + "BestsellersHash.dat", "w").write(response_hash)
        except Exception as e:
            logging.error(f"Error capturing screenshot: {e}")

async def handle_interaction(interaction: discord.Interaction):
    await interaction.response.defer()

    # to avoid taking a screenshot every time
    # we will check the saved timestamp and make sure it is from the same utc day
    try:
        timestamp = int(open(constants.CACHE_FOLDER + "BestsellersTimestamp.dat", "r").read())
        last_capture_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        current_date = datetime.now(timezone.utc).date()

        if last_capture_date == current_date:
            # same day, use cached image
            output_path = constants.CACHE_FOLDER + "bestsellers.png"
        else:
            # different day, capture new image
            output_path = await capture_renderer_screenshot(auto=True)
    except Exception as e:
        logging.warning(f"Error checking cache: {e}")
        output_path = await capture_renderer_screenshot(auto=True)

    # the timestamp on the dat file
    capture_time = datetime.fromtimestamp(int(open(constants.CACHE_FOLDER + "BestsellersTimestamp.dat", "r").read()), tz=timezone.utc)

    view = discord.ui.LayoutView()
    container = discord.ui.Container(accent_colour=constants.ACCENT_COLOUR)
    container.add_item(
        discord.ui.Section(
            discord.ui.TextDisplay("# Best Sellers"),
            discord.ui.TextDisplay(f"*Last updated: {discord.utils.format_dt(capture_time, style='F')}*"),
            accessory=discord.ui.Thumbnail(f'attachment://{constants.KEYART_FNAME}')
        )
    )

    container.add_item(
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                "attachment://bestsellers.png"
            )
        )
    )

    
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay("-# Festival Tracker")
    )

    view.add_item(container)
    await interaction.edit_original_response(view=view, attachments=[discord.File(output_path, "bestsellers.png"), discord.File(constants.KEYART_PATH, constants.KEYART_FNAME)])