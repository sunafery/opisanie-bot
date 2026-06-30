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
BOT_USERNAME = "@opisanie_marketbot"
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

def get_settings(uid):
    if uid not in user_settings:
        user_settings[uid] = {"model": "smart", "platform": "auto"}
    return user_settings[uid]

def clean_text(text):
    return re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)

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

def build_system_prompt(platform_pref):
    platform_line = ""
    if platform_pref == "avito":
        platform_line = "Пользователь предпочитает формат Avito по умолчанию: пиши короче, проще, как от частного продавца, 5-7 предложений, если он явно не попросит другую площадку."
    elif platform_pref == "ozonwb":
        platform_line = "Пользователь предпочитает формат карточки Wildberries/Ozon по умолчанию: пиши развёрнуто, 8-12 предложений, с блоком Характеристики, если он явно не попросит другую площадку."

    return """Ты дружелюбный и грамотный ИИ-помощник в Telegram. Ты можешь поддержать разговор на любую тему и ответить на любой вопрос пользователя, как полноценный собеседник.

При этом у тебя есть отдельная сильная специализация: ты профессиональный копирайтер маркетплейсов и эксперт в моде, кроссовках, брендах, технике и товарах. Когда пользователь просит написать или обсудить описание товара, ты применяешь эти правила:
- Если товар это известная модель, используй свои реальные знания о ней: материалы, технологии, историю, особенности
- Не выдумывай факты, которых не знаешь точно, тогда пиши обобщённо, но убедительно
- Если просят описание для карточки Wildberries или Ozon, пиши развёрнуто: вступление, особенности, блок Характеристики построчно, призыв к покупке, 8-12 предложений
- Если просят описание для Avito, пиши короче и проще, как от частного продавца, 5-7 предложений
- Если просят характеристики, дай компактным списком: бренд, модель, материалы, технологии, для чего подходит
- Если уместно, упомяни типы площадок где искать товар, и уточни что точную доступность нужно проверять напрямую
- Если просят перевести текст на другой язык, переведи точно и грамотно
""" + platform_line + """

Общие правила для любых ответов:
- Пиши только на русском языке (если пользователь сам не пишет на другом или явно просит перевод), грамотно, живым языком, без канцелярита
- Никогда не используй иероглифы или символы других алфавитов, если явно не попросили перевод на соответствующий язык
- Если пользователь просит переписать, сократить, продолжить или изменить что-то из предыдущего сообщения, опирайся на контекст диалога
- Не добавляй шаблонные фразы вроде предложений переписать текст, если тебя об этом не просили
- Веди себя естественно, как живой умный собеседник, а не как бот по жёсткому шаблону"""

def get_user_state(uid):
    if uid not in user_history:
        user_history[uid] = []
    return user_history[uid]

DEFAULT_COMMANDS = [
    BotCommand("start", "Начать сначала"),
    BotCommand("new", "Новый разговор"),
    BotCommand("settings", "Режим и площадка"),
    BotCommand("history", "Последние описания"),
    BotCommand("referral", "Пригласить друга"),
    BotCommand("subscription", "Оформить Подписку"),
    BotCommand("about", "О нас"),
    BotCommand("support", "Поддержка"),
    BotCommand("myid", "Узнать свой Telegram ID")
]

OWNER_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand("activate", "Включить Подписку пользователю"),
    BotCommand("deactivate", "Отключить Подписку пользователю"),
    BotCommand("stats", "Статистика бота")
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
        bot.reply_to(message, "Привет, создатель! У тебя безлимит.\n\nМожешь спросить о чём угодно или попросить описание товара. В меню доступны /activate, /deactivate и /stats.")
        return
    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT
    bot.reply_to(message, "Привет! Я ИИ-помощник, который пишет продающие описания товаров за секунды — для Avito, Wildberries и Ozon.\n\nЗнаю бренды, модели, материалы и технологии, поэтому описания получаются не шаблонные, а живые и убедительные. Могу переписать, сократить, добавить характеристики, перевести на другой язык или адаптировать под нужную площадку прямо в диалоге.\n\nМожешь прислать даже фото товара — опишу его сам.\n\nКак начать: напиши название товара и пару деталей. Например: Кроссовки Nike Air Max, белые, новые, размер 42\n\nКоманда /settings — выбрать режим работы и площадку по умолчанию.")

