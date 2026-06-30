import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
import random
import re
import os
from groq import Groq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CARD_NUMBER = os.environ.get("CARD_NUMBER")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

OWNER_ID = 1249820876
OWNER_USERNAME = "sunafery"
FREE_LIMIT = 3
STARS_PRICE = 150

user_free_left = {}
user_history = {}
pro_users = set()

def clean_text(text):
    return re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)

SYSTEM_PROMPT = """Ты дружелюбный и грамотный ИИ-помощник в Telegram. Ты можешь поддержать разговор на любую тему и ответить на любой вопрос пользователя, как полноценный собеседник.

При этом у тебя есть отдельная сильная специализация: ты профессиональный копирайтер маркетплейсов и эксперт в моде, кроссовках, брендах, технике и товарах. Когда пользователь просит написать или обсудить описание товара, ты применяешь эти правила:
- Если товар это известная модель, используй свои реальные знания о ней: материалы, технологии, историю, особенности
- Не выдумывай факты, которых не знаешь точно, тогда пиши обобщённо, но убедительно
- Если просят описание для карточки Wildberries или Ozon, пиши развёрнуто: вступление, особенности, блок Характеристики построчно, призыв к покупке, 8-12 предложений
- Если просят описание для Avito, пиши короче и проще, как от частного продавца, 5-7 предложений
- Если просят характеристики, дай компактным списком: бренд, модель, материалы, технологии, для чего подходит
- Если уместно, упомяни типы площадок где искать товар (официальный сайт бренда, Авито, Wildberries, площадки перепродажи), и уточни что точную доступность нужно проверять напрямую

Общие правила для любых ответов:
- Пиши только на русском языке (если пользователь сам не пишет на другом), грамотно, живым языком, без канцелярита
- Никогда не используй иероглифы или символы других алфавитов
- Если пользователь просит переписать, сократить, продолжить или изменить что-то из предыдущего сообщения, опирайся на контекст диалога
- Не добавляй шаблонные фразы вроде предложений переписать текст, если тебя об этом не просили
- Веди себя естественно, как живой умный собеседник, а не как бот по жёсткому шаблону"""

def get_user_state(uid):
    if uid not in user_history:
        user_history[uid] = []
    return user_history[uid]

def is_unlimited(uid):
    return uid == OWNER_ID or uid in pro_users

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    user_history[uid] = []
    if uid == OWNER_ID:
        bot.reply_to(message, "Привет, создатель! У тебя безлимит.\n\nМожешь спросить о чём угодно или попросить описание товара.")
        return
    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT
    bot.reply_to(message, "Привет! Я ИИ-помощник, который пишет продающие описания товаров за секунды — для Avito, Wildberries и Ozon.\n\nЗнаю бренды, модели, материалы и технологии, поэтому описания получаются не шаблонные, а живые и убедительные. Могу переписать, сократить, добавить характеристики или адаптировать под нужную площадку прямо в диалоге.\n\nА ещё со мной можно просто поговорить на любую тему, как с обычным ИИ-помощником.\n\nКак начать: напиши название товара и пару деталей — бренд, цвет, состояние. Например: Кроссовки Nike Air Max, белые, новые, размер 42\n\nУ тебя " + str(user_free_left[uid]) + " бесплатных запросов. Дальше — Подписка с безлимитом, команда /subscription")

