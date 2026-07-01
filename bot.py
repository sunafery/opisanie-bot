import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
import re
import os
import base64
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

user_free_left = {}
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

MENU_ABOUT_TEXT = ("ℹ️ О боте\n\n"
    "Marketplace Description Bot создан, чтобы продавцам не приходилось тратить часы на написание описаний — одна фраза с названием товара, и через 10 секунд готов живой убедительный текст.\n\n"
    "Что умею:\n"
    "🛍️ Описания для Avito, Wildberries и Ozon\n"
    "📷 Распознавание товара по фото\n"
    "✏️ Редактирование прямо в диалоге\n"
    "🎯 Разбор брендов, моделей, материалов и технологий\n\n"
    "Просто напиши название товара — начнём.")

MENU_SUPPORT_TEXT = "🛠️ Поддержка\n\nЧто-то пошло не так или есть идея как улучшить бота?\nНажми кнопку ниже — ответим быстро."

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
    BotCommand("myid", "Мой Telegram ID")
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

    bot.reply_to(message, WELCOME_TEXT)
    bot.send_message(message.chat.id, MENU_MAIN_TEXT, reply_markup=build_main_menu_markup())

@bot.message_handler(commands=['menu'])
def menu_command(message):
    bot.reply_to(message, MENU_MAIN_TEXT, reply_markup=build_main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def main_menu_callback(call):
    uid = call.from_user.id
    action = call.data.replace("menu_", "")
    bot.answer_callback_query(call.id)

    if action == "main":
        safe_edit(call, MENU_MAIN_TEXT, build_main_menu_markup())
    elif action == "about":
        safe_edit(call, MENU_ABOUT_TEXT, build_about_markup())
    elif action == "support":
        safe_edit(call, MENU_SUPPORT_TEXT, build_support_markup())
    elif action == "subscription":
        safe_edit(call, get_sub_text(), build_sub_markup())
    elif action == "settings":
        safe_edit(call, SETTINGS_MAIN_TEXT, build_settings_main_markup())

def safe_edit(call, text, markup):
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_open_") or call.data == "set_reset")
def settings_open_callback(call):
    uid = call.from_user.id
    s = get_settings(uid)
    bot.answer_callback_query(call.id)

    if call.data == "set_reset":
        user_settings[uid] = {"model": "smart", "platform": "auto", "tone": "auto", "length": "auto"}
        bot.answer_callback_query(call.id, "Настройки сброшены")
        safe_edit(call, SETTINGS_MAIN_TEXT, build_settings_main_markup())
        return

    section = call.data.replace("set_open_", "")
    if section == "model":
        safe_edit(call, "🤖 Выберите модель", build_model_markup(s))
    elif section == "platform":
        safe_edit(call, "🛍️ Выберите площадку", build_platform_markup(s))
    elif section == "tone":
        safe_edit(call, "✍️ Выберите стиль", build_tone_markup(s))
    elif section == "length":
        safe_edit(call, "📄 Выберите длину", build_length_markup(s))

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_model_") or call.data.startswith("set_platform_") or call.data.startswith("set_tone_") or call.data.startswith("set_length_"))
def settings_value_callback(call):
    uid = call.from_user.id
    s = get_settings(uid)
    data = call.data

    if data.startswith("set_model_"):
        s["model"] = data.replace("set_model_", "")
        bot.answer_callback_query(call.id, "Обновлено")
        safe_edit(call, "🤖 Выберите модель", build_model_markup(s))
    elif data.startswith("set_platform_"):
        s["platform"] = data.replace("set_platform_", "")
        bot.answer_callback_query(call.id, "Обновлено")
        safe_edit(call, "🛍️ Выберите площадку", build_platform_markup(s))
    elif data.startswith("set_tone_"):
        s["tone"] = data.replace("set_tone_", "")
        bot.answer_callback_query(call.id, "Обновлено")
        safe_edit(call, "✍️ Выберите стиль", build_tone_markup(s))
    elif data.startswith("set_length_"):
        s["length"] = data.replace("set_length_", "")
        bot.answer_callback_query(call.id, "Обновлено")
        safe_edit(call, "📄 Выберите длину", build_length_markup(s))

@bot.message_handler(commands=['new'])
def new_topic(message):
    uid = message.from_user.id
    user_history[uid] = []
    bot.reply_to(message, "🔄 Начинаем с чистого листа.\n\nПредыдущий контекст сброшен — бот забыл прошлый товар и все правки к нему. Это полезно, если переходишь к описанию совсем другой вещи, чтобы детали не смешивались.\n\nПросто напиши название нового товара и детали, или пришли фото — начнём заново.")

@bot.message_handler(commands=['support'])
def support_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✉️ Написать в поддержку", url="https://t.me/" + OWNER_USERNAME))
    bot.reply_to(message, MENU_SUPPORT_TEXT, reply_markup=markup)

@bot.message_handler(commands=['referral'])
def referral_command(message):
    uid = message.from_user.id
    link = "https://t.me/" + BOT_USERNAME + "?start=ref_" + str(uid)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 Поделиться ссылкой", switch_inline_query=link))
    bot.reply_to(message, "🎁 Приглашай друзей и получай бонусные запросы!\n\nЗа каждого, кто перейдёт по твоей ссылке и запустит бота, тебе начислится +" + str(REFERRAL_BONUS) + " бесплатных запроса.", reply_markup=markup)

@bot.message_handler(commands=['history'])
def history_command(message):
    uid = message.from_user.id
    items = user_text_history.get(uid, [])
    if not items:
        bot.reply_to(message, "Пока нет сохранённых описаний. Сгенерируй первое!")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for i, item in enumerate(items):
        preview = item.replace("\n", " ")[:45]
        markup.add(InlineKeyboardButton(str(i + 1) + ") " + preview + "...", callback_data="hist_" + str(i)))
    bot.reply_to(message, "📜 Последние описания. Нажми чтобы вернуться и продолжить редактировать:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("hist_"))
def history_callback(call):
    uid = call.from_user.id
    idx = int(call.data.replace("hist_", ""))
    items = user_text_history.get(uid, [])
    if idx >= len(items):
        bot.answer_callback_query(call.id, "Не найдено")
        return
    selected_text = items[idx]
    settings_ = get_settings(uid)
    user_history[uid] = [
        {"role": "system", "content": build_system_prompt(settings_)},
        {"role": "assistant", "content": selected_text}
    ]
    bot.answer_callback_query(call.id, "Загружено")
    bot.send_message(call.message.chat.id, "Вернулся к этому описанию. Можно продолжать редактировать:\n\n" + selected_text)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != OWNER_ID:
        return
    active_subs = sum(1 for uid, exp in pro_users.items() if exp > datetime.now())
    bot.reply_to(message, "📊 Статистика:\n\nПользователей всего: " + str(len(all_users)) + "\nАктивных подписок: " + str(active_subs) + "\nПришло по рефералке: " + str(len(referred_by)))

@bot.message_handler(commands=['settings'])
def settings_command(message):
    bot.reply_to(message, SETTINGS_MAIN_TEXT, reply_markup=build_settings_main_markup())

@bot.message_handler(commands=['subscription'])
def subscription_command(message):
    bot.reply_to(message, get_sub_text(), reply_markup=build_sub_markup())

@bot.callback_query_handler(func=lambda call: call.data == "pay_stars")
def buy_stars(call):
    prices = [LabeledPrice(label="Подписка на 1 месяц", amount=STARS_PRICE)]
    bot.send_invoice(call.message.chat.id, title="Подписка — безлимит", description="Безлимитные описания товаров на 1 месяц", invoice_payload="subscription_1_month", provider_token="", currency="XTR", prices=prices)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = message.from_user.id
    expiry = datetime.now() + timedelta(days=30)
    pro_users[uid] = expiry
    bot.reply_to(message, "✅ Оплата прошла! Подписка активна до " + expiry.strftime("%d.%m.%Y") + ".")

@bot.message_handler(commands=['myid'])
def myid(message):
    bot.reply_to(message, "Твой Telegram ID: " + str(message.from_user.id) + "\n\nЕсли оплачивал переводом на карту, пришли этот номер мне.")

@bot.message_handler(commands=['activate'])
def activate(message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        parts = message.text.split()
        target_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
        expiry = datetime.now() + timedelta(days=days)
        pro_users[target_id] = expiry
        expiry_str = expiry.strftime("%d.%m.%Y")
        bot.reply_to(message, "Готово. Подписка пользователя " + str(target_id) + " активна до " + expiry_str + ".")
        try:
            bot.send_message(target_id, "Твоя Подписка активирована и действует до " + expiry_str + ". Спасибо за поддержку!")
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "Используй: /activate 123456789 30")

@bot.message_handler(commands=['deactivate'])
def deactivate(message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        pro_users.pop(target_id, None)
        bot.reply_to(message, "Подписка пользователя " + str(target_id) + " деактивирована.")
        try:
            bot.send_message(target_id, "Твоя Подписка была деактивирована.")
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "Используй: /deactivate 123456789")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    all_users.add(uid)
    if not is_unlimited(uid):
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "Бесплатные запросы закончились. Напиши /subscription.")
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
        bot.reply_to(message, text)
    except Exception:
        bot.reply_to(message, "Не получилось распознать фото, попробуй ещё раз или опиши товар текстом.")

@bot.message_handler(func=lambda m: True)
def generate(message):
    uid = message.from_user.id
    all_users.add(uid)
    history = get_user_state(uid)
    settings_ = get_settings(uid)
    is_new_topic = len(history) == 0
    if not is_unlimited(uid) and is_new_topic:
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "Бесплатные запросы закончились. Напиши /subscription.")
            return
    bot.send_chat_action(message.chat.id, 'typing')
    if is_new_topic:
        history.append({"role": "system", "content": build_system_prompt(settings_)})
    history.append({"role": "user", "content": message.text})
    trimmed = [history[0]] + history[-11:] if len(history) > 12 else history
    model_name = MODELS.get(settings_.get("model", "smart"), MODELS["smart"])
    try:
        response = client.chat.completions.create(model=model_name, messages=trimmed, max_tokens=700, temperature=0.8)
        text = clean_text(response.choices[0].message.content)
        history.append({"role": "assistant", "content": text})
        add_to_text_history(uid, text)
        if not is_unlimited(uid) and is_new_topic:
            user_free_left[uid] -= 1
        bot.reply_to(message, text)
    except Exception:
        bot.reply_to(message, "Произошла ошибка, попробуй ещё раз через минуту.")

print("Бот запущен и работает...")
bot.polling(none_stop=True)
