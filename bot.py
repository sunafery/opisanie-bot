import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
import random
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
user_language = {}
referred_by = {}
all_users = set()

MODELS = {
    "smart": "llama-3.3-70b-versatile",
    "fast": "llama-3.1-8b-instant"
}
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

LANGUAGES = {
    "ru": "Русский",
    "en": "English",
    "es": "Espanol",
    "de": "Deutsch",
    "fr": "Francais",
    "it": "Italiano",
    "pt": "Portugues",
    "tr": "Turkce",
    "zh": "Zhongwen",
    "ar": "Arabiya"
}

LANG_FLAGS = {
    "ru": "Русский",
    "en": "English",
    "es": "Espanol",
    "de": "Deutsch",
    "fr": "Francais",
    "it": "Italiano",
    "pt": "Portugues",
    "tr": "Turkce",
    "zh": "Zhongwen",
    "ar": "Arabiya"
}

WELCOME_TEXTS = {
    "ru": "Привет! Я ИИ-помощник, который пишет продающие описания товаров за секунды — для Avito, Wildberries и Ozon.\n\nЗнаю бренды, модели, материалы и технологии, поэтому описания получаются живые, а не шаблонные. Могу переписать, сократить, добавить характеристики или перевести текст прямо в диалоге. Понимаю и фото товара — просто пришли картинку.\n\nКак начать: напиши название товара и пару деталей. Например: Кроссовки Nike Air Max, белые, новые, размер 42",
    "en": "Hi! I am an AI assistant that writes selling product descriptions in seconds.\n\nI know brands, models, materials and technologies, so descriptions feel alive, not templated. I can rewrite, shorten, add specs or translate right in the chat. I also understand product photos, just send a picture.\n\nHow to start: send the product name and a few details. Example: Nike Air Max sneakers, white, new, size 42",
    "es": "Hola! Soy un asistente de IA que escribe descripciones de venta en segundos.\n\nConozco marcas, modelos, materiales y tecnologias. Puedo reescribir, acortar, anadir caracteristicas o traducir en el chat. Tambien entiendo fotos de productos.\n\nComo empezar: escribe el nombre del producto y algunos detalles.",
    "de": "Hallo! Ich bin ein KI-Assistent der in Sekunden verkaufsstarke Produktbeschreibungen schreibt.\n\nIch kenne Marken, Modelle, Materialien und Technologien. Ich kann umschreiben, kurzen, Merkmale hinzufugen oder ubersetzen. Ich verstehe auch Produktfotos.\n\nSo geht es: Schreib den Produktnamen und ein paar Details.",
    "fr": "Salut! Je suis un assistant IA qui redige des descriptions de produits convaincantes en quelques secondes.\n\nJe connais les marques, modeles, materiaux et technologies. Je peux reecrire, raccourcir, ajouter des caracteristiques ou traduire. Je comprends aussi les photos.\n\nPour commencer: ecris le nom du produit et quelques details.",
    "it": "Ciao! Sono un assistente IA che scrive descrizioni di vendita in pochi secondi.\n\nConosco marchi, modelli, materiali e tecnologie. Posso riscrivere, accorciare, aggiungere caratteristiche o tradurre. Capisco anche le foto dei prodotti.\n\nPer iniziare: scrivi il nome del prodotto e alcuni dettagli.",
    "pt": "Ola! Sou um assistente de IA que escreve descricoes de venda em segundos.\n\nConheco marcas, modelos, materiais e tecnologias. Posso reescrever, encurtar, adicionar caracteristicas ou traduzir. Tambem entendo fotos de produtos.\n\nPara comecar: escreva o nome do produto e alguns detalhes.",
    "tr": "Merhaba! Saniyeler icinde satis odakli urun aciklamalari yazan bir yapay zeka asistaniyim.\n\nMarkalari, modelleri, malzemeleri ve teknolojileri biliyorum. Yeniden yazabilir, kisaltabilir, ozellik ekleyebilir veya cevirebilirim. Urun fotograflarini da anliyorum.\n\nBaslamak icin: urun adini ve birkac detayi yaz.",
    "zh": "Hello! I am an AI assistant that writes product descriptions in seconds. I know brands, models and materials. I can rewrite, shorten, add specs or translate. I also understand product photos. To start: send the product name and details.",
    "ar": "Hello! I am an AI assistant that writes product descriptions in seconds. I know brands, models and materials. I can rewrite, shorten, add specs or translate. I also understand product photos. To start: send the product name and details."
}

def get_settings(uid):
    if uid not in user_settings:
        user_settings[uid] = {"model": "smart", "platform": "auto", "length": "auto", "tone": "auto"}
    return user_settings[uid]

