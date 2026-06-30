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

WELCOME = """Привет! Я делаю продающие описания товаров для Avito, Wildberries и Ozon за 10 секунд.

Просто напиши мне название товара и пару деталей (цвет, состояние, особенности) — я верну готовый текст.

Пример: "Кроссовки Nike Air Max, белые, новые, размер 42"

У тебя {free} бесплатных описаний. Дальше — 299 руб/месяц безлимит (просто напиши /pro)."""

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT
    bot.reply_to(message, WELCOME.format(free=user_free_left[uid]))

@bot.message_handler(commands=['pro'])
def pro(message):
    bot.reply_to(message, f"Чтобы получить безлимит за 299 руб/мес — переведи на карту {CARD_NUMBER} и пришли скриншот сюда. Активирую вручную в течение часа.")

@bot.message_handler(func=lambda m: True)
def generate(message):
    uid = message.from_user.id
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

    prompt = f"""Напиши продающее описание товара для маркетплейса (Avito/Wildberries/Ozon) на основе этих данных:
{message.text}

Стиль текста на этот раз: {chosen_style}

Требования:
- 4-6 предложений
- Подчеркни выгоды для покупателя, не просто перечисляй характеристики
- Естественный, живой язык, без канцелярита
- В конце короткий призыв к действию
- Без хештегов и эмодзи
- Обязательно сформулируй текст по-новому, не используй шаблонные клише и затёртые фразы"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=1.1
        )
        text = response.choices[0].message.content
        user_free_left[uid] -= 1
        bot.reply_to(message, f"{text}\n\n— Осталось бесплатных: {user_free_left[uid]}")
    except Exception:
        bot.reply_to(message, "Произошла ошибка, попробуй ещё раз через минуту.")

print("Бот запущен и работает...")
bot.polling(none_stop=True)