@bot.message_handler(commands=['new'])
def new_topic(message):
    uid = message.from_user.id
    user_history[uid] = []
    bot.reply_to(message, "Начинаем новый разговор. Напиши что нужно.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "Что умеет этот бот:\n\nПишу продающие описания товаров для Avito, Wildberries и Ozon за секунды. Разбираюсь в брендах, моделях кроссовок, технике и других товарах. Понимаю фото товара. А ещё можешь просто пообщаться со мной на любую тему.\n\nКоманды:\n/new - новый разговор\n/settings - модель ИИ и площадка\n/history - последние описания\n/referral - пригласить друга за бонус\n/subscription - оформить Подписку")

@bot.message_handler(commands=['about'])
def about_command(message):
    bot.reply_to(message, "О нас:\n\nЭтот бот появился из обычной боли любого продавца — каждое описание товара съедает время, которое лучше потратить на сам бизнес.\n\nТеперь хватает одной фразы с названием товара, и через 10 секунд готов текст, который реально разбирается в брендах и моделях, а не лепит общие слова.\n\nИм уже пользуются продавцы на Avito, Wildberries и Ozon — присоединяйся.")

@bot.message_handler(commands=['support'])
def support_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Написать в поддержку", url="https://t.me/" + OWNER_USERNAME))
    bot.reply_to(message, "Что-то пошло не так или есть идея, как сделать бота лучше? Нажми кнопку ниже — ответим быстро и разберёмся вместе.", reply_markup=markup)

@bot.message_handler(commands=['referral'])
def referral_command(message):
    uid = message.from_user.id
    link = "https://t.me/" + BOT_USERNAME + "?start=ref_" + str(uid)
    bot.reply_to(message, "Приглашай друзей и получай бонусные запросы!\n\nЗа каждого, кто перейдёт по твоей ссылке и запустит бота, тебе начислится +" + str(REFERRAL_BONUS) + " бесплатных запроса.\n\nТвоя ссылка:\n" + link)

@bot.message_handler(commands=['history'])
def history_command(message):
    uid = message.from_user.id
    items = user_text_history.get(uid, [])
    if not items:
        bot.reply_to(message, "Пока нет сохранённых описаний. Сгенерируй первое!")
        return
    text = "Твои последние описания:\n\n"
    for i, item in enumerate(items, 1):
        short = item if len(item) < 200 else item[:200] + "..."
        text += str(i) + ") " + short + "\n\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != OWNER_ID:
        return
    active_subs = sum(1 for uid, exp in pro_users.items() if exp > datetime.now())
    text = ("Статистика бота:\n\n"
            "Всего пользователей: " + str(len(all_users)) + "\n"
            "Активных подписок: " + str(active_subs) + "\n"
            "Приглашено по реферальной программе: " + str(len(referred_by)))
    bot.reply_to(message, text)

@bot.message_handler(commands=['settings'])
def settings_command(message):
    uid = message.from_user.id
    s = get_settings(uid)
    markup = build_settings_markup(s)
    bot.reply_to(message, "Настройки:\n\nВыбери модель ИИ и площадку по умолчанию для описаний.", reply_markup=markup)

def build_settings_markup(s):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(("✅ " if s["model"] == "smart" else "") + "Умная модель", callback_data="model_smart"))
    markup.add(InlineKeyboardButton(("✅ " if s["model"] == "fast" else "") + "Быстрая модель", callback_data="model_fast"))
    markup.add(InlineKeyboardButton(("✅ " if s["platform"] == "avito" else "") + "Площадка: Avito", callback_data="platform_avito"))
    markup.add(InlineKeyboardButton(("✅ " if s["platform"] == "ozonwb" else "") + "Площадка: Wildberries/Ozon", callback_data="platform_ozonwb"))
    markup.add(InlineKeyboardButton(("✅ " if s["platform"] == "auto" else "") + "Площадка: Автоматически", callback_data="platform_auto"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith("model_") or call.data.startswith("platform_"))
def settings_callback(call):
    uid = call.from_user.id
    s = get_settings(uid)
    if call.data.startswith("model_"):
        s["model"] = call.data.split("_")[1]
    else:
        s["platform"] = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, "Настройка обновлена")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=build_settings_markup(s))
    except Exception:
        pass

