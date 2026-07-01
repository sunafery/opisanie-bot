import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
import re
import os
import base64
import json
import time
from datetime import datetime, timedelta
from groq import Groq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CARD_NUMBER = os.environ.get("CARD_NUMBER")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

OWNER_ID = 1249820876
OWNER_USERNAME = "sunafery"
BOT_USERNAME = "opisanie_marketbot"
FREE_LIMIT = 3
STARS_PRICE = 150
REFERRAL_BONUS = 2

# === Сохранение данных ===
DATA_FILE = "user_data.json"
last_request_time = {}  # Анти-флуд

def load_user_data():
    global user_free_left
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                user_free_left = {int(k): v for k, v in data.get("free_left", {}).items()}
        except Exception:
            user_free_left = {}
    else:
        user_free_left = {}

def save_user_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"free_left": user_free_left}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

load_user_data()

user_history = {}
pro_users = {}
user_settings = {}
user_text_history = {}
referred_by = {}
all_users = set()

MODELS = {
    "smart": "llama-3.3-70b-versatile",
    "fast": "llama-3.1-8b-instant"
}
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

WELCOME_TEXT = ("👋 Добро пожаловать!\n\n"
    "Marketplace Description Bot — ваш надёжный помощник в создании продающих описаний для маркетплейсов.\n\n"
    "Мы создаём тексты, которые не только привлекают внимание покупателей, но и помогают карточкам товара выглядеть профессионально.\n\n"
    "🎁 У тебя есть 3 бесплатных запросов. После их использования потребуется подписка.")

MENU_MAIN_TEXT = "📋 Главное меню\n\nВыбери раздел или просто напиши название товара:"

def get_balance_text(uid):
    if is_unlimited(uid):
        return "♾️ У тебя безлимитная подписка"
    remaining = user_free_left.get(uid, 0)
    return f"🔸 Осталось бесплатных запросов: {remaining}"

def get_sub_text():
    return ("💳 Подписка\n\n"
        "Снимает лимит на количество запросов и даёт постоянный доступ ко всем функциям.\n\n"
        "Способы оплаты:\n\n"
        "⭐ Telegram Stars — мгновенно, активируется автоматически. Нажми кнопку ниже.\n\n"
        "💳 Перевод на карту (160 ₽ + отзыв) — переведи 160 ₽ на карту " + CARD_NUMBER + ", оставь короткий отзыв о боте и пришли скриншот перевода вместе с командой /myid. Активирую вручную в течение часа.")

SETTINGS_MAIN_TEXT = "⚙️ Настройки\n\nВыбери, что хочешь изменить:"

MODEL_LABELS = {"smart": "Умная (точнее)", "fast": "Быстрая (быстрее)"}
PLATFORM_LABELS = {"auto": "Автоматически", "ozonwb": "Wildberries / Ozon", "avito": "Avito"}
TONE_LABELS = {"auto": "Автоматически", "casual": "Неформальный", "formal": "Официальный"}
LENGTH_LABELS = {"auto": "Автоматически", "short": "Краткое описание", "long": "Подробное описание"}

def get_settings(uid):
    if uid not in user_settings:
        user_settings[uid] = {"model": "smart", "platform": "auto", "tone": "auto", "length": "auto"}
    return user_settings[uid]

def clean_text(text):
    return re.sub(r'[\u3040-\u30ff\uac00-\ud7af]', '', text)

def is_unlimited(uid):
    if uid == OWNER_ID:
        return True
    expiry = pro_users.get(uid)
    return expiry is not None and expiry > datetime.now()

def add_to_text_history(uid, text):
    if uid not in user_text_history:
        user_text_history[uid] = []
    user_text_history[uid].append(text)
    if len(user_text_history[uid]) > 5:
        user_text_history[uid].pop(0)