def get_language(uid):
    return user_language.get(uid, "ru")

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

def build_system_prompt(settings_, lang_code):
    lang_name = LANGUAGES.get(lang_code, "Russian")
    platform_pref = settings_.get("platform", "auto")
    tone_pref = settings_.get("tone", "auto")
    length_pref = settings_.get("length", "auto")

    platform_line = ""
    if platform_pref == "avito":
        platform_line = "Default format: Avito style, shorter, personal, like a private seller, 5-7 sentences."
    elif platform_pref == "ozonwb":
        platform_line = "Default format: Wildberries/Ozon card, detailed 8-12 sentences, with a Characteristics block."

    tone_line = ""
    if tone_pref == "formal":
        tone_line = "Use a formal, professional tone in all responses."
    elif tone_pref == "casual":
        tone_line = "Use a casual, friendly, conversational tone in all responses."

    length_line = ""
    if length_pref == "short":
        length_line = "Keep responses concise and brief unless the user asks for more detail."
    elif length_pref == "long":
        length_line = "Provide detailed and thorough responses by default."

    return ("You are a friendly and articulate AI assistant in Telegram. You can hold a conversation on any topic.\n\n"
            "You also have a strong specialty: professional marketplace copywriter and expert in fashion, sneakers, brands, electronics and products.\n\n"
            "Product description rules:\n"
            "- If the product is a known model, use your real knowledge: materials, technology, history, features\n"
            "- If the user caption or message explicitly states a brand or model name, always trust that stated information over any visual guess from an image\n"
            "- Do not invent facts you are not sure about\n"
            "- Wildberries/Ozon card: 8-12 sentences, intro, features, Characteristics block, call to action\n"
            "- Avito: 5-7 sentences, simpler, like a private seller\n"
            "- Characteristics request: compact list, brand, model, materials, tech, use case\n"
            "- If asked to translate, do it accurately and fluently\n"
            + platform_line + "\n"
            + tone_line + "\n"
            + length_line + "\n\n"
            "General rules:\n"
            "- Always respond in this language: " + lang_name + ", unless user explicitly asks to switch\n"
            "- Never use random foreign script characters outside the active language\n"
            "- Use conversation context when user asks to rewrite or edit previous text\n"
            "- Do not add template phrases offering to rewrite unless asked\n"
            "- Behave naturally like a smart real conversational partner")

def get_user_state(uid):
    if uid not in user_history:
        user_history[uid] = []
    return user_history[uid]

def build_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("О боте", callback_data="menu_about"),
        InlineKeyboardButton("Подписка", callback_data="menu_subscription"),
        InlineKeyboardButton("Настройки", callback_data="menu_settings"),
        InlineKeyboardButton("Поддержка", callback_data="menu_support")
    )
    return markup

def build_language_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(name, callback_data="lang_" + code) for code, name in LANGUAGES.items()]
    markup.add(*buttons)
    return markup

def build_settings_markup(s):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(("OK " if s["model"] == "smart" else "") + "Умная модель (точнее)", callback_data="model_smart"),
        InlineKeyboardButton(("OK " if s["model"] == "fast" else "") + "Быстрая модель (мгновенно)", callback_data="model_fast"),
        InlineKeyboardButton(("OK " if s["platform"] == "auto" else "") + "Площадка: Автоматически", callback_data="platform_auto"),
        InlineKeyboardButton(("OK " if s["platform"] == "avito" else "") + "Площадка: Avito", callback_data="platform_avito"),
        InlineKeyboardButton(("OK " if s["platform"] == "ozonwb" else "") + "Площадка: WB / Ozon", callback_data="platform_ozonwb"),
        InlineKeyboardButton(("OK " if s["tone"] == "auto" else "") + "Тон: Автоматически", callback_data="tone_auto"),
        InlineKeyboardButton(("OK " if s["tone"] == "casual" else "") + "Тон: Неформальный", callback_data="tone_casual"),
        InlineKeyboardButton(("OK " if s["tone"] == "formal" else "") + "Тон: Официальный", callback_data="tone_formal"),
        InlineKeyboardButton(("OK " if s["length"] == "auto" else "") + "Длина: Автоматически", callback_data="length_auto"),
        InlineKeyboardButton(("OK " if s["length"] == "short" else "") + "Длина: Короткий текст", callback_data="length_short"),
        InlineKeyboardButton(("OK " if s["length"] == "long" else "") + "Длина: Подробный текст", callback_data="length_long")
    )
    return markup