@bot.message_handler(commands=['subscription'])
def subscription(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Оплатить Telegram Stars (мгновенно)", callback_data="pay_stars"))
    text = ("Подписка снимает лимит на количество запросов и даёт постоянный доступ ко всем функциям бота.\n\n"
            "Доступны два способа оплаты:\n\n"
            "Telegram Stars — оплата происходит мгновенно внутри Telegram, подписка активируется автоматически сразу после оплаты. Нажми кнопку ниже.\n\n"
            "Перевод на карту (160 руб + отзыв о работе сервиса) — переведи 160 руб на карту " + CARD_NUMBER + ", оставь короткий отзыв о боте и пришли скриншот перевода вместе с командой /myid. Активирую подписку вручную в течение часа.\n\n"
            "Для оплаты в криптовалюте — напиши в поддержку, обсудим детали индивидуально.")
    bot.reply_to(message, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "pay_stars")
def buy_stars(call):
    prices = [LabeledPrice(label="Подписка на 1 месяц", amount=STARS_PRICE)]
    bot.send_invoice(
        call.message.chat.id,
        title="Подписка - безлимит",
        description="Безлимитные описания товаров на 1 месяц",
        invoice_payload="subscription_1_month",
        provider_token="",
        currency="XTR",
        prices=prices
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = message.from_user.id
    expiry = datetime.now() + timedelta(days=30)
    pro_users[uid] = expiry
    bot.reply_to(message, "Оплата прошла успешно! Подписка активна до " + expiry.strftime("%d.%m.%Y") + ".")

@bot.message_handler(commands=['myid'])
def myid(message):
    bot.reply_to(message, "Твой Telegram ID: " + str(message.from_user.id) + "\n\nЕсли оплачивал Подписку переводом на карту, пришли этот номер мне.")

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
        bot.reply_to(message, "Используй так: /activate 123456789 30")

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
        bot.reply_to(message, "Используй так: /deactivate 123456789")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    all_users.add(uid)

    if not is_unlimited(uid):
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "Бесплатные запросы закончились. Напиши /subscription чтобы оформить Подписку с безлимитом.")
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
                {"role": "system", "content": "Ты эксперт по товарам и копирайтер маркетплейсов. Внимательно рассмотри фото и определи что за товар, бренд, модель если узнаваема. Напиши грамотное продающее описание на русском языке, 5-8 предложений, без иероглифов и канцелярита."},
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
            bot.reply_to(message, "Бесплатные запросы закончились. Напиши /subscription чтобы оформить Подписку с безлимитом.")
            return

    bot.send_chat_action(message.chat.id, 'typing')

    if is_new_topic:
        system_prompt = build_system_prompt(settings_["platform"])
        history.append({"role": "system", "content": system_prompt})

    history.append({"role": "user", "content": message.text})

    if len(history) > 12:
        trimmed_history = [history[0]] + history[-11:]
    else:
        trimmed_history = history

    model_name = MODELS.get(settings_["model"], MODELS["smart"])

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=trimmed_history,
            max_tokens=700,
            temperature=0.8
        )
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