def build_system_prompt(settings_):
    platform_pref = settings_.get("platform", "auto")
    tone_pref = settings_.get("tone", "auto")
    length_pref = settings_.get("length", "auto")
    platform_line = ""
    if platform_pref == "avito":
        platform_line = "По умолчанию формат Avito: короче, проще, как от частного продавца, 5-7 предложений."
    elif platform_pref == "ozonwb":
        platform_line = "По умолчанию формат карточки Wildberries/Ozon: развёрнуто, 8-12 предложений, с блоком Характеристики."
    tone_line = ""
    if tone_pref == "formal":
        tone_line = "Используй официальный, деловой тон."
    elif tone_pref == "casual":
        tone_line = "Используй неформальный, дружелюбный тон."
    length_line = ""
    if length_pref == "short":
        length_line = "Отвечай кратко и по делу."
    elif length_pref == "long":
        length_line = "Давай развёрнутые, подробные ответы."
    return ("Ты дружелюбный и грамотный ИИ-помощник в Telegram. Можешь поддержать разговор на любую тему.\n\n"
            "У тебя есть сильная специализация: профессиональный копирайтер маркетплейсов и эксперт в моде, кроссовках, брендах, технике.\n\n"
            "Правила:\n"
            "- Если товар известная модель, используй реальные знания: материалы, технологии, историю, особенности\n"
            "- Если в подписи или сообщении явно указан бренд или модель, доверяй этому полностью, не переопределяй визуальной догадкой\n"
            "- Не выдумывай факты, в которых не уверен\n"
            "- Карточка WB/Ozon: 8-12 предложений, вступление, особенности, блок Характеристики, призыв к действию\n"
            "- Avito: 5-7 предложений, проще, как от частного продавца\n"
            "- По запросу характеристик — компактный список: бренд, модель, материалы, технологии, применение\n"
            "- Если просят перевести текст, переводи точно\n"
            + platform_line + " " + tone_line + " " + length_line + "\n\n"
            "- Пиши только на русском языке, грамотно, живым языком, без канцелярита\n"
            "- Никогда не используй иероглифы и символы других алфавитов\n"
            "- Используй контекст диалога, если просят переписать или изменить предыдущий текст\n"
            "- Не добавляй шаблонные фразы с предложением переписать текст, если не просили\n"
            "- Веди себя естественно, как живой умный собеседник")

def get_user_state(uid):
    if uid not in user_history:
        user_history[uid] = []
    return user_history[uid]

def build_main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("ℹ️ О боте", callback_data="menu_about"),
        InlineKeyboardButton("💳 Подписка", callback_data="menu_subscription"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
        InlineKeyboardButton("🔸 Мои запросы", callback_data="show_balance"),
        InlineKeyboardButton("🛠️ Поддержка", callback_data="menu_support")
    )
    return markup

def build_about_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    return markup

def build_support_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✉️ Написать в поддержку", url="https://t.me/" + OWNER_USERNAME))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    return markup

def build_sub_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("⭐ Оплатить Telegram Stars", callback_data="pay_stars"),
        InlineKeyboardButton("⬅️ Назад", callback_data="menu_main")
    )
    return markup

def build_settings_main_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🤖 Модель ИИ  >", callback_data="set_open_model"),
        InlineKeyboardButton("🛍️ Маркетплейс  >", callback_data="set_open_platform"),
        InlineKeyboardButton("✍️ Стиль текста  >", callback_data="set_open_tone"),
        InlineKeyboardButton("📄 Длина описания  >", callback_data="set_open_length"),
        InlineKeyboardButton("🔄 Сбросить настройки", callback_data="set_reset"),
        InlineKeyboardButton("⬅️ Назад", callback_data="menu_main")
    )
    return markup

def build_model_markup(s):
    options = [
        ("smart", "Умная (точнее)"),
        ("fast", "⚡ Быстрая (быстрее)")
    ]
    options.sort(key=lambda x: 0 if x[0] == s["model"] else 1)
    markup = InlineKeyboardMarkup(row_width=1)
    for key, label in options:
        prefix = "✅ " if s["model"] == key else ""
        markup.add(InlineKeyboardButton(prefix + label, callback_data="set_model_" + key))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_settings"))
    return markup

def build_platform_markup(s):
    options = [
        ("auto", "🤖 Автоматически"),
        ("ozonwb", "🟣 Wildberries / Ozon"),
        ("avito", "🟡 Avito")
    ]
    options.sort(key=lambda x: 0 if x[0] == s["platform"] else 1)
    markup = InlineKeyboardMarkup(row_width=1)
    for key, label in options:
        prefix = "✅ " if s["platform"] == key else ""
        markup.add(InlineKeyboardButton(prefix + label, callback_data="set_platform_" + key))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_settings"))
    return markup

