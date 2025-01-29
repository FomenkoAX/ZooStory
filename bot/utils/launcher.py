import asyncio
import argparse
import sys
from datetime import datetime, timezone
from random import randint
from better_proxy import Proxy

from bot.utils import logger
from bot.core.tapper import run_tapper
from bot.core.registrator import register_sessions, get_tg_client
from bot.utils import build_check
from bot.utils.accounts import Accounts
from bot.utils.firstrun import load_session_names

def print_banner():
    print('''
    \033[38;5;128m╔▄▄▄╥▄▄▄▄╥ ,▄######▄, ,▄######▄,\033[38;5;213m  ╔▄▄╥ \033[37m- (ZooStory!)
    \033[38;5;128m""    ║▓▀  [▓Γ    ⅂▓┦ [▓Γ    ⅂▓┦\033[38;5;213m  [▓▓▌ 
    \033[38;5;128m    ,▄╬|   ╫╫|    ╫▓| ╫╫|    ╫▓|\033[38;5;213m  ╘║║╛ 
    \033[38;5;128m  Γ▄█"     ║▓▌    |▓╪ ║▓▌    |▓╪\033[38;5;213m   ▓▓  \033[37m- For education purpose
    \033[38;5;128m_▄█║'      ╘▓▄,__,▄▓╝ ╘▓▄,__,▄▓╝\033[38;5;213m   ▀▀  \033[37m- Version: 1.5 (accounts.json edition)
    \033[38;5;128m"╘╘╘╘╘╘╘╘"  ╘╘╘╘╘╘╘"   ╘╘╘╘╘╘╘" \033[38;5;213m   ╘╘  \033[37m- By [T.Gram]: \033[5m@UglyScripts\033[38;5;135m
    \033[0m''')

    print('''

EN | Mining is about to end on 31st JAN, and using the farm at this time increases the risks.
     If you wish to proceed, please confirm your account by completing a transaction of
     (0.5 TON) in the app to reduce these risks. Avoid using your MAIN ACCOUNT.
          
RU | Майнинг завершится 31 января, и использование фермы в это время увеличивает риски.
     Если вы хотите продолжить, пожалуйста, подтвердите свою учетную запись, завершив транзакцию
     на сумму (0.5 TON) в приложении, чтобы снизить эти риски.
     Избегайте использования вашей ОСНОВНОЙ УЧЕТНОЙ ЗАПИСИ.
                                                 
-> Choose Option to continue (1/2):
    1. Run bot
    2. Create session

    ''')


def get_proxy(raw_proxy: str) -> Proxy:
    return Proxy.from_str(proxy=raw_proxy).as_url if raw_proxy else None


async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform (1/2)")
    action = parser.parse_args().action

    if not action:
        print_banner()

        while True:
            action = input("-> ")

            if not action.isdigit():
                logger.warning("Option must be number")
            elif action not in ["1", "2"]:
                logger.warning("Option must be 1 or 2")
            else:
                action = int(action)
                break

    used_session_names = load_session_names()

    if action == 2:
        await register_sessions()
    elif action == 1:
        accounts = await Accounts().get_accounts()
        await run_tasks(accounts=accounts, used_session_names=used_session_names)

async def mining_end(start_delay: 0):
    await asyncio.sleep(start_delay)
    current_utc_date = datetime.now(timezone.utc)
    comparison_date = datetime(2025, 1, 31, tzinfo=timezone.utc)
    if current_utc_date < comparison_date:
        return True
    else:
        logger.warning("Script Stopped, Mining Phrase has been ended on (31 Jan. 2025)")
        sys.exit(input("Press Enter to exit"))

async def run_tasks(accounts, used_session_names: str):
    await mining_end(0)
    await build_check.check_base_url()
    tasks = []
    for account in accounts:
        session_name, user_agent, raw_proxy = account.values()
        first_run = session_name not in used_session_names
        tg_client = await get_tg_client(session_name=session_name, proxy=raw_proxy)
        proxy = get_proxy(raw_proxy=raw_proxy)
        tasks.append(asyncio.create_task(run_tapper(tg_client=tg_client, user_agent=user_agent, proxy=proxy, first_run=first_run)))
        tasks.append(asyncio.create_task(build_check.check_bot_update_loop(2000)))
        tasks.append(asyncio.create_task(mining_end(2000)))
        await asyncio.sleep(randint(5, 20))

    await asyncio.gather(*tasks)
