import telebot
import random
from groq import Groq

import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CARD_NUMBER = os.environ.get("CARD_NUMBER")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

user_free_left = {}
FREE_LIMIT = 3
OWNER_ID = 1249820876

WELCOME = """Привет! Я делаю продающие описания товаров для Avito, Wildberries и Ozon за 10 секунд.

Просто напиши мне название товара и пару деталей (цвет, состояние, особенности) — я верну готовый текст.

Пример: "Кроссовки Nike Air Max, белые, новые, размер 42"

У тебя {free} бесплатных описаний. Дальше — 299 руб/месяц безлимит (просто напиши /pro)."""

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if uid == OWNER_ID:
        bot.reply_to(message, "Привет, создатель! У тебя безлимит на генерации.\n\nПросто напиши название товара и детали.")
        return
    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT
    bot.reply_to(message, WELCOME.format(free=user_free_left[uid]))

@bot.message_handler(commands=['pro'])
def pro(message):
    bot.reply_to(message, f"Чтобы получить безлимит за 299 руб/мес — переведи на карту {CARD_NUMBER} и пришли скриншот сюда. Активирую вручную в течение часа.")

@bot.message_handler(func=lambda m: True)
def generate(message):
    uid = message.from_user.id

    if uid != OWNER_ID:
        if uid not in user_free_left:
            user_free_left[uid] = FREE_LIMIT

        if user_free_left[uid] <= 0:
            bot.reply_to(message, "Бесплатные описания закончились. Напиши /pro чтобы получить безлимит за 299 руб/мес.")
            return

    bot.send_chat_action(message.chat.id, 'typing')

    styles = [
        "энергичный и динамичный, с короткими фразами",
        "спокойный и дружелюбный, как совет от друга",
        "уверенный и убедительный, с акцентом на выгоду",
        "лёгкий и игривый, с лёгкой иронией",
        "лаконичный и по делу, без лишних слов"
    ]
    chosen_style = random.choice(styles)

    prompt = f"""Ты профессиональный копирайтер маркетплейсов и эксперт в моде, кроссовках, брендах и стрит-стиле. Ты хорошо разбираешься в конкретных моделях обуви и одежды, их истории, материалах и особенностях. Напиши грамотное продающее описание товара для Avito/Wildberries/Ozon на основе этих данных от пользователя:
{message.text}

Стиль текста на этот раз: {chosen_style}

Правила:
- Если товар — известная модель (например конкретная модель кроссовок, бренд одежды) — используй свои реальные знания о ней: материалы, технологии, историю, особенности дизайна, для чего она создавалась
- Если пользователь дал дополнительные детали (цвет, состояние, размер) — обязательно используй их
- Пиши только на русском языке, грамотно и без ошибок, живым литературным языком, без канцелярита
- Никогда не используй иероглифы, латиницу не к месту или символы других языков — только чистый русский текст
- 5-7 предложений
- Подчеркни выгоды для покупателя, а не просто перечисляй характеристики
- В конце короткий, естественный призыв к действию
- Без хештегов и эмодзи
- Каждый раз формулируй по-новому, не используй шаблонные клише и затёртые фразы
- Уточняющий вопрос задавай ТОЛЬКО если в сообщении нет вообще никакой узнаваемой информации о товаре (например просто слово обувь без названия модели или бренда). Если товар узнаваем — пиши полноценное уверенное описание без вопросов в конце
- Учитывай разницу площадок: для Avito пиши чуть более простым, личным тоном, как от частного продавца. Для Wildberries и Ozon — более структурированным и уверенным тоном, как от официального продавца, с акцентом на характеристики и преимущества товара. Если площадка явно не указана пользователем, пиши универсально, подходящее для обеих"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=450,
            temperature=0.85
        )
        text = response.choices[0].message.content
        if uid == OWNER_ID:
            bot.reply_to(message, text)
        else:
            user_free_left[uid] -= 1
            bot.reply_to(message, f"{text}\n\n— Осталось бесплатных: {user_free_left[uid]}")
    except Exception:
        bot.reply_to(message, "Произошла ошибка, попробуй ещё раз через минуту.")

print("Бот запущен и работает...")
bot.polling(none_stop=True)