def build_tone_markup(s):
    options = [
        ("auto", "🤖 Автоматически"),
        ("casual", "😎 Неформальный"),
        ("formal", "🎩 Официальный")
    ]
    options.sort(key=lambda x: 0 if x[0] == s["tone"] else 1)
    markup = InlineKeyboardMarkup(row_width=1)
    for key, label in options:
        prefix = "✅ " if s["tone"] == key else ""
        markup.add(InlineKeyboardButton(prefix + label, callback_data="set_tone_" + key))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_settings"))
    return markup

def build_length_markup(s):
    options = [
        ("auto", "🤖 Автоматически"),
        ("short", "📌 Краткое описание"),
        ("long", "📝 Подробное описание")
    ]
    options.sort(key=lambda x: 0 if x[0] == s["length"] else 1)
    markup = InlineKeyboardMarkup(row_width=1)
    for key, label in options:
        prefix = "✅ " if s["length"] == key else ""
        markup.add(InlineKeyboardButton(prefix + label, callback_data="set_length_" + key))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_settings"))
    return markup

DEFAULT_COMMANDS = [
    BotCommand("start", "Начать сначала"),
    BotCommand("menu", "Главное меню"),
    BotCommand("new", "Новый разговор"),
    BotCommand("settings", "Настройки"),
    BotCommand("history", "Последние описания"),
    BotCommand("referral", "Пригласить друга"),
    BotCommand("subscription", "Подписка"),
    BotCommand("support", "Поддержка"),
    BotCommand("myid", "Мой Telegram ID"),
    BotCommand("balance", "Мои запросы")
]

OWNER_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand("activate", "Включить Подписку"),
    BotCommand("deactivate", "Отключить Подписку"),
    BotCommand("stats", "Статистика")
]

try:
    bot.set_my_commands(commands=DEFAULT_COMMANDS, scope=BotCommandScopeDefault())
    bot.set_my_commands(commands=OWNER_COMMANDS, scope=BotCommandScopeChat(OWNER_ID))
except Exception:
    pass

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    user_history[uid] = []
    all_users.add(uid)
    parts = message.text.split()
    if len(parts) > 1 and parts[1].startswith("ref_") and uid not in referred_by:
        try:
            referrer_id = int(parts[1].replace("ref_", ""))
            if referrer_id != uid:
                referred_by[uid] = referrer_id
                user_free_left[referrer_id] = user_free_left.get(referrer_id, FREE_LIMIT) + REFERRAL_BONUS
                save_user_data()
                try:
                    bot.send_message(referrer_id, "По твоей ссылке пришёл новый пользователь! Тебе начислено +" + str(REFERRAL_BONUS) + " запроса.")
                except Exception:
                    pass
        except ValueError:
            pass

    if uid == OWNER_ID:
        bot.reply_to(message, "Привет, создатель! Безлимит активен. Доступны /activate, /deactivate и /stats.")
        return

    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT
        save_user_data()

    bot.reply_to(message, WELCOME_TEXT)
    bot.send_message(message.chat.id, MENU_MAIN_TEXT + "\n\n" + get_balance_text(uid), reply_markup=build_main_menu_markup())

    try:
        bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeChat(uid))
    except Exception:
        pass

@bot.message_handler(commands=['menu'])
def menu_command(message):
    bot.reply_to(message, MENU_MAIN_TEXT + "\n\n" + get_balance_text(message.from_user.id), reply_markup=build_main_menu_markup())

