import threading
import json
import os
from datetime import datetime, timezone, timedelta
import time
import re
import requests
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import sync_playwright

AUTH_FILE = "auth.json"
HISTORY_FILE = "history.txt"
ALL_ORDERS_URL = "https://merchant-eu.mykeeta.com/api/order/history/getOrders"
PAGE_URL = "https://merchant-eu.mykeeta.com/m/web/mach/b_pc_order_history_list?locale=en&cityId=101200020"
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080/api/keeta/create_order")

HEADERS = {    'accept': 'application/json, text/plain, */*',
    'accept-language': 'pl,ru;q=0.9,en-US;q=0.8,en;q=0.7,ar;q=0.6',
    'accountid': '4611686018429226254',
    'appversion': '',
    'cityid': '101200020',
    'clienttype': 'b_pc',
    'content-type': 'application/json',
    'locale': 'en',
    'm-appkey': 'fe_com.keetapp.sailorfe.b.pc',
    'm-traceid': '-4217100518479034698',
    'mtgsig': '{"a1":"1.2","a2":1768137921239,"a3":"00w4v2122w485477yzz43w96w91v073z80y01y3809197958uz1u53v8","a5":"bEKr7Rbjpw1KtLRDn9FhdRY+ZICl/xX+YJNYO8Rtd084vLe7QO89k9VuuDwizQb8fiL/8EbSCshHOdxaODUFHoeex3w5FzKu2vG2k8LZol1GmIpK3un6263stb1qNpxdvtd5J4dEveI=","a6":"h1.8xw4HFwDNZANKXewnYBzxLQNyj3OpThVoY4x1V2C8wbs7wjeduBwOMRFdIKVPs1tBD76j+6Y8JHipFONXve+Ohs6Jzr1VTAoriltEvE/fue6Mm4pUAxCWYaorw8hoHTGR9LD2McLrPZ0rdJVHOvy+WOp15NTXkXzUza/Sii6vbXtNPnoR4AxAovOSAKjTknW9wO0YYk6ZwU9EF40jkdAPuROW9HI6ECOVIJ6qdvvh0nQVxLCJ3UB0psRS4rSw5VaixTQMDDFFdKgZvJGIgj4vLYAN0VZhKL2tYcVp9wsOvFE8/2PaQ+DkX6SryG23yBrBaVBNQnX1DhNVPkk+O4QBgx9xYj2fdfGd4Cl5llHfoOMhyASx4vVTf5DWaiByaIM/","a8":"bf52a4cb1983351bacfde0b2147ef097","a9":"3.4.0,7,185","a10":"e6","x0":4,"d1":"514940208d02349bf19e5b6fdc4b74b8"}',
    'opcenterselectedregion': 'BH',
    'origin': 'https://merchant-eu.mykeeta.com',
    'platform': '1',
    'priority': 'u=1, i',
    'referer': 'https://merchant-eu.mykeeta.com/web/mach/b_pc_order_history_list?locale=en&cityId=101200020',
    'region': 'BH',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'shopid': '100728298',
    'syslocale': 'en',
    'timezone': 'GMT+08:00',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15',}

AVAILABLE_BRANCHES = {
    "Hidd": "2e8c35f7-d75e-4442-b496-cbb929842c10"
}


WEEKLY_SCHEDULE = {
    0: [14, 24],
    1: [14, 24],  # Вторник
    2: [14, 14],  # Среда
    3: [15, 2],  # Четверг (до 3 ночи)
    4: [15, 2],  # Пятница
    5: [14, 24],
    6: [None, None]
}

MENU_CATEGORIES = {
    "Pizzas": {
        "Pepperoni",
        "Margherita",
        "BBQ Chicken Ranch",
        "Smoked Turkey And Mushroom",
        "Four Cheese",
        "Seafood",
        "Hawaiian",
        "Vegetarian",
        "Veggie Mexican",
    },
    "Brick Pizzas": {
        "Pepperoni Detroit Brick",
        "Smoked Turkey And Mushroom Detroit Brick",
        "BBQ Chicken Ranch Detroit Brick",
        "Margherita Detroit Brick"
    },
    "Beverages": {
        "Coca Cola Zero",
        "Coca Cola",
        "7Up Diet",
        "Fanta Orange",
        "Kinza Cola",
        "Water",
        "Mirinda Citrus",
        "7Up"
    },
    "Sauces": {
        "Hot Honey Sauce",
        "Ranch Sauce",
        "BBQ Sauce",
        "Honey Mustard Sauce",
    },
    "Combo Deals": {
        "Detroit Combo",
        "Pizza Combo"
    },
    "Sides": {
        "Cheesy Garlic Baguette"
    }
}


class MenuMatcher:
    @staticmethod
    def match_item(raw_name):
        name = raw_name.strip()

        size = None

        if re.search(r'(?i)\b(Small|S)\b', name):
            size = "S"
        elif re.search(r'(?i)\b(Medium|M)\b', name):
            size = "M"
        elif re.search(r'(?i)\b(Large|L)\b', name):
            size = "L"

        clean_name = re.sub(r'(?i)\b(Small|Medium|Large|Size|S|M|L)\b', '', name)

        clean_name = re.sub(r'[()\[\]-]', '', clean_name).strip()

        found_cat, found_name = MenuMatcher._find_in_dict(clean_name)

        if found_cat:
            return found_name, found_cat, size

        name_without_pizza = re.sub(r'(?i)\bPizza\b', '', clean_name).strip()

        found_cat_2, found_name_2 = MenuMatcher._find_in_dict(name_without_pizza)
        if found_cat_2:
            return found_name_2, found_cat_2, size

        return clean_name, "Other", size

    @staticmethod
    def _find_in_dict(name_to_check):
        name_lower = name_to_check.lower()

        for category, items in MENU_CATEGORIES.items():
            for item in items:
                if item.lower() == name_lower:
                    return category, item
        return None, None

def load_cookies():
    if not os.path.exists(AUTH_FILE):
        print(f"❌ Ошибка: Файл {AUTH_FILE} не найден.")
        return None
    try:
        with open(AUTH_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)

            if isinstance(data, list):
                try:
                    return {cookie['name']: cookie['value'] for cookie in data}
                except TypeError:
                    print("❌ Ошибка формата auth.json: внутри списка не объекты.")
                    return None

            elif isinstance(data, dict):
                if "cookies" in data and isinstance(data["cookies"], list):
                    return {c['name']: c['value'] for c in data["cookies"]}

                return data

            else:
                print(f"❌ Непонятный формат в auth.json. Тип данных: {type(data)}")
                return None

    except Exception as e:
        print(f"❌ Ошибка чтения куки: {e}")
        return None


def parse_options(attributes_list, is_combo, size):
    result = {
        "is_thin_dough": False,
        "is_garlic_crust": False,
        "size": None,
        "order_items": [],
        "combo_items": [],
        'description_parts': [],
        'description': '',
    }

    for modifier in attributes_list:
        if not modifier: continue

        if not is_combo:
            if modifier.get("groupName", "")=="Garlic Crust":
                if modifier.get("shopProductGroupSkuList", [])[0].get("spuName") == "With Garlic Oil On The Crust": result["is_garlic_crust"] = True

            if modifier.get("groupName", "") == "Dough Type":
                if modifier.get("shopProductGroupSkuList", [])[0].get("spuName") == "Thin": result[
                    "is_thin_dough"] = True

            if modifier.get("groupName", "") == "Better Together":
                items = modifier.get("shopProductGroupSkuList", [])
                for item in items:
                    item_name = item.get("spuName")
                    price = item.get("price")/1000
                    order_item = {
                        'name': item_name,
                        'amount': price,
                        'quantity': item.get("count"),
                        'is_garlic_crust': False,
                        "is_thin_dough": False,
                        'category': "Sauces"
                    }
                    result["order_items"].append(order_item)

            if "Modifiers" in modifier.get("groupName", ""):
                if modifier.get("shopProductGroupSkuList", [])[0] is not None:
                    pizza_modifiers = modifier.get("shopProductGroupSkuList", [])
                    for pizza_modifier in pizza_modifiers:
                        name = pizza_modifier.get("spuName")
                        count = pizza_modifier.get("count")
                        result["description_parts"].append(f"{name} x{count}")
        else:
            if modifier.get("groupName", "")=="Choose Your Pizza":
                if modifier.get("shopProductGroupSkuList", [])[0] is not None:
                    pizza = modifier.get("shopProductGroupSkuList", {})[0]
                    new_combo_item = {
                        "item_name": pizza.get("spuName"),
                        'quantity': pizza.get("count"),
                        'category': "Pizzas",
                        'size': size,
                        'is_thin_dough': False,
                        "is_garlic_crust": False,
                    }
                    result["combo_items"].append(new_combo_item)

            if modifier.get("groupName", "")=="Choose Your Beverage":
                if modifier.get("shopProductGroupSkuList", [])[0] is not None:
                    beverage = modifier.get("shopProductGroupSkuList", {})[0]
                    new_combo_item = {
                        "item_name": beverage.get("spuName"),
                        'quantity': beverage.get("count"),
                        'category': "Beverages"
                    }
                    result["combo_items"].append(new_combo_item)

            if modifier.get("groupName", "")=="Choose Your Sauce":
                if modifier.get("shopProductGroupSkuList", [])[0] is not None:
                    sauce = modifier.get("shopProductGroupSkuList", [])[0]
                    new_combo_item = {
                        "item_name": sauce.get("spuName"),
                        'quantity': sauce.get("count"),
                        'category': "Sauces",
                        'size': None
                    }
                    result["combo_items"].append(new_combo_item)

            if modifier.get("groupName", "")=="Choose Your Detroit Pizza":
                if modifier.get("shopProductGroupSkuList", [])[0] is not None:
                    detroit_pizza = modifier.get("shopProductGroupSkuList", [])[0]
                    new_combo_item = {
                        "item_name": detroit_pizza.get("spuName"),
                        'quantity': detroit_pizza.get("count"),
                        'category': "Brick Pizzas"
                    }
                    result["combo_items"].append(new_combo_item)


            if "Modifiers" in modifier.get("groupName", ""):
                if modifier.get("shopProductGroupSkuList", [])[0] is not None:
                    pizza_modifiers = modifier.get("shopProductGroupSkuList", [])
                    for pizza_modifier in pizza_modifiers:
                        name = pizza_modifier.get("spuName")
                        count = pizza_modifier.get("count")
                        result["description_parts"].append(f"{name} x{count}")

            if modifier.get("groupName", "") == "Garlic Crust":
                if modifier.get("shopProductGroupSkuList", [])[0].get("spuName") == "With Garlic Oil On The Crust":
                    for item in result["combo_items"]:
                        if item["category"] == "Pizzas":
                            item["is_garlic_crust"] = True

            if modifier.get("groupName", "") == "Dough Type":
                if modifier.get("shopProductGroupSkuList", [])[0].get("spuName") == "Thin":
                    for item in result["combo_items"]:
                        if item["category"] == "Pizzas":
                            item["is_thin_dough"] = True

            for item in result["combo_items"]:
                if item["category"] == "Pizzas":
                    item["description"] = result.get("description", '')


    if not is_combo:
        if result["is_thin_dough"]:
            result["description_parts"].append("Thin")
        if result["is_garlic_crust"]:
            result["description_parts"].append("Garlic")

        result["description"] = ", ".join(result["description_parts"])

    else:
        base_modifiers_str = ", ".join(result["description_parts"])

        for item in result["combo_items"]:
            if item["category"] in ["Pizzas", "Brick Pizzas"]:
                parts = []
                if base_modifiers_str:
                    parts.append(base_modifiers_str)

                if item.get("is_thin_dough"):
                    parts.append("Thin")
                if item.get("is_garlic_crust"):
                    parts.append("Garlic")

                item["description"] = ", ".join(parts)

        result["description"] = base_modifiers_str

    del result["description_parts"]
    return result

def parse_orders(orders):
    if len(orders) == 0:
        return None

    for order in orders:
        base_order = order.get("baseOrder", {})
        order_id = str(base_order.get("orderViewId"))
        status = base_order.get("status", {})
        branch_name = order.get("merchantOrder", {}).get("shopName", "")
        parse_order(order, order_id, status, branch_name)


def parse_order(order, order_id, status, branch_name):
    base_order = order.get("baseOrder", {})

    ctime = base_order.get("ctime")

    if ctime:
        current_time_ms = int(time.time() * 1000)
        is_old = (current_time_ms - ctime) > (3 * 60 * 1000)
        is_cancelled = (status == 50)

        if is_old and not is_cancelled:
            print(f"⏩ Пропуск заказа {order_id} (Старый, создан: {get_bahrain_time(ctime)})")
            return
    else:
        print(f"⚠️ У заказа {order_id} нет поля ctime, пропускаем фильтр.")
    order_items = order.get("products", [])
    client_info = order.get("recipientInfo", {})
    total_price = order.get("feeDtl", {}).get("merchantFee", {}).get("productPrice")/1000
    branch_id = ""
    if "Hidd" in branch_name: branch_id = AVAILABLE_BRANCHES.get("Hidd")
    parsed_order_items = parse_order_items(order_items)

    parsed_order = {
        'orderId': order_id,
        'orderItems': parsed_order_items,
        'address': client_info.get("addressName", "")+ client_info.get("houseNumber", ""),
        'telephoneNo': client_info.get("interCode")+client_info.get("phone"),
        'name': client_info.get("name", ""),
        'amountPaid': total_price,
        'timestamp': get_bahrain_time(ctime),
        'status': status,
        'description': base_order.get("remark", ""),
        'branchId': branch_id,
        "paymentType": base_order.get("payTypeDesc"),
    }
    response = requests.post(BACKEND_URL, json=parsed_order)
    print(response.status_code)


def get_bahrain_time(timestamp):
    dt_utc = datetime.fromtimestamp(timestamp/1000, tz=timezone.utc)

    bahrain_tz = timezone(timedelta(hours=3))

    dt_bahrain = dt_utc.astimezone(bahrain_tz)
    return dt_bahrain.strftime('%Y-%m-%dT%H:%M:%S')


def parse_order_items(raw_items):
    parsed_items = []

    for item in raw_items:
        raw_name = item.get("name", "")
        raw_spec = item.get("groups", [])

        quantity = item.get("count", 1)
        price = float(item.get("price", 0))

        full_raw_name = f"{raw_name}"

        db_name, category, db_size = MenuMatcher.match_item(full_raw_name)

        is_combo= False

        if category == "Combo Deals": is_combo = True

        if db_name == "Unknown":
            db_name = raw_name

        parsed_opts = parse_options(raw_spec, is_combo, db_size)

        remark = item.get("remark", "").strip()
        description = parsed_opts["description"]

        full_description_str = ", ".join(filter(None, [remark, description]))
        order_item = {
            "name": db_name,
            "size": db_size,
            "quantity": quantity,
            "amount": price,
            "category": category,
            "is_garlic_crust": parsed_opts["is_garlic_crust"],
            "is_thin_dough": parsed_opts["is_thin_dough"],
            "description": full_description_str,
            "combo_items": parsed_opts.get("combo_items", []),
        }

        parsed_items.append(order_item)

        if parsed_opts.get("order_items", []) :
            parsed_items.extend(parsed_opts["order_items"])


    return parsed_items

def processed_ids():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())