@bot.message_handler(commands=['new'])
def new_topic(message):
    uid = message.from_user.id
    user_history[uid] = []
    bot.reply_to(message, "Начинаем новый разговор. Напиши что нужно.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "Что умеет этот бот:\n\nПишу продающие описания товаров для Avito, Wildberries и Ozon за секунды. Разбираюсь в брендах, моделях кроссовок, технике и других товарах — описания получаются живые, а не шаблонные. А ещё можешь просто пообщаться со мной на любую тему.\n\nКак пользоваться:\n1. Напиши название товара и детали, или любой вопрос\n2. Получи ответ\n3. Можешь попросить: перепиши короче, добавь характеристики, сделай под Wildberries\n4. Команда /new начинает разговор заново\n\nКоманды:\n/start - начать сначала\n/new - новый разговор\n/subscription - оформить Подписку\n/about - о нас\n/support - поддержка\n/myid - узнать свой Telegram ID")

@bot.message_handler(commands=['about'])
def about_command(message):
    bot.reply_to(message, "О нас:\n\nЭтот бот появился из обычной боли любого продавца — каждое описание товара съедает время, которое лучше потратить на сам бизнес.\n\nТеперь хватает одной фразы с названием товара, и через 10 секунд готов текст, который реально разбирается в брендах и моделях, а не лепит общие слова.\n\nИм уже пользуются продавцы на Avito, Wildberries и Ozon — присоединяйся.")

@bot.message_handler(commands=['support'])
def support_command(message):
    bot.reply_to(message, "Что-то пошло не так или есть идея, как сделать бота лучше? Пиши прямо мне — @" + OWNER_USERNAME + "\n\nОтвечаю обычно быстро, разберёмся вместе.")

@bot.message_handler(commands=['subscription'])
def subscription(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Оплатить Telegram Stars (мгновенно)", callback_data="pay_stars"))
    text = "Оформление Подписки (безлимит):\n\n1) Telegram Stars - оплата мгновенная, активируется автоматически, нажми кнопку ниже\n\n2) 160 руб + отзыв о работе сервиса - переведи 160 руб на карту " + CARD_NUMBER + " и напиши пару слов о том как тебе бот (можно прямо сюда, в любой чат продавцов или в виде репоста). Пришли скриншот перевода и команду /myid, активирую вручную в течение часа\n\nЕсли нужна оплата в криптовалюте, напиши в поддержку @" + OWNER_USERNAME + ", договоримся индивидуально"
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
    pro_users.add(uid)
    bot.reply_to(message, "Оплата прошла успешно! Подписка активирована, теперь у тебя безлимит.")

@bot.message_handler(commands=['myid'])
def myid(message):
    bot.reply_to(message, "Твой Telegram ID: " + str(message.from_user.id) + "\n\nЕсли оплачивал Подписку переводом на карту, пришли этот номер мне.")

@bot.message_handler(commands=['activate'])
def activate(message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        pro_users.add(target_id)
        bot.reply_to(message, "Готово, пользователь " + str(target_id) + " теперь с Подпиской.")
        try:
            bot.send_message(target_id, "Твоя Подписка активирована! Теперь у тебя безлимит.")
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "Используй так: /activate 123456789")

@bot.message_handler(commands=['deactivate'])
def deactivate(message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        pro_users.discard(target_id)
        bot.reply_to(message, "Подписка отключена у пользователя " + str(target_id) + ".")
    except (IndexError, ValueError):
        bot.reply_to(message, "Используй так: /deactivate 123456789")

@bot.message_handler(func=lambda m: True)
def generate(message):
    uid = message.from_user.id
    history = get_user_state(uid)

    is_new_topic = len(history) == 0

    if not is_unlimited(uid) and is_new_topic:
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT
        if user_free_left[uid] <= 0:
            bot.reply_to(message, "Бесплатные запросы закончились. Напиши /subscription чтобы оформить Подписку с безлимитом.")
            return

    bot.send_chat_action(message.chat.id, 'typing')

    if is_new_topic:
        history.append({"role": "system", "content": SYSTEM_PROMPT})

    history.append({"role": "user", "content": message.text})

    if len(history) > 12:
        trimmed_history = [history[0]] + history[-11:]
    else:
        trimmed_history = history

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=trimmed_history,
            max_tokens=700,
            temperature=0.8
        )
        text = clean_text(response.choices[0].message.content)
        history.append({"role": "assistant", "content": text})

        if not is_unlimited(uid) and is_new_topic:
            user_free_left[uid] -= 1
            footer = "\n\n— Осталось бесплатных запросов: " + str(user_free_left[uid])
        else:
            footer = ""

        bot.reply_to(message, text + footer)
    except Exception:
        bot.reply_to(message, "Произошла ошибка, попробуй ещё раз через минуту.")

print("Бот запущен и работает...")
bot.polling(none_stop=True)