@bot.message_handler(commands=['balance'])
def balance_command(message):
    bot.reply_to(message, get_balance_text(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def main_menu_callback(call):
    uid = call.from_user.id
    action = call.data.replace("menu_", "")
    bot.answer_callback_query(call.id)

    if action == "main":
        safe_edit(call, MENU_MAIN_TEXT + "\n\n" + get_balance_text(uid), build_main_menu_markup())
    elif action == "about":
        safe_edit(call, MENU_ABOUT_TEXT, build_about_markup())
    elif action == "support":
        safe_edit(call, MENU_SUPPORT_TEXT, build_support_markup())
    elif action == "subscription":
        safe_edit(call, get_sub_text(), build_sub_markup())
    elif action == "settings":
        safe_edit(call, SETTINGS_MAIN_TEXT, build_settings_main_markup())

@bot.callback_query_handler(func=lambda call: call.data == "show_balance")
def show_balance(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    safe_edit(call, get_balance_text(uid) + "\n\nНажми /menu чтобы вернуться", build_main_menu_markup())

def safe_edit(call, text, markup):
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    all_users.add(uid)

    if uid in last_request_time and time.time() - last_request_time[uid] < 3:
        bot.reply_to(message, "⏳ Подожди 3 секунды перед следующим запросом.")
        return
    last_request_time[uid] = time.time()

    if not is_unlimited(uid):
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "🛑 Бесплатные запросы закончились.\n\nНапиши /subscription для оформления подписки.")
            return

    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        b64_image = base64.b64encode(downloaded).decode('utf-8')
        caption = message.caption if message.caption else "Опиши этот товар как продающее описание для маркетплейса."
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": "Ты эксперт по товарам и копирайтер маркетплейсов. Внимательно рассмотри фото. Если в подписи пользователя явно указан бренд или модель, доверяй этому полностью и не переопределяй визуальной догадкой. Напиши продающее описание на русском языке, 5-8 предложений, естественным языком, без канцелярита."},
                {"role": "user", "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64_image}}
                ]}
            ],
            max_tokens=600
        )
        text = clean_text(response.choices[0].message.content)
        add_to_text_history(uid, text)
        
        if not is_unlimited(uid):
            user_free_left[uid] -= 1
            save_user_data()
            remaining = user_free_left[uid]
            if remaining > 0:
                bot.reply_to(message, f"🔸 Осталось бесплатных запросов: {remaining}")
            else:
                bot.reply_to(message, "🛑 Бесплатные запросы закончились.\n\nНапиши /subscription для оформления подписки.")
        
        bot.reply_to(message, text)
    except Exception:
        bot.reply_to(message, "Не получилось распознать фото, попробуй ещё раз или опиши товар текстом.")

@bot.message_handler(func=lambda m: True)
def generate(message):
    uid = message.from_user.id
    all_users.add(uid)

    # Исключаем команды
    if message.text and message.text.startswith('/'):
        return

    if uid in last_request_time and time.time() - last_request_time[uid] < 3:
        bot.reply_to(message, "⏳ Подожди 3 секунды перед следующим запросом.")
        return
    last_request_time[uid] = time.time()

    if not is_unlimited(uid):
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "🛑 Бесплатные запросы закончились.\n\nНапиши /subscription для оформления подписки.")
            return

    bot.send_chat_action(message.chat.id, 'typing')

    history = get_user_state(uid)
    settings_ = get_settings(uid)

    if len(history) == 0:
        history.append({"role": "system", "content": build_system_prompt(settings_)})

    history.append({"role": "user", "content": message.text})
    trimmed = [history[0]] + history[-11:] if len(history) > 12 else history
    model_name = MODELS.get(settings_.get("model", "smart"), MODELS["smart"])

    try:
        response = client.chat.completions.create(model=model_name, messages=trimmed, max_tokens=700, temperature=0.8)
        text_response = clean_text(response.choices[0].message.content)
        history.append({"role": "assistant", "content": text_response})
        add_to_text_history(uid, text_response)
        
        if not is_unlimited(uid):
            user_free_left[uid] -= 1
            save_user_data()
            remaining = user_free_left[uid]
            if remaining > 0:
                bot.reply_to(message, f"{text_response}\n\n🔸 Осталось бесплатных запросов: {remaining}")
            else:
                bot.reply_to(message, f"{text_response}\n\n🛑 Бесплатные запросы закончились.\n\nНапиши /subscription для оформления подписки.")
        else:
            bot.reply_to(message, text_response)
    except Exception:
        bot.reply_to(message, "Произошла ошибка, попробуй ещё раз через минуту.")

print("Бот запущен и работает...")
bot.polling(none_stop=True)
