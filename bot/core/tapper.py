import asyncio
import traceback
import json
import shutil
import os
import random
import datetime
import brotli
import functools
import string

from typing import Callable
from multiprocessing.util import debug
from time import time
from urllib.parse import unquote, parse_qs, quote

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import (
    Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan,
    AuthKeyDuplicated, SessionExpired, SessionRevoked, FloodWait, UserAlreadyParticipant
)
from pyrogram.raw import types
from pyrogram.raw import functions

from bot.config import settings

from bot.utils import logger
from bot.exceptions import TelegramInvalidSessionException, TelegramProxyError
from .headers import headers

from random import randint

from bot.utils.functions import gen_hash, get_icon, user_animals, new_animals_list, upgradable_animals_list, available_positions, require_feed, date_parse, date_unix

from ..utils.firstrun import append_line_to_file

def error_handler(func: Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            await asyncio.sleep(1)
    return wrapper

class Tapper:
    def __init__(self, tg_client: Client, first_run: bool):
        self.tg_client = tg_client
        self.first_run = first_run
        self.session_name = tg_client.name
        self.bot_peer = 'zoo_story_bot'
        self.api_key = None
        self.upgrade_possible = True
        self.user_animals = None
        self.user_coins = 0

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                await self.tg_client.connect()

            while True:
                try:
                    peer = await self.tg_client.resolve_peer(self.bot_peer)
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"{self.session_name} | FloodWait {fl}")
                    logger.info(f"{self.session_name} | Sleep {fls}s")
                    await asyncio.sleep(fls + 3)
                    
            ref_key = random.choice([settings.REF_KEY, "ref1178697351"]) if settings.SUPPORT_AUTHOR else settings.REF_KEY
            ref_id = ref_key.removeprefix("ref")
            
            web_view = await self.tg_client.invoke(functions.messages.RequestAppWebView(
                peer=peer,
                app=types.InputBotAppShortName(bot_id=peer, short_name="game"),
                platform='android',
                write_allowed=True,
                start_param=ref_key
            ))

            auth_url = web_view.url
            tg_web_data = unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            params = parse_qs(tg_web_data)
            photo_url = json.loads(params.get('user', ['{}'])[0]).get('photo_url', '')
            start_param = params.get('start_param', [''])[0]
            chat_type = params.get('chat_type', [''])[0]
            chat_instance = params.get('chat_instance', [''])[0]
            user_hash = params.get('hash', [''])[0]
            self.api_key = user_hash
            
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            
            login_data = {
                "data":{
                    "initData": tg_web_data,
                    "startParam": start_param,
                    "photoUrl": photo_url,
                    "platform": "android",
                    "chatId": "",
                    "chatType": chat_type,
                    "chatInstance": chat_instance
                    }
                }

            return ref_id, login_data

        except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
                SessionExpired, SessionRevoked):
            raise TelegramInvalidSessionException(f"Telegram session is invalid. Client: {self.tg_client.name}")
        except AttributeError as e:
            raise TelegramProxyError(e)
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)
            
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
                
    @error_handler  
    async def join_and_mute_tg_channel(self, link: str):
        await asyncio.sleep(delay=random.randint(15, 30))
        
        if not self.tg_client.is_connected:
            await self.tg_client.connect()
    
        try:
            path = link.replace("https://t.me/", "")
            if path.startswith('+'):
                invite_hash = path[1:]
                result = await self.tg_client.invoke(functions.messages.ImportChatInvite(hash=invite_hash))
                channel_title = result.chats[0].title
                entity = result.chats[0]
                peer = types.InputPeerChannel(channel_id=entity.id, access_hash=entity.access_hash)
            else:
                peer = await self.tg_client.resolve_peer(f'@{path}')
                channel = types.InputChannel(channel_id=peer.channel_id, access_hash=peer.access_hash)
                await self.tg_client.invoke(functions.channels.JoinChannel(channel=channel))
                channel_title = path

            await asyncio.sleep(delay=3)
            
            await self.tg_client.invoke(functions.account.UpdateNotifySettings(
                peer=types.InputNotifyPeer(peer=peer),
                settings=types.InputPeerNotifySettings(
                    show_previews=False,
                    silent=True,
                    mute_until=2147483647))
            )
            
            logger.success(f"{self.session_name} | Joined & Mute Channel: <y>{channel_title}</y>")
            
        except FloodWait as e:
            logger.warning(f"<ly>{self.session_name}</ly> | {e}.")
            if e.value and settings.FLOOD_WAIT:
                logger.warning(f"<ly>{self.session_name}</ly> | Due to FloodWait Waiting {e.value}s")
                await asyncio.sleep(e.value)
                return False
        except UserAlreadyParticipant:
            logger.info(f"<ly>{self.session_name}</ly> | Already Subscribed to channel: <y>{link}</y>")
        except Exception as e:
            logger.error(f"<ly>{self.session_name}</ly> | (Task) Error Subscribing channel {link}: {e}")
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            await asyncio.sleep(random.randint(10, 20))
        
    @error_handler
    async def change_tg_name(self, name):
        await asyncio.sleep(delay=random.randint(15, 30))
        
        if not self.tg_client.is_connected:
            await self.tg_client.connect()
    
        try:
            me = await self.tg_client.get_me()
            current_first_name = me.first_name
            current_last_name = me.last_name or ""
            if name in current_last_name or name in current_first_name:
                return
            
            updated_last_name = f"{current_last_name} {name}".strip()
            await self.tg_client.update_profile(last_name=updated_last_name)
            logger.info(f"{self.session_name} | Successfully updated Name to: <y>{current_first_name} {updated_last_name}</y>")
        except Exception as e:
            logger.error(f"{self.session_name} | Error updating Name: {str(e)}")
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            await asyncio.sleep(random.randint(10, 20))

    @error_handler
    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='http://ip-api.com/json', timeout=aiohttp.ClientTimeout(20))
            response.raise_for_status()

            response_json = await response.json()
            ip = response_json.get('query', 'N/A')
            country = response_json.get('country', 'N/A')

            logger.info(f"{self.session_name} | Proxy IP : {ip} | Proxy Country : {country}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    @error_handler
    async def make_request(
        self,
        http_client: aiohttp.ClientSession,
        method,
        endpoint=None,
        url=None,
        extra_headers=None,
        web_boundary=None,
        json_data=None,
        urlencoded_data=None,
        **kwargs
        ):
        full_url = url or f"https://api.zoo.team{endpoint or ''}"
        
        request_headers = http_client._default_headers.copy()
        if extra_headers:
            request_headers.update(extra_headers)
            
        if web_boundary:
            boundary = "------WebKitFormBoundary" + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            body = "\r\n".join(
                f"{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}"
                for key, value in web_boundary.items()
            ) + f"\r\n{boundary}--\r\n"

            request_headers["Content-Type"] = f"multipart/form-data; boundary=----{boundary.strip('--')}"
            kwargs["data"] = body
            
        elif json_data is not None:
            request_headers["Content-Type"] = "application/json"
            kwargs["json"] = json_data

        elif urlencoded_data is not None:
            request_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            kwargs["data"] = aiohttp.FormData(urlencoded_data)

        retries = 0
        max_retries = settings.MAX_REQUEST_RETRY
        
        while retries < max_retries:
            try:
                response = await http_client.request(method, full_url, headers=request_headers, **kwargs)
                response.raise_for_status()
                
                if settings.SAVE_RESPONSE_DATA:
                    response_data = ""
                    response_data += f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Session: {self.session_name}\n\n"
                    response_data += f"Request URL: {full_url}\n"

                    if method == 'POST':
                        request_body = kwargs.get('json', None)
                        if request_body is not None:
                            response_data += f"Request Body (JSON): {json.dumps(request_body, indent=2)}\n\n"
                        else:
                            request_body = kwargs.get('data', None)
                            if request_body is not None:
                                response_data += f"Request Body (Data): {request_body}\n\n"

                    response_data += f"Response Code: {response.status}\n"
                    response_data += f"Response Headers: {dict(response.headers)}\n"
                    response_data += f"Response Body: {await response.text()}\n"
                    response_data += "-" * 50 + "\n"
                    
                    with open("saved_data.txt", "a", encoding='utf8') as file:
                        file.write(response_data)
                response_json = await response.json()
                return response_json
            except aiohttp.ClientResponseError as error:
                
                if settings.SAVE_RESPONSE_DATA:
                    response_data = ""
                    response_data += f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Session: {self.session_name}\n\n"
                    response_data += f"Request URL: {full_url}\n"

                    if method == 'POST':
                        request_body = kwargs.get('json', None)
                        if request_body is not None:
                            response_data += f"Request Body (JSON): {json.dumps(request_body, indent=2)}\n\n"
                        else:
                            request_body = kwargs.get('data', None)
                            if request_body is not None:
                                response_data += f"Request Body (Data): {request_body}\n\n"

                    response_data += f"Response Code: {error.status}\n"
                    response_data += f"Response Headers: {dict(error.headers)}\n"
                    response_data += f"Response Message: {await error.message}\n"
                    response_data += "-" * 50 + "\n"
                    
                    with open("saved_data.txt", "a", encoding='utf8') as file:
                        file.write(response_data)
                        
                if error.status in (500, 502, 503):
                    retries += 1
                    logger.warning(f"{self.session_name} | Received <r>{error.status}</r>, retrying {retries}/{max_retries}...")
                    await asyncio.sleep(2 ** retries)
                    continue
                else:
                    logger.error(f"{self.session_name} | HTTP error: {error}")
                    raise
            except (aiohttp.ClientError, Exception) as error:
                print(traceback.format_exc())
                logger.error(f"{self.session_name} | Unknown error when processing request: {error}")
                raise
        logger.error(f"{self.session_name} | Max retries reached for 'Server Un-Reachable' error.")
        raise aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=503,
            message="Max retries reached for 503 errors."
        )
    
    @error_handler
    async def login(self, http_client: aiohttp.ClientSession, login_json):
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(login_json))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': 'empty',
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/telegram/auth", json_data=login_json, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None

    @error_handler
    async def user_data(self, http_client: aiohttp.ClientSession):
        json_data = {"data":{}}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        response = await self.make_request(http_client, 'POST', endpoint="/user/data/all", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def refer_finish(self, http_client: aiohttp.ClientSession, refer):
        json_data = {"data":refer}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/alliance/user/info", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def onboard_finish(self, http_client: aiohttp.ClientSession):
        json_data = {"data":1}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/hero/onboarding/finish", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def after_data(self, http_client: aiohttp.ClientSession):
        json_data = {"data":{"lang":"en"}}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/user/data/after", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def check_in(self, http_client: aiohttp.ClientSession, day):
        json_data = {"data":day}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/quests/daily/claim", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def check_quest(self, http_client: aiohttp.ClientSession, quest, quest_solution=None):
        json_data = {"data": [quest, quest_solution]}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }

        response = await self.make_request(http_client, 'POST', endpoint="/quests/check", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == False and response.get("error", {}) == "need requirements":
            return 'wrong'
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def claim_quest(self, http_client: aiohttp.ClientSession, quest, quest_solution=None):
        json_data = {"data": [quest, quest_solution]}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/quests/claim", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def result_quiz(self, http_client: aiohttp.ClientSession, quiz, quiz_answer=None):
        json_data = {"data": {"key": quiz, "result": quiz_answer}}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/quiz/result/set", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def claim_quiz(self, http_client: aiohttp.ClientSession, quiz):
        json_data = {"data": {"key": quiz}}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/quiz/claim", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def buy_animal(self, http_client: aiohttp.ClientSession, animal, position):
        json_data = {"data": {"position": position, "animalKey": animal}}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/animal/buy", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    @error_handler
    async def buy_feed(self, http_client: aiohttp.ClientSession):
        json_data = {"data": "instant"}
        api_time = str(int(time()))
        api_hash = await gen_hash(api_time=api_time, json_data=json.dumps(json_data))
        additional_headers = {
            'Api-Time': api_time,
            'Api-Key': self.api_key,
            'Api-Hash': api_hash
        }
        
        response = await self.make_request(http_client, 'POST', endpoint="/autofeed/buy", json_data=json_data, extra_headers=additional_headers)
        if response.get("success", {}) == True:
            return response
        return None
    
    async def run(self, user_agent: str, proxy: str | None) -> None:
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        headers["User-Agent"] = user_agent

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn, trust_env=True) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            delay = randint(settings.START_DELAY[0], settings.START_DELAY[1])
            logger.info(f"{self.session_name} | Starting in {delay} seconds")
            await asyncio.sleep(delay=delay)
            
            while True:
                try:
                    if settings.NIGHT_MODE:
                        current_utc_time = datetime.datetime.utcnow().time()

                        start_time = datetime.time(settings.NIGHT_TIME[0], 0)
                        end_time = datetime.time(settings.NIGHT_TIME[1], 0)

                        next_checking_time = randint(settings.NIGHT_CHECKING[0], settings.NIGHT_CHECKING[1])

                        if start_time <= current_utc_time <= end_time:
                            logger.info(f"{self.session_name} | Night-Mode is on, The current UTC time is {current_utc_time.replace(microsecond=0)}, next check-in on {round(next_checking_time / 3600, 1)} hours.")
                            await asyncio.sleep(next_checking_time)
                            continue

                    sleep_time = randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])

                    try:
                        ref_id, login_json = await self.get_tg_web_data(proxy=proxy)
                    except TelegramProxyError:
                        return logger.error(f"<r>The selected proxy cannot be applied to the Telegram client.</r>")
                    except Exception as e:
                        return logger.error(f"Stop Tapper. Reason: {e}")
                    
                    logger.info(f"{self.session_name} | Trying to login")
                    
                    # Login
                    login_data = await self.login(http_client, login_json=login_json)
                    if not login_data:
                        logger.error(f"{self.session_name} | Login Failed")
                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                        await asyncio.sleep(delay=sleep_time)
                        continue
                    
                    logger.success(f"{self.session_name} | <g>🦒 Login Successful</g>")
                    
                    # User-Data
                    user_data = await self.user_data(http_client)
                    if not user_data:
                        logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                        await asyncio.sleep(delay=sleep_time)
                        break
                    
                    onboard = user_data['data']['hero'].get('onboarding')
                    animals = user_data['data'].get('animals')
                    self.user_animals = animals
                    
                    tokens = user_data['data']['hero'].get('tokens')
                    self.user_coins = int(user_data['data']['hero'].get('coins'))
                    
                    tkperhr = user_data['data']['hero'].get('tph')
                    
                    quests = user_data['data']['dbData'].get('dbQuests')
                    friends = user_data['data']['profile'].get('friends') or 0
                    
                    quizzes = user_data['data']['dbData'].get('dbQuizzes')
                    
                    db_animals = user_data['data']['dbData'].get('dbAnimals')
                    
                    after_data = await self.after_data(http_client)
                    if not after_data:
                        logger.error(f"{self.session_name} | Unknown error while collecting User after Data!")
                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                        await asyncio.sleep(delay=sleep_time)
                        break
                    
                    quest_check = after_data['data'].get('quests')
                    quiz_check = after_data['data'].get('quizzes')
                    
                    if len(onboard) == 0 and len(animals) == 0:
                        logger.info(f"{self.session_name} | Non-Invited account. Using Refer...")
                        await asyncio.sleep(randint(2, 5))
                        refer_data = await self.refer_finish(http_client, refer=ref_id)
                        if not refer_data:
                            logger.error(f"{self.session_name} | Unknown error while using refer code!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            break
                        await asyncio.sleep(randint(2, 5))
                        onboard_data = await self.onboard_finish(http_client)
                        if not onboard_data:
                            logger.error(f"{self.session_name} | Unknown error while collecting On-Board Data!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            break
                        logger.success(f"{self.session_name} | <g>Account Registered!</g>")
                    
                    logger.success(f"{self.session_name} | Feed: <g>{self.user_coins}</g> | Coins: <g>{tokens}</g> | Coins/Hour: <g>{tkperhr}</g>")
                    
                    await asyncio.sleep(randint(1, 3))
                        
                    # Check-In
                    if settings.AUTO_SIGN_IN:
                        day_check = [k for k, v in after_data['data']['dailyRewards'].items() if v == 'canTake']
                        
                        if day_check:
                            checkin_data = await self.check_in(http_client, day=int(day_check[0]))
                            if not checkin_data:
                                logger.error(f"{self.session_name} | Unknown error while check-in!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                break
                            
                            reward_money = next((item['rewardMoney'] for item in user_data['data']['dbData']['dbDailyRewards'] if item['key'] == int(day_check[0])), 0)
                            self.user_coins = int(reward_money) + self.user_coins
                            logger.success(f"{self.session_name} | Check-In Successful <y>{day_check[0]}</y>: <g>+{reward_money} Feed</g>")

                        await asyncio.sleep(randint(1, 3))
                        
                    # Quests
                    if settings.AUTO_TASK:
                        tasks = [
                            task
                            for task in quests
                            if (
                                task["checkType"] == "telegramChannel"
                                or (task["checkType"] == "invite" and task["checkCount"] <= int(friends))
                                or task["checkType"] == "fakeCheck"
                                or (task["checkType"] == "checkCode" and task["key"].startswith(("rebus_", "riddle_")))
                                or (
                                    task["key"].startswith("chest_")
                                    and datetime.datetime.utcnow() > date_parse(task["dateStart"])
                                    and datetime.datetime.utcnow() < date_parse(task["dateEnd"])
                                    and datetime.datetime.utcnow() > date_parse(task["actionTo"])
                                )
                            )
                        ]

                        finished = [task for task in tasks if any(q["key"] == task["key"] for q in quest_check)]
                        pending = [task for task in tasks if task not in finished]
                        if len(pending) > 0:
                            logger.info(f"{self.session_name} | Task: <le>{len(tasks)}</le> | Pending Task: <y>{len(pending)}</y> | Finished Task: <g>{len(finished)}</g>")
                            logger.info(f"{self.session_name} | Processing Tasks...")
                            
                            for task in pending:
                                if "t.me" in task.get("actionUrl", "") and "telegramChannel" in task.get("checkType", ""):
                                    if settings.AUTO_JOIN_CHANNELS:
                                        join_data = await self.join_and_mute_tg_channel(link=task["actionUrl"])
                                        if join_data == False:
                                            continue
                                        await asyncio.sleep(random.randint(5, 10))
                                        
                                if task["key"].startswith("chest_"):
                                    action_date = date_parse(date=task["actionTo"])
                                    if action_date:
                                        chest_time = date_unix(date=action_date) - date_unix(date=datetime.datetime.utcnow())
                                        if chest_time <= sleep_time and settings.CHEST_SLEEP:
                                            logger.info(f"{self.session_name} | Sleeping <y>{round(chest_time / 60, 1)}</y> min, Until Chest appears...")
                                            await asyncio.sleep(delay=chest_time + 120)
                                        if chest_time > sleep_time and settings.CHEST_SLEEP:
                                            continue
                                            
                                if task.get("checkType") != "fakeCheck":
                                    await self.check_quest(http_client, quest=task["key"])
                                    
                                if task.get("checkType") == "checkCode":
                                    await self.check_quest(http_client, quest=task["key"], quest_solution=task["checkData"])
                    
                                data_done = await self.claim_quest(http_client, quest=task["key"])
                                if data_done:
                                    self.user_coins = int(task['reward']) + self.user_coins
                                    task_title = task.get('title') or ("Chest" if task.get('key').startswith("chest_") else task_title)
                                    logger.success(f"{self.session_name} | Task: <y>{task_title}</y> | Reward: <y>+{task['reward']} Feed</y>")
                                    quest_check.append({"key": task["key"]})
                                    
                                await asyncio.sleep(random.randint(3, 6))
                                
                    # Auto Quiz
                    if settings.AUTO_QUIZ:
                        finished_quiz = [
                            quiz for quiz in quizzes
                            if any(q["key"] == quiz["key"] for q in quiz_check)
                        ]
                        
                        pending_quiz = [
                            quiz for quiz in quizzes
                            if not any(q["key"] == quiz["key"] for q in quiz_check)
                        ]
                        
                        if len(pending_quiz) > 0:
                            logger.info(f"{self.session_name} | Quiz: <le>{len(quizzes)}</le> | Pending Quiz: <y>{len(pending_quiz)}</y> | Finished Quiz: <g>{len(finished_quiz)}</g>")
                            logger.info(f"{self.session_name} | Processing Quizzes...")
                        
                        for quiz in pending_quiz:
                            quiz_key = quiz["key"]
                            quiz_answer = random.choice(quiz["answers"])["key"]
                            
                            result_quiz = await self.result_quiz(http_client, quiz=quiz_key, quiz_answer=quiz_answer)
                            if not result_quiz:
                                logger.error(f"{self.session_name} | Unknown error while resulting quiz!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            
                            done_quiz = await self.claim_quiz(http_client, quiz=quiz_key)
                            if done_quiz:
                                self.user_coins = int(quiz['reward']) + self.user_coins
                                logger.success(f"{self.session_name} | Quiz: <y>{quiz_key}</y> | Reward: <y>+{quiz['reward']} Feed</y>")
                                quiz_check.append({"key": quiz_key})
                            
                            await asyncio.sleep(random.randint(5, 8))
                    
                    # Auto Feed
                    if settings.AUTO_FEED:
                        feed_requires = require_feed(user_data=user_data)
                        if feed_requires:
                            logger.info(f"{self.session_name} | Feeding Animals...")
                            feed_animals = await self.buy_feed(http_client)
                            if feed_animals:
                                logger.success(f"{self.session_name} | Auto feed purchased!")
                            
                    # Auto Upgrade
                    if settings.AUTO_UPGRADE:
                        logger.info(f"{self.session_name} | Upgrading Animals...")
                         
                        while self.upgrade_possible:
                            save_feed = self.user_coins - settings.SAVE_FEED
                            user_animal_list = user_animals(animal_db=db_animals, animal_user=self.user_animals)
                            new_animals = new_animals_list(animal_db=db_animals, animal_user=user_animal_list, balance=save_feed)
                            upgradable_animals = upgradable_animals_list(animal_user=user_animal_list, balance=save_feed)
                            
                            if not new_animals and not upgradable_animals:
                                logger.info(f"{self.session_name} | No more animals to upgrade, Stopping...")
                                self.upgrade_possible = False
                                break
                            
                            collection = new_animals if new_animals else upgradable_animals
                            animal = collection[0]
                            position = animal.get("position") or available_positions(animal_db=db_animals, animal_user=user_animal_list)[0]
                            
                            purchase_animal = await self.buy_animal(http_client, animal=animal['key'], position=position)
                            if purchase_animal:
                                emoji = get_icon(key=animal['key'])
                                logger.success(f"{self.session_name} | Animal Purchased {emoji}: <y>{animal['title']}</y>")
                                self.user_animals = purchase_animal['data'].get('animals')
                                self.user_coins = purchase_animal['data']['hero'].get('coins')
                                tokens = purchase_animal['data']['hero'].get('tokens')
                                tkperhr = purchase_animal['data']['hero'].get('tph')
                                
                                
                            if not purchase_animal:
                                logger.error(f"{self.session_name} | Something Went Wrong, animal can not be purchased!")
                            
                            await asyncio.sleep(random.randint(5, 8))

                        logger.info(f"{self.session_name} | Upgrade Completed!")
                        logger.success(f"{self.session_name} | Updated Feed: <g>{self.user_coins}</g> | Updated Coins: <g>{tokens}</g> | Updated Coins/Hour: <g>{tkperhr}</g>")
                         
                    logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                    await asyncio.sleep(delay=sleep_time)

                except Exception as error:
                    print(traceback.format_exc())
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    await asyncio.sleep(delay=3)

async def run_tapper(tg_client: Client, user_agent: str, proxy: str | None, first_run: bool):
    try:
        await Tapper(tg_client=tg_client, first_run=first_run).run(user_agent=user_agent, proxy=proxy)
    except TelegramInvalidSessionException:
        session_file = f"sessions/{tg_client.name}.session"
        if not os.path.exists("sessions/deleted_sessions"):
            os.makedirs("sessions/deleted_sessions", exist_ok=True)
        shutil.move(session_file, f"sessions/deleted_sessions/{tg_client.name}.session")
        logger.error(f"Telegram account {tg_client.name} is not work!")