DEFAULT_COMMANDS = [
    BotCommand("start", "Начать сначала"),
    BotCommand("new", "Новый разговор"),
    BotCommand("menu", "Главное меню"),
    BotCommand("settings", "Настройки"),
    BotCommand("language", "Сменить язык"),
    BotCommand("history", "Последние описания"),
    BotCommand("referral", "Пригласить друга"),
    BotCommand("subscription", "Подписка"),
    BotCommand("about", "О нас"),
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
                    bot.send_message(referrer_id, "По твоей ссылке пришёл новый пользователь! Тебе начислено +" + str(REFERRAL_BONUS) + " бесплатных запроса.")
                except Exception:
                    pass
        except ValueError:
            pass

    if uid == OWNER_ID:
        bot.reply_to(message, "Привет, создатель! Безлимит активен.\n\nДоступны /activate, /deactivate и /stats.")
        return

    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT

    bot.reply_to(message, "Выбери язык / Choose your language:", reply_markup=build_language_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_callback(call):
    uid = call.from_user.id
    lang_code = call.data.replace("lang_", "")
    user_language[uid] = lang_code
    bot.answer_callback_query(call.id, "OK")
    welcome = WELCOME_TEXTS.get(lang_code, WELCOME_TEXTS["ru"])
    bot.send_message(call.message.chat.id, welcome)
    bot.send_message(call.message.chat.id, "Выбери раздел или просто напиши вопрос:", reply_markup=build_main_menu())

@bot.message_handler(commands=['menu'])
def menu_command(message):
    bot.reply_to(message, "Выбери раздел или просто напиши вопрос:", reply_markup=build_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def main_menu_callback(call):
    uid = call.from_user.id
    action = call.data.replace("menu_", "")
    bot.answer_callback_query(call.id)

    if action == "about":
        bot.send_message(call.message.chat.id,
            "О боте:\n\nЭтот бот появился из обычной боли любого продавца — каждое описание товара съедает время, которое лучше потратить на сам бизнес.\n\nТеперь хватает одной фразы с названием товара, и через 10 секунд готов текст, который реально разбирается в брендах и моделях, а не лепит общие слова.\n\nЧто умеет бот:\n- Писать описания для Avito, Wildberries и Ozon\n- Распознавать товар по фото\n- Общаться на 10 языках\n- Переписывать, сокращать и редактировать тексты прямо в диалоге\n- Разбираться в брендах, моделях, материалах и технологиях\n\nПросто напиши название товара — начнём.")

    elif action == "subscription":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Оплатить Telegram Stars (мгновенно)", callback_data="pay_stars"))
        bot.send_message(call.message.chat.id,
            "Подписка снимает лимит на количество запросов и даёт постоянный доступ ко всем функциям бота.\n\n"
            "Telegram Stars — оплата мгновенная, подписка активируется автоматически. Нажми кнопку ниже.\n\n"
            "Перевод на карту (160 ₽ + отзыв о работе сервиса) — переведи 160 ₽ на карту " + CARD_NUMBER + ", оставь короткий отзыв о боте и пришли скриншот перевода вместе с командой /myid. Активирую вручную в течение часа.",
            reply_markup=markup)

    elif action == "settings":
        s = get_settings(uid)
        bot.send_message(call.message.chat.id,
            "Настройки:\n\nВыбери модель ИИ, площадку, тон и длину текста по умолчанию.",
            reply_markup=build_settings_markup(s))

    elif action == "support":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Написать в поддержку", url="https://t.me/" + OWNER_USERNAME))
        bot.send_message(call.message.chat.id,
            "Что-то пошло не так или есть идея как улучшить бота? Нажми кнопку ниже — ответим быстро.",
            reply_markup=markup)

@bot.message_handler(commands=['language'])
def language_command(message):
    bot.reply_to(message, "Выбери язык / Choose your language:", reply_markup=build_language_markup())

@bot.message_handler(commands=['new'])
def new_topic(message):
    uid = message.from_user.id
    user_history[uid] = []
    bot.reply_to(message, "Начинаем новый разговор с чистого листа.\n\nПредыдущий контекст сброшен — бот забыл прошлый товар и все правки к нему. Это полезно, если переходишь к описанию совсем другой вещи, чтобы детали не смешивались.\n\nПросто напиши название нового товара и детали (бренд, цвет, состояние, материал), или пришли фото — начнём заново.")

@bot.message_handler(commands=['about'])
def about_command(message):
    bot.reply_to(message, "О боте:\n\nЭтот бот появился из обычной боли любого продавца — каждое описание товара съедает время, которое лучше потратить на сам бизнес.\n\nТеперь хватает одной фразы с названием товара, и через 10 секунд готов текст, который реально разбирается в брендах и моделях, а не лепит общие слова.\n\nИм уже пользуются продавцы на Avito, Wildberries и Ozon — присоединяйся.")

@bot.message_handler(commands=['support'])
def support_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Написать в поддержку", url="https://t.me/" + OWNER_USERNAME))
    bot.reply_to(message, "Что-то пошло не так или есть идея как улучшить бота? Нажми кнопку ниже — ответим быстро.", reply_markup=markup)

@bot.message_handler(commands=['referral'])
def referral_command(message):
    uid = message.from_user.id
    link = "https://t.me/" + BOT_USERNAME + "?start=ref_" + str(uid)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Поделиться ссылкой", switch_inline_query=link))
    bot.reply_to(message,
        "Приглашай друзей и получай бонусные запросы!\n\nЗа каждого, кто перейдёт по твоей ссылке и запустит бота, тебе начислится +" + str(REFERRAL_BONUS) + " бесплатных запроса.",
        reply_markup=markup)

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
    bot.reply_to(message, "Твои последние описания. Нажми на нужное чтобы вернуться и продолжить редактировать:", reply_markup=markup)

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
    lang = get_language(uid)
    system_prompt = build_system_prompt(settings_, lang)
    user_history[uid] = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": selected_text}
    ]
    bot.answer_callback_query(call.id, "Загружено")
    bot.send_message(call.message.chat.id, "Вернулся к этому описанию, можно редактировать:\n\n" + selected_text)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != OWNER_ID:
        return
    active_subs = sum(1 for uid, exp in pro_users.items() if exp > datetime.now())
    bot.reply_to(message, "Статистика:\n\nВсего пользователей: " + str(len(all_users)) + "\nАктивных подписок: " + str(active_subs) + "\nПришло по рефералке: " + str(len(referred_by)))

@bot.message_handler(commands=['settings'])
def settings_command(message):
    uid = message.from_user.id
    s = get_settings(uid)
    bot.reply_to(message, "Настройки:\n\nВыбери модель ИИ, площадку, тон и длину текста по умолчанию.", reply_markup=build_settings_markup(s))

@bot.callback_query_handler(func=lambda call: call.data.startswith("model_") or call.data.startswith("platform_") or call.data.startswith("tone_") or call.data.startswith("length_"))
def settings_callback(call):
    uid = call.from_user.id
    s = get_settings(uid)
    if call.data.startswith("model_"):
        s["model"] = call.data.split("_")[1]
    elif call.data.startswith("platform_"):
        s["platform"] = call.data.split("_", 1)[1]
    elif call.data.startswith("tone_"):
        s["tone"] = call.data.split("_")[1]
    elif call.data.startswith("length_"):
        s["length"] = call.data.split("_")[1]
    bot.answer_callback_query(call.id, "Обновлено")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=build_settings_markup(s))
    except Exception:
        pass

@bot.message_handler(commands=['subscription'])
def subscription_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Оплатить Telegram Stars (мгновенно)", callback_data="pay_stars"))
    bot.reply_to(message,
        "Подписка снимает лимит на количество запросов и даёт постоянный доступ ко всем функциям бота.\n\n"
        "Telegram Stars — оплата мгновенная, подписка активируется автоматически. Нажми кнопку ниже.\n\n"
        "Перевод на карту (160 ₽ + отзыв о работе сервиса) — переведи 160 ₽ на карту " + CARD_NUMBER + ", оставь короткий отзыв о боте и пришли скриншот перевода вместе с командой /myid. Активирую вручную в течение часа.",
        reply_markup=markup)

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
    bot.reply_to(message, "Оплата прошла! Подписка активна до " + expiry.strftime("%d.%m.%Y") + ".")

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
    lang = get_language(uid)
    lang_name = LANGUAGES.get(lang, "Russian")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        b64_image = base64.b64encode(downloaded).decode('utf-8')
        caption = message.caption if message.caption else "Describe this product."
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": "You are a product expert and marketplace copywriter. Look at the photo carefully. If the user caption explicitly states a brand or model name, you must trust that information completely and not override it with your own visual guess. Write a selling description in " + lang_name + ", 5-8 sentences, natural language."},
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
    lang = get_language(uid)
    is_new_topic = len(history) == 0
    if not is_unlimited(uid) and is_new_topic:
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "Бесплатные запросы закончились. Напиши /subscription.")
            return
    bot.send_chat_action(message.chat.id, 'typing')
    if is_new_topic:
        history.append({"role": "system", "content": build_system_prompt(settings_, lang)})
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