def save_new_id(order_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{order_id}\n")

def run_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'])

        try:
            context = browser.new_context(
                storage_state=AUTH_FILE,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
        except Exception as e:
            print(f"❌ Ошибка чтения файла авторизации: {e}")
            print("Попробуйте удалить auth.json и пройти авторизацию заново.")
            browser.close()
            return

        page = context.new_page()

        print("Opening a new page...")

        final_data = {}

        def handle_response(response):
            if "api/order/history/getOrders" in response.url and response.status == 200:
                print("🎯 Поймали ответ API!")
                try:
                    data = response.json()
                    final_data["orders"] = data.get("data", {}).get("list", [])
                    print(f"📦 Получено {len(final_data['orders'])} заказов из перехвата.")
                except Exception as e:
                    print(f"Ошибка парсинга JSON: {e}")

        page.on("response", handle_response)

        page.goto(
            PAGE_URL
        )

        page.wait_for_timeout(25000)

        print(f"📍 Текущий URL: {page.url}")
        print(f"📄 Заголовок: {page.title()}")

        orders = final_data.get("orders", [])

        browser.close()

        try:
            parse_orders(orders)
        except Exception as e:
            print(f"Unfortunately an exception has dropped: {e}")


def is_shop_open():
    bahrain_tz = timezone(timedelta(hours=3))
    now = datetime.now(bahrain_tz)

    day_of_week = now.weekday()


    today_schedule = WEEKLY_SCHEDULE.get(day_of_week, [10, 2])

    open_hour = today_schedule[0]
    close_hour = today_schedule[1]

    current_hour = now.hour

    if open_hour < close_hour:
        is_open = open_hour <= current_hour < close_hour

    else:
        is_open = current_hour >= open_hour or current_hour < close_hour

    if not is_open:
        print(
            f"🕒 Сейчас {now.strftime('%H:%M')} (День {day_of_week}). График на сегодня: {open_hour}:00 - {close_hour}:00")

    return is_open


def run_scraper_loop():
    print("🚀 СТАРТ СКРАПЕРА")

    if "AUTH_JSON_CONTENT" in os.environ:
        print("🔑 Восстанавливаем auth.json...")
        with open(AUTH_FILE, "w", encoding='utf-8') as f:
            f.write(os.environ["AUTH_JSON_CONTENT"])

    time.sleep(2)

    while True:
        try:
            if is_shop_open():
                run_browser()

                print("⏳ Ждем 60 секунд...")
                time.sleep(40)
            else:
                print("CLosed")
                time.sleep(40)

        except Exception as e:
            print(f"🔥 Глобальная ошибка цикла: {e}")
            time.sleep(10)

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "alive", "service": "keeta-scraper"}

@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=run_scraper_loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

