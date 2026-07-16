import asyncio
import asyncio
from datetime import datetime, timezone
import hashlib
import logging
import discord
from playwright.async_api import async_playwright
import requests
import base64
import time
import os
import json

from bot import constants


class BestsellersRenderer:
    def __init__(self, bot: constants.BotExt):
        self.bot = bot
        self.last_best_sellers_hash = None
        self.last_notified_hash = None

    async def get_leaving_new_lists(self) -> tuple:
        # numbers:numbers:numbers...
        leaving_today_string = []

        # we r making the value containing the ids for new and leaving soon tracks
        logging.debug(f'[GET] {constants.FN_CATALOG}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        response = requests.get(constants.FN_CATALOG, headers=headers)
        if response.status_code == 401 or response.status_code == 403:
            self.bot.oauth_manager._create_token()
            raise Exception('Please try again.')
        
        data = response.json()

        storefront = discord.utils.find(lambda storefront: storefront['name'] == 'BRWeeklyStorefront', data['storefronts'])
        shop_tracks = storefront['catalogEntries']

        for track in shop_tracks:
            if not track['meta']['templateId'].startswith('SparksSong:'):
                continue
            
            # offer_info contains the leaving date in ISO
            # check if it is the same day as today

            # set it to custom for testing
            track['meta']['outDate'] = "2026-03-14T23:59:59.999Z"

            leaving_date = datetime.fromisoformat(track['meta']['outDate'])
            if leaving_date.date() != datetime.now(tz=timezone.utc).date():
                continue

            sid_num = track['meta']['templateId'].split(":")[1].split("_")[-1]
            leaving_today_string.append(sid_num)

        # make new jam track string
        new_jam_track_string = []

        tracks = constants.get_jam_tracks(use_cache=True)
        for track in tracks:
            # check new until date
            track_data = track.get('track')
            new_until = track_data.get('nu')

            if new_until:
                new_until_date = datetime.fromisoformat(new_until)
                if new_until_date.date() > datetime.now(tz=timezone.utc).date():
                    sid_num = track_data['ti'].split(":")[1].split("_")[-1]
                    new_jam_track_string.append(sid_num)

        return leaving_today_string, new_jam_track_string

    async def capture_renderer_screenshot(self, auto: bool = True, cols: int = 4) -> str:
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
            
            leaving_today_string, new_jam_track_string = await self.get_leaving_new_lists()
            leaving_today_string = ":".join(leaving_today_string)
            new_jam_track_string = ":".join(new_jam_track_string)

            # encode as base64 url
            leaving_today_string = base64.urlsafe_b64encode(leaving_today_string.encode('utf-8')).decode('utf-8').rstrip('=')
            new_jam_track_string = base64.urlsafe_b64encode(new_jam_track_string.encode('utf-8')).decode('utf-8').rstrip('=')
            url = f"http://festivaltracker.org/5604c25f39614cbb_do_not_index-bestsellers-img-generator?gridcols={cols}"

            print(url)

            data_url = "https://cdn2.unrealengine.com/fn_bsdata/ebb74910-dd35-44b8-b826-d58dc16c6456.json"
            try:
                req = requests.get(data_url)
                req.raise_for_status()
            except Exception as e:
                logging.error(f"Error fetching bestsellers data: {e}")
                return

            bestsellers_data = req.json()
            bestsellers_country_keys = bestsellers_data.keys()

            bestsellers_countries = []

            # {
			# 			type: "solo_showcase_product",
			# 			image: "https://fortnite-api.com/images/cosmetics/br/backpack_indoorlace_mic/icon.png",
			# 			background_image:
			# 				"https://fortnite-api.com/images/cosmetics/series/creatorcollabseries.png",
			# 			bundle_image:
			# 				"https://fortnite-api.com/images/cosmetics/br/newdisplayassets/3f906da46e4624b5/renderimage_0.png",
			# 			bundle_name: "Laufey Bundle",
			# 			name: "Silver Mic",
			# 			subtitle: "Microphone",
			# 			icon: musicsvg,
			# 			countries: []
			# },

            music_icon = 'data:image/svg+xml,%3C%3Fxml%20version%3D%221.0%22%20encoding%3D%22utf-8%22%3F%3E%3C!DOCTYPE%20svg%20PUBLIC%20%22-%2F%2FW3C%2F%2FDTD%20SVG%201.1%2F%2FEN%22%20%22http%3A%2F%2Fwww.w3.org%2FGraphics%2FSVG%2F1.1%2FDTD%2Fsvg11.dtd%22%3E%3C!--%20License%3A%20MIT.%20Made%20by%20elusiveicons%3A%20https%3A%2F%2Felusiveicons.com%20--%3E%3Csvg%20version%3D%221.1%22%20id%3D%22svg2%22%20xmlns%3Adc%3D%22http%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%22%20xmlns%3Acc%3D%22http%3A%2F%2Fcreativecommons.org%2Fns%23%22%20xmlns%3Ardf%3D%22http%3A%2F%2Fwww.w3.org%2F1999%2F02%2F22-rdf-syntax-ns%23%22%20xmlns%3Asvg%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20xmlns%3Asodipodi%3D%22http%3A%2F%2Fsodipodi.sourceforge.net%2FDTD%2Fsodipodi-0.dtd%22%20xmlns%3Ainkscape%3D%22http%3A%2F%2Fwww.inkscape.org%2Fnamespaces%2Finkscape%22%20sodipodi%3Adocname%3D%22music.svg%22%20inkscape%3Aversion%3D%220.48.4%20r9939%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20xmlns%3Axlink%3D%22http%3A%2F%2Fwww.w3.org%2F1999%2Fxlink%22%20%20width%3D%22800px%22%20height%3D%22800px%22%20viewBox%3D%220%200%201200%201200%22%20enable-background%3D%22new%200%200%201200%201200%22%20xml%3Aspace%3D%22preserve%22%3E%3Cpath%20id%3D%22path14742%22%20fill%3D%22%23fff%22%20inkscape%3Aconnector-curvature%3D%220%22%20d%3D%22M364.798%2C80.329l-30.419%2C790.778c-40.935-21.007-92.292-30.096-146.179-22.449C72.007%2C865.114-11.66%2C952.766%2C1.33%2C1044.407c12.992%2C91.647%2C117.714%2C152.585%2C233.902%2C136.124c103.119-14.613%2C180.524-85.303%2C187.557-165.075l0.022%2C0.045c0.016-0.181%2C0.026-0.452%2C0.042-0.656c0.173-2.026%2C0.271-4.08%2C0.346-6.119c4.327-82.368%2C30.815-708.026%2C30.815-708.026l652.416-67.219l-29.467%2C563.479c-41.867-23.303-95.68-33.684-152.264-25.665c-116.192%2C16.473-199.854%2C104.105-186.863%2C195.759c12.986%2C91.639%2C117.709%2C152.587%2C233.901%2C136.107c105.313-14.906%2C183.777-88.319%2C187.895-170.171l0.05-0.05C1161.89%2C896.157%2C1198.7%2C46.799%2C1200%2C16.784L364.798%2C80.329z%22%2F%3E%3C%2Fsvg%3E'
            bundle_icon = 'data:image/svg+xml,%3C%3Fxml%20version%3D%221.0%22%20encoding%3D%22utf-8%22%3F%3E%3C!--%20License%3A%20MIT.%20Made%20by%20Diemen%20Design%3A%20https%3A%2F%2Fgithub.com%2FDiemenDesign%2FLibreICONS%20--%3E%3Csvg%20fill%3D%22%23000000%22%20width%3D%22800px%22%20height%3D%22800px%22%20viewBox%3D%220%200%2014%2014%22%20role%3D%22img%22%20focusable%3D%22false%22%20aria-hidden%3D%22true%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M%2012.941406%2C5.32656%2011.755469%2C1.76875%20C%2011.603125%2C1.30937%2011.174219%2C1%2010.689063%2C1%20L%207.375%2C1%20l%200%2C4.5%205.594531%2C0%20c%20-0.0094%2C-0.0586%20-0.0094%2C-0.11719%20-0.02812%2C-0.17344%20z%20M%206.625%2C1%203.3109375%2C1%20C%202.8257812%2C1%202.396875%2C1.30937%202.2445312%2C1.76875%20L%201.0585937%2C5.32656%20C%201.0398437%2C5.38286%201.0398437%2C5.44141%201.0304687%2C5.5%20L%206.625%2C5.5%206.625%2C1%20Z%20M%201%2C6.25%201%2C11.875%20C%201%2C12.49609%201.5039062%2C13%202.125%2C13%20l%209.75%2C0%20C%2012.496094%2C13%2013%2C12.49609%2013%2C11.875%20l%200%2C-5.625%20-12%2C0%20z%22%2F%3E%3C%2Fsvg%3E'

            for key in bestsellers_country_keys:
                is_country = key.startswith('bestsellers_list_')
                if is_country:
                    country_code = key.split('_')[-1]
                    
                    offer_list = bestsellers_data[key]['offer_list']
                    expiry_date = bestsellers_data[key]['expiry_date']
                    bestsellers_countries.append({
                        'country_code': country_code,
                        'offer_list': offer_list,
                        'expiry_date': expiry_date
                    })

            # flip into a per offer id and countries
            per_offer_id = {}

            for country in bestsellers_countries:
                country_code = country['country_code']
                offer_list = country['offer_list']
                for offer_id in offer_list:
                    if offer_id not in per_offer_id:
                        per_offer_id[offer_id] = {
                            'offer_id': offer_id,
                            'countries': [],
                            'expiry_date': expiry_date
                        }
                    per_offer_id[offer_id]['countries'].append({
                        'code': country_code,
                        'rank': offer_list.index(offer_id) + 1
                    })

            shop_req = requests.get(f"https://fortnite-api.com/v2/shop?responseFlags=7")
            shop_req.raise_for_status()
            shop_data = shop_req.json()

            shop_entries = shop_data['data']['entries']

            logging.debug(f'[GET] {constants.FN_CATALOG}')
            headers = {
                'Authorization': self.bot.oauth_manager.session_token
            }
            response = requests.get(constants.FN_CATALOG, headers=headers)
            if response.status_code == 401 or response.status_code == 403:
                self.bot.oauth_manager._create_token()
                raise Exception('Please try again.')

            data = response.json()
            
            storefront = discord.utils.find(lambda storefront: storefront['name'] == 'BRWeeklyStorefront', data['storefronts'])
            entries = storefront['catalogEntries']
            open('storefront.json', 'w').write(json.dumps(storefront, indent=4))

            data_to_give_to_website = {
                'items': []
            }

            for offer in per_offer_id.keys():
                offer_info = next((x for x in entries if x['offerId'] == offer), None)
                if offer_info is None:
                    logging.warning(f"Offer {offer} not found in storefront.")
                    continue
                
                offer_type = offer_info['meta']['templateId'].split(":")[0]
                # print(offer_type)

                devname = offer_info['devName']
                # print(devname)

                offer_countries = per_offer_id[offer]['countries']
                # print(offer_countries)

                # first locate the item in shop_data
                offer_in_shop_data = discord.utils.find(lambda x: x['offerId'] == offer, shop_entries)

                if offer_in_shop_data is None:
                    logging.warning(f"Offer {offer} not found in shop_data.")
                    continue

                item_image_url = None

                allowed_item_types = [
                    'SparksSong',
                    'SparksGuitar',
                    'SparksBass',
                    'SparksMicrophone',
                    'SparksKeytar',
                    'SparksDrums',
                    'SparksAura',
                    'SparksDrum', # for good measure
                    'SparksDrumkit' # good measure again
                ]

                english_item_types = {
                    'SparksSong': 'Jam Track',
                    'SparksMicrophone': 'Microphone',
                    'SparksGuitar': 'Guitar',
                    'SparksBass': 'Bass',
                    'SparksKeytar': 'Keytar',
                    'SparksDrums': 'Drums',
                    'SparksAura': 'Aura',
                    'SparksDrum': 'Drums',
                    'SparksDrumkit': 'Drums'
                }

                # why fortnite-api.com?
                try: 
                    item_image_url = offer_in_shop_data['newDisplayAsset']['renderImages'][0]['image']
                except:
                    try:
                        item_image_url = offer_in_shop_data['tracks'][0]['albumArt']
                    except:
                        try:
                            item_image_url = offer_in_shop_data['images']['icon']
                        except:
                            try:
                                item_image_url = offer_in_shop_data['images']['large']
                            except:
                                logging.warning(f"image not found")
                
                if offer_type == "DynamicBundle":
                    bundle_items = offer_info['dynamicBundleInfo']['bundleItems']
                    
                    first_item_name = ""
                    first_item_subtitle = ""
                    remaining_item = 0

                    background_image = ""
                    image_urls = []
                    first_item_set = False

                    bundle_image_url = None

                    bundle_name = "Cannot access bundle name"

                    try:
                        bundle_name = offer_in_shop_data['bundle']['name']
                        bundle_image_url = offer_in_shop_data['bundle']['image']
                    except Exception as e:
                        logging.warning(f"Bundle name not found for offer {offer} {offer_in_shop_data}", exc_info=e)

                    for bundle_item in bundle_items:
                        item_type = bundle_item['item']['templateId'].split(":")[0]
                        item_id = bundle_item['item']['templateId'].split(":")[1]

                        if item_type not in allowed_item_types:
                            continue

                        # locate the item inside shop_data bundle items
                        sub_item_img_url = None

                        brItems = offer_in_shop_data.get('brItems', [])
                        tracks = offer_in_shop_data.get('tracks', [])
                        instruments = offer_in_shop_data.get('instruments', [])

                        item = discord.utils.find(lambda x: x['id'].lower() == item_id.lower(), brItems)

                        if item is None:
                            logging.warning(f"Item {item_id} not found in {offer_in_shop_data['devName']} britems.")

                            item = discord.utils.find(lambda x: x['id'].lower() == item_id.lower(), instruments)
                            if item is None:
                                logging.warning(f"Item {item_id} not found in {offer_in_shop_data['devName']} instruments.")

                                item = discord.utils.find(lambda x: x['id'].lower() == item_id.lower(), tracks)
                                if item is None:
                                    logging.warning(f"Item {item_id} not found in {offer_in_shop_data['devName']} tracks.")
                                    continue

                        try:
                            sub_item_img_url = item['images']['icon']
                        except:
                            try:
                                sub_item_img_url = item['newDisplayAsset']['renderImages'][0]['image']
                            except:
                                try:
                                    sub_item_img_url = item['images']['large']
                                except:
                                    try:
                                        sub_item_img_url = item['albumArt']
                                    except:
                                        logging.warning(f"Item {item_id} not found in {offer_in_shop_data['devName']} image urls.")
                                        continue

                        item_name = item.get('name', 'Name Not Available')
                        if item_name == 'Name Not Available':
                            pass
                        item_subtitle = english_item_types[item_type]

                        if item_type == 'SparksSong':
                            item_name = item['title']
                            item_subtitle = item['artist']
                        
                        if not first_item_set:
                            first_item_name = item_name
                            first_item_subtitle = item_subtitle
                            first_item_set = True
                        else:
                            remaining_item += 1

                        try:
                            background_image = item['series']['image']
                        except:
                            pass

                        image_urls.append(sub_item_img_url)

                    bundle_colour_1 = None
                    bundle_colour_2 = None

                    try:
                        bundle_colour_1 = offer_info['meta']['color1']
                        bundle_colour_2 = offer_info['meta']['color2']
                    except:
                        pass

                    item_template_data = {
                        'type': 'multi_item_showcase_product',
                        'image': bundle_image_url,
                        'background_image': background_image,
                        'bundle_colour_1': bundle_colour_1,
                        'bundle_colour_2': bundle_colour_2,
                        'bundle_images': image_urls,
                        'bundle_name': bundle_name,
                        'name': first_item_name,
                        'subtitle': first_item_subtitle,
                        'remaining': remaining_item,
                        'icon': bundle_icon,
                        'countries': list(sorted(offer_countries, key=lambda x: x['rank']))
                    }

                    if len(image_urls) > 0:
                        data_to_give_to_website['items'].append(item_template_data)

                elif offer_type in allowed_item_types:
                    brItems = offer_in_shop_data.get('brItems', [])
                    tracks = offer_in_shop_data.get('tracks', [])
                    instruments = offer_in_shop_data.get('instruments', [])

                    item = None
                    # instruments first, then tracks, then brItems (the order matters)
                    if len(instruments) > 0:
                        item = instruments[0]
                    elif len(tracks) > 0:
                        item = tracks[0]
                    elif len(brItems) > 0:
                        item = brItems[0]

                    item_name = offer_in_shop_data.get('name', 'Name Not Available')
                    if item_name == 'Name Not Available':
                        print('NAME NOT FOUND', offer_in_shop_data)
                        if item:
                            item_name = item.get('name', 'Name Not Available x2')
                        else:
                            logging.warning(f"Item {item_id} not found in {offer_in_shop_data['devName']} {offer_type}s.")

                    print(item_name, offer_type)
                    
                    background = None
                    try:
                        background = item['series']['image']
                    except:
                        try:
                            background = offer_in_shop_data['series']['image']
                        except:
                            pass

                    subtitle = english_item_types[offer_type]
                    if offer_type == "SparksSong":
                        item_name = offer_in_shop_data['tracks'][0]['title']
                        subtitle = offer_in_shop_data['tracks'][0]['artist']

                    item_template_data = {
                        'type': 'solo_showcase_product',
                        'image': item_image_url,
                        'background_image': background,
                        'name': item_name,
                        'subtitle': subtitle,
                        'icon': music_icon,
                        'countries': list(sorted(offer_countries, key=lambda x: x['rank']))
                    }

                    data_to_give_to_website['items'].append(item_template_data)

            open('items.json', 'w').write(json.dumps(data_to_give_to_website, indent=4))

            logging.debug(f"Navigating to {url}")
            await page.goto(url)

            await asyncio.sleep(2)
            await page.evaluate(f"window.setBestsellersData({json.dumps(data_to_give_to_website)})", None)
            await asyncio.sleep(3)

            try:
                output_path = constants.CACHE_FOLDER + "bestsellers.png"
                await page.locator("#container").screenshot(path=output_path)
                open(constants.CACHE_FOLDER + "BestsellersTimestamp.dat", "w").write(str(int(datetime.now().timestamp())))

                return output_path
                
            except asyncio.TimeoutError as e:
                logging.error(f"Timed out waiting for snapshot:", exc_info=e)
                raise Exception("Timed out.")
            finally:
                await browser.close()

    async def handle_cacher(self):
        # this function is ran every minute
        # it should check the hash of the bestsellers response and if it has changed, capture a new screenshot
        # bestsellers hash is also saved locally

        logging.debug('Best sellers task loop start')
        
        url = "https://cdn2.unrealengine.com/fn_bsdata/ebb74910-dd35-44b8-b826-d58dc16c6456.json"
        try:
            req = requests.get(url)
            req.raise_for_status()
        except Exception as e:
            logging.error(f"Error fetching bestsellers data: {e}")
            return

        unix_ts = int(time.time())

        # generate hash of the content to check for changes
        best_sellers_hash = hashlib.md5(req.content).hexdigest()

        if self.last_best_sellers_hash == None:
            # init last best sellers hash
            try:
                self.last_best_sellers_hash = open(constants.CACHE_FOLDER + "BestsellersHash.dat", "r").read().strip()

                ch = await self.bot.fetch_channel(1328386911743639662)
                await ch.send(f"Best Sellers init hashes at <t:{unix_ts}:F>:" +
                f"\nCache: {self.last_best_sellers_hash}\nUpstream: {best_sellers_hash}\nLast Modified: {req.headers.get('Last-Modified', 'N/A')}")
            except Exception as e:
                logging.warning(f"Error reading hash cache: {e}")
                self.last_best_sellers_hash = ""

        logging.debug(f'[GET] {constants.FN_CATALOG}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        shop_response = requests.get(constants.FN_CATALOG, headers=headers)
        shop_data = shop_response.json()

        archive_path = f'{constants.CACHE_FOLDER}/archive_best_sellers/{best_sellers_hash}_{unix_ts}/'

        if self.last_best_sellers_hash != best_sellers_hash:

            channel: discord.TextChannel
            try:
                channel = await self.bot.fetch_channel(1328386911743639662)
            except Exception as e:
                logging.warning(f"Error sending hash change message: {e}")

            if channel:
                await channel.send(
                    f"Best Sellers response has changed" +
                    f"\nUpstream: {best_sellers_hash}" +
                    f"\nCache: {self.last_best_sellers_hash}" + 
                    f"\nLast Modified header: {req.headers.get('Last-Modified', 'N/A')}")

                await channel.send(
                    f"Rendering image..."
                )

            await self.capture_renderer_screenshot(auto=True)

            if channel:
                await channel.send(file=discord.File(constants.CACHE_FOLDER + "bestsellers.png"))

            self.last_best_sellers_hash = best_sellers_hash
            try:
                os.makedirs(archive_path, exist_ok=True)
                with open(f'{archive_path}BestSellers.json', 'wb') as f:
                    f.write(req.content)

                with open(f'{archive_path}Shop.json', 'w', encoding='utf-8') as f:
                    json.dump(shop_data, f, indent=4)
            except Exception as e:
                logging.error(f"Error archiving bestsellers: {e}")

            open(constants.CACHE_FOLDER + "BestsellersHash.dat", "w").write(best_sellers_hash)

        # Check if we should notify subscribers
        if self.last_notified_hash == None:
            try:
                self.last_notified_hash = open(constants.CACHE_FOLDER + "BestsellersLastNotifiedHash.dat", "r").read().strip()

                ch = await self.bot.fetch_channel(1328386911743639662)
                await ch.send(f"Best Sellers notif hash init at <t:{unix_ts}:F>:" +
                    f"\nHash: {self.last_notified_hash}")

            except Exception as e:
                logging.warning(f"Error reading hash cache / File does not exist?: {e}")
                self.last_notified_hash = "Error at time of read/file may not exist yet"

        current_utc_hour = datetime.now(timezone.utc).hour
        in_window = current_utc_hour in [0, 1, 2]
        should_notify = False

        if in_window:
            if current_utc_hour == 2 and self.last_notified_hash != best_sellers_hash:
                should_notify = True
        else:
            if self.last_notified_hash != best_sellers_hash:
                should_notify = True

        if should_notify:
            ch = await self.bot.fetch_channel(1328386911743639662)
            await ch.send(f"Subscribers should currently be notified" + 
            f"\nUpstream: {best_sellers_hash}" +
            f"\nLast: {self.last_notified_hash}\nAt <t:{unix_ts}:F> (window active)")

            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            logging.info(' WERE IN WERE IN  ')
            # TODO: Get channels/users to send notifications to (e.g. combined channels filtered by best sellers event)
            # TODO: Build embed and rendered image attachment
            # Target send loop:
            # await target.send(content=content, embed=embed, file=file)

            self.last_notified_hash = best_sellers_hash

            try:
                open(constants.CACHE_FOLDER + "BestsellersLastNotifiedHash.dat", "w").write(best_sellers_hash)
            except Exception as e:
                logging.error(f"Error updating BestsellersLastNotifiedHash: {e}")

        logging.debug('Best sellers task loop complete')


    async def handle_interaction(self, interaction: discord.Interaction):
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
                output_path = await self.capture_renderer_screenshot(auto=True)
        except Exception as e:
            logging.warning(f"Error checking cache: {e}")
            output_path = await self.capture_renderer_screenshot(auto=True)

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