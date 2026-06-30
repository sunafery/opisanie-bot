import telebot
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
FREE_LIMIT = 3

user_free_left = {}
user_history = {}
pro_users = set()

def clean_text(text):
    return re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)

SYSTEM_PROMPT = """Ты профессиональный копирайтер маркетплейсов и эксперт в моде, кроссовках, брендах, технике и товарах в целом. Ты помогаешь продавцам создавать продающие описания и разбираешься в конкретных моделях, их истории, материалах и характеристиках. Общайся естественно и живо, как опытный человек, а не по жёсткому шаблону.

Общие правила:
- Пиши только на русском языке, грамотно, живым литературным языком, без канцелярита
- Никогда не используй иероглифы или символы других алфавитов
- Если товар это известная модель, используй свои реальные знания о ней: материалы, технологии, историю, особенности
- Не выдумывай факты, которых не знаешь точно, в таком случае пиши обобщённо, но убедительно
- Если пользователь просит переписать, сократить, добавить характеристики, изменить тон, выполняй правку, опираясь на предыдущий текст в этом диалоге
- Если пользователь просит описание для карточки товара Wildberries или Ozon, пиши развёрнуто и структурированно: вступление, блок с особенностями, блок Характеристики построчно, призыв к покупке. Объём 8-12 предложений
- Если пользователь просит описание для Avito, пиши короче, проще, как от частного продавца, 5-7 предложений
- Если пользователь просит именно характеристики, дай отдельным компактным списком: бренд, модель, материалы, технологии, страна бренда, для чего подходит
- Если пользователь спрашивает где искать конкретную узнаваемую модель или это уместно по контексту, упомяни 2-3 типа площадок (официальный сайт бренда, Авито, Wildberries, площадки перепродажи кроссовок), кратко оцени распространённость модели, и уточни что точную доступность и цену нужно проверять напрямую
- Не пиши конкретные несуществующие ссылки, только называй типы платформ
- Без хештегов и эмодзи
- Не добавляй в конце шаблонную фразу о готовности переписать или изменить текст, пользователь и так знает что может попросить правку"""

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
        bot.reply_to(message, "Привет, создатель! У тебя безлимит на генерации.\n\nНапиши название товара и детали, я составлю описание. Можно потом попросить переписать, сократить или добавить характеристики.")
        return
    if uid not in user_free_left:
        user_free_left[uid] = FREE_LIMIT
    bot.reply_to(message, "Привет! Я делаю продающие описания товаров для Avito, Wildberries и Ozon, разбираюсь в брендах и моделях.\n\nНапиши мне название товара и детали (бренд, цвет, состояние, материал), получишь готовый текст. После этого можно попросить переписать, сократить, добавить характеристики или сделать под другую площадку.\n\nУ тебя " + str(user_free_left[uid]) + " бесплатных описаний. Дальше доступна Подписка, команда /podpiska")

@bot.message_handler(commands=['new'])
def new_topic(message):
    uid = message.from_user.id
    user_history[uid] = []
    bot.reply_to(message, "Начинаем новое описание. Напиши название товара и детали.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "Что умеет этот бот:\n\nЯ пишу продающие описания товаров для Avito, Wildberries и Ozon. Разбираюсь в брендах, моделях кроссовок, технике и других товарах, могу рассказать про конкретную модель, её характеристики и где её обычно искать.\n\nКак пользоваться:\n1. Напиши название товара и детали (бренд, цвет, состояние, материал)\n2. Получи готовое описание\n3. Можешь сразу попросить: перепиши короче, добавь характеристики, сделай под Wildberries\n4. Команда /new начинает описание нового товара заново\n\nКоманды:\n/start - начать сначала\n/new - новый товар\n/podpiska - оформить Подписку\n/о - о боте\n/support - поддержка\n/myid - узнать свой Telegram ID")

@bot.message_handler(commands=['about'])
def about_command(message):
    bot.reply_to(message, "О нас:\n\nЭтот бот создан, чтобы продавцам на маркетплейсах не приходилось тратить часы на написание описаний товаров. Просто опиши товар в паре слов, и получишь готовый грамотный текст за секунды.")

@bot.message_handler(commands=['support'])
def support_command(message):
    bot.reply_to(message, "Поддержка:\n\nЕсли у тебя вопрос, ошибка или предложение, просто напиши сообщение прямо в этот чат, мы постараемся ответить как можно быстрее.")

@bot.message_handler(commands=['podpiska'])
def subscription(message):
    bot.reply_to(message, "Чтобы оформить Подписку (безлимит) за 299 руб/мес, переведи на карту " + CARD_NUMBER + " и пришли скриншот сюда. После перевода также пришли команду /myid и сообщи мне результат, активирую Подписку вручную в течение часа.")

@bot.message_handler(commands=['myid'])
def myid(message):
    bot.reply_to(message, "Твой Telegram ID: " + str(message.from_user.id) + "\n\nЕсли оплачивал Подписку, пришли этот номер мне.")

@bot.message_handler(commands=['activate'])
def activate(message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        pro_users.add(target_id)
        bot.reply_to(message, "Готово, пользователь " + str(target_id) + " теперь с Подпиской (безлимит).")
        try:
            bot.send_message(target_id, "Твоя Подписка активирована! Теперь у тебя безлимит на описания.")
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "Используй так: /activate 123456789 (укажи ID пользователя)")

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
            bot.reply_to(message, "Бесплатные описания закончились. Напиши /podpiska чтобы оформить Подписку с безлимитом.")
            return

    bot.send_chat_action(message.chat.id, 'typing')

    if is_new_topic:
        styles = [
            "энергичный и динамичный, с короткими фразами",
            "спокойный и дружелюбный, как совет от друга",
            "уверенный и убедительный, с акцентом на выгоду",
            "лёгкий и игривый, с лёгкой иронией",
            "лаконичный и по делу, без лишних слов"
        ]
        style_note = "\n\nСтиль текста: " + random.choice(styles)
        user_text = message.text + style_note
        history.append({"role": "system", "content": SYSTEM_PROMPT})
    else:
        user_text = message.text

    history.append({"role": "user", "content": user_text})

    if len(history) > 10:
        trimmed_history = [history[0]] + history[-9:]
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
            footer = "\n\n— Осталось бесплатных новых описаний: " + str(user_free_left[uid])
        else:
            footer = ""

        bot.reply_to(message, text + footer)
    except Exception:
        bot.reply_to(message, "Произошла ошибка, попробуй ещё раз через минуту.")

print("Бот запущен и работает...")
bot.polling(none_stop=True)
