from hashlib import md5
from urllib.parse import quote
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date

icons = [
    {"key": "turtle", "icon": "🐢"},
    {"key": "rabbit", "icon": "🐇"},
    {"key": "squirrel", "icon": "🐿️"},
    {"key": "flamingo", "icon": "🦩"},
    {"key": "zebra", "icon": "🦓"},
    {"key": "moose", "icon": "🦌"},
    {"key": "giraffe", "icon": "🦒"},
    {"key": "parrot", "icon": "🦜"},
    {"key": "fox", "icon": "🦊"},
    {"key": "penguin", "icon": "🐧"},
    {"key": "crocodile", "icon": "🐊"},
    {"key": "panda", "icon": "🐼"},
    {"key": "wolf", "icon": "🐺"},
    {"key": "bear", "icon": "🐻"},
    {"key": "dolphin", "icon": "🐬"},
    {"key": "platypus", "icon": "🦔"},
    {"key": "capybara", "icon": "🦙"},
    {"key": "walrus", "icon": "🦭"},
    {"key": "seal", "icon": "🦦"}, 
    {"key": "pepe", "icon": "🐸"},
    {"key": "doge", "icon": "🐕"},
    {"key": "elephant", "icon": "🐘"},
    {"key": "rhinoceros", "icon": "🦏"},
    {"key": "orca", "icon": "🐋"},
    {"key": "tiger", "icon": "🐅"},
    {"key": "shark", "icon": "🦈"},
    {"key": "lion", "icon": "🦁"},
    {"key": "special_icecream", "icon": "🍦"},
    {"key": "special_snake_cobra", "icon": "🐍"},
    {"key": "alpaca", "icon": "🦙"},
    {"key": "mountain_goat", "icon": "🐐"},
]

async def gen_hash(api_time, json_data):
    return md5(f"{api_time}_{quote(json_data)}".encode("utf-8")).hexdigest()

def get_icon(key=None):
    for item in icons:
        if item["key"] == key:
            return item["icon"]
    return '🤡'
        
def user_animals(animal_db, animal_user):
    user_animals = []
    for item in animal_user:
        animal = next(
            (entry for entry in animal_db if entry['key'] == item['key']), None)
        
        levels = animal['levels']
        
        current_level = next(
            (entry for entry in levels if entry['level'] == item['level']), None)
        
        current_level_index = next(
            (index for index, entry in enumerate(levels) if entry['level'] == item['level']), -1)
        
        next_level = levels[current_level_index + 1] if current_level_index + 1 < len(levels) else None
        
        next_profit_difference = (
            next_level['profit'] - current_level['profit'] if next_level else 0
        )

        user_animals.append({
            **item,
            **animal,
            "currentLevel": current_level,
            "nextLevel": next_level,
            "nextProfitDifference": next_profit_difference
        })
    return user_animals

def new_animals_list(animal_db, animal_user, balance):
    sorted_list = sorted(
        [
            animal for animal in animal_db
            if all(
                [
                    animal['key'] not in [ua['key'] for ua in animal_user],
                    animal['levels'][0]['price'] <= balance,
                    animal.get('dateStart') is None or datetime.utcnow() > parse_date(animal['dateStart']),
                    animal.get('dateEnd') is None or datetime.utcnow() < parse_date(animal['dateEnd'])
                ]
            )
        ],
        key=lambda x: x['levels'][0]['profit'],
        reverse=True
    )
    return sorted_list
    
def upgradable_animals_list(animal_user, balance): 
    upgradable_animals = sorted(
        [
            item
            for item in animal_user
            if item.get("nextLevel") and item["nextLevel"]["price"] <= balance
        ],
        key=lambda x: x["nextProfitDifference"],
        reverse=True,
    )
    return upgradable_animals
    
def available_positions(animal_db, animal_user):
    positions = list(range(1, len(animal_db) + 2))
    used_positions = [ua['position'] for ua in animal_user]
    position_list = [pos for pos in positions if pos not in used_positions]
    return position_list

def require_feed(user_data):
    feed_data = user_data['data'].get('feed', [])
    hero_data = user_data['data'].get('hero', [])
    price_db = user_data['data']['dbData'].get("dbAutoFeed", [])
    
    is_need_feed = feed_data.get("isNeedFeed", False)
    next_feed_time = feed_data.get("nextFeedTime")
    
    has_expired = False
    if next_feed_time:
        next_feed_time_utc = datetime.fromisoformat(next_feed_time)
        has_expired = datetime.utcnow() > next_feed_time_utc
    
    balance = int(hero_data.get("coins", 0))
    tph = hero_data.get("tph", 0)
    
    feed_price_in_tph = next(
        (item.get("priceInTph", 0) for item in price_db if item.get("key") == "instant"),
        0
    )
    
    feed_price = int(int(tph) * feed_price_in_tph)
    
    should_purchase = is_need_feed or has_expired
    can_purchase = balance >= feed_price
    
    return should_purchase and can_purchase

def date_parse(date):
    return parse_date(date) if isinstance(date, str) and date.strip() else None

def date_unix(date):
    try:
        if isinstance(date, str):
            datetime_object = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(date, datetime):
            datetime_object = date
        else:
            raise ValueError("Invalid date format. Must be a string or datetime object.")

        datetime_object = datetime_object.replace(tzinfo=timezone.utc)
        unix_timestamp = int(datetime_object.timestamp())
        return unix_timestamp
    except ValueError as e:
        print(f"Error parsing date: {e}")
        return None