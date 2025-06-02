import os
import random
import logging
import aiohttp
from datetime import datetime, timedelta
import pytz
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes,
    MessageHandler,
    filters
)
from telegram.error import TimedOut, NetworkError, RetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
import httpx
import signal
import sys
import json
from typing import Dict, List, Union

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
DNEVNIK_LOGIN = os.getenv('DNEVNIK_LOGIN')
DNEVNIK_PASSWORD = os.getenv('DNEVNIK_PASSWORD')
ADMIN_IDS = [1048782601]  

schedule_dict = {
    'Monday': [
        ('8:30', 'Разговоры о важном'),
        ('9:25', 'Геометрия'),
        ('10:30', 'География'),
        ('11:25', 'Английский язык'),
        ('12:20', 'Индивидуальный проект'),
        ('13:15', 'Вероятность и статистика'),
        ('14:20', 'Физика')
    ],
    'Tuesday': [
        ('8:30', 'Русский язык'),
        ('9:25', 'Обществознание'),
        ('10:30', 'История'),
        ('11:25', 'Алгебра'),
        ('12:20', 'Литература'),
        ('13:15', 'Английский язык'),
        ('14:20', 'Биология')
    ],
    'Wednesday': [
        ('8:30', 'Алгебра'),
        ('9:25', 'Физкультура'),
        ('10:30', 'Русский язык'),
        ('11:25', 'Геометрия'),
        ('12:20', 'Английский язык'),
        ('13:15', 'Алгебра'),
        ('14:20', 'Литература')
    ],
    'Thursday': [
        ('8:30', 'История'),
        ('9:25', 'Литература'),
        ('10:30', 'Алгебра'),
        ('11:25', 'Обществознание'),
        ('12:20', 'Геометрия'),
        ('13:15', 'Физика'),
        ('14:20', 'Физкультура')
    ],
    'Friday': [
        ('8:30', 'Обществознание'),
        ('9:25', 'Практикум по обществознание'),
        ('10:30', 'Информатика'),
        ('11:25', 'Обществознание'),
        ('12:20', 'Химия'),
        ('13:15', 'ОБЗР'),
        ('14:20', 'ОПД')
    ]
}

motivational_quotes = [
    "Верь в себя, и ты уже на полпути к успеху!",
    "Каждый день - это новая возможность.",
    "Действуй сейчас. Не жди идеального момента.",
    "Твои мечты не имеют срока годности.",
    "Путь в тысячу миль начинается с первого шага.",
    "Успех - это способность идти от неудачи к неудаче, не теряя энтузиазма.",
    "Образование - это не подготовка к жизни; образование - это и есть жизнь.",
    "Знание - сила, учение - свет!",
    "Никогда не поздно стать тем, кем ты мог бы быть.",
    "Сложнее всего начать действовать, все остальное зависит только от упорства.",
    "Чтобы дойти до цели, надо прежде всего идти.",
    "Учитесь так, словно вы постоянно ощущаете нехватку своих знаний.",
    "Образование — это то, что остаётся после того, как забывается всё выученное в школе.",
    "Усердие - мать успеха.",
    "Каждая ошибка - это еще один шаг к успеху.",
    "Чем больше знаешь, тем больше можешь.",
    "Ваше будущее создается тем, что вы делаете сегодня.",
    "Инвестиции в знания всегда приносят наибольший доход.",
    "Чтение - вот лучшее учение!",
    "Учиться и не размышлять - напрасно терять время.",
    "Чем умнее человек, тем легче он признает себя дураком.",
    "Знание есть сила, сила есть знание.",
    "Чтобы достичь цели, нужно прежде всего к ней идти.",
    "Великие дела начинаются с малого.",
    "Дорогу осилит идущий."
]

answers_dict: Dict[str, List[Union[str, str]]] = {}
ANSWERS_FILE = "answers.json"
global adding_answers_states
adding_answers_states = {}

CHATS_FILE = "chats.json"
CHATS_SET = set()  

def load_chats():
    """Загрузка списка чатов из файла"""
    try:
        global CHATS_SET
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, 'r', encoding='utf-8') as f:
                chats = json.load(f)
                CHATS_SET = set(chats)
                logger.info(f"Загружены чаты: {CHATS_SET}")
        return CHATS_SET
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке списка чатов: {e}")
        return CHATS_SET

def save_chats(chats):
    """Сохранение списка чатов в файл"""
    try:
        global CHATS_SET
        CHATS_SET = chats
        with open(CHATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(chats), f)
        logger.info(f"Сохранены чаты: {CHATS_SET}")
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении списка чатов: {e}")

def add_chat(chat_id: int):
    """Добавление нового чата в список"""
    global CHATS_SET
    CHATS_SET.add(chat_id)
    save_chats(CHATS_SET)
    logger.info(f"Добавлен чат {chat_id}. Текущие чаты: {CHATS_SET}")

def load_answers():
    """Загрузка ответов из файла"""
    global answers_dict
    try:
        if os.path.exists(ANSWERS_FILE):
            with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
                answers_dict = json.load(f)
            logger.info(f"✅ Ответы успешно загружены: {answers_dict}")
        else:
            logger.info("Файл с ответами не найден, создаем новый")
            answers_dict = {}
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке ответов: {e}")

def save_answers():
    """Сохранение ответов в файл"""
    try:
        logger.info(f"Попытка сохранения ответов: {answers_dict}")
        with open(ANSWERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(answers_dict, f, ensure_ascii=False, indent=2)
        logger.info("✅ Ответы успешно сохранены")
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении ответов: {e}")

async def add_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление ответов для предмета"""
    user_id = update.effective_user.id
    logger.info(f"Команда add_answer получена. ID пользователя: {user_id}")
    
    if user_id not in ADMIN_IDS:
        logger.warning(f"Отказано в доступе пользователю {user_id}")
        await update.message.reply_text("⛔️ Эта команда доступна только администратору")
        return
    
    try:
        args = context.args
        if not args:
            await update.message.reply_text("❗️ Укажите предмет после команды, например:\n/add_answer Математика")
            return
        
        subject = ' '.join(args)
        logger.info(f"Начало добавления ответов для предмета: {subject}")
        
        global adding_answers_states
        adding_answers_states[user_id] = {
            'subject': subject,
            'answers': []
        }
        logger.info(f"Состояние добавления ответов установлено для пользователя {user_id}: {adding_answers_states[user_id]}")
        
        await update.message.reply_text(
            f"📝 Отправьте ответы для предмета '{subject}'\n"
            "Можно отправлять текст и фотографии.\n"
            "Для завершения отправьте /done"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении ответов: {e}")
        await update.message.reply_text("❌ Произошла ошибка при добавлении ответов")

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка команды завершения добавления ответов"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    add_chat(chat_id)  
    logger.info(f"Получена команда /done от пользователя {user_id}")
    
    global adding_answers_states
    logger.info(f"Текущие состояния при получении /done: {adding_answers_states}")
    
    if user_id not in adding_answers_states:
        await update.message.reply_text("❌ Вы не находитесь в режиме добавления ответов")
        return
    
    try:
        state = adding_answers_states[user_id]
        subject = state['subject']
        answers = state['answers']
        
        if not answers:
            await update.message.reply_text("❌ Нет добавленных ответов")
            del adding_answers_states[user_id]
            return
        
        
        global answers_dict
        answers_dict[subject] = answers
        logger.info(f"Сохранение ответов для предмета {subject}: {answers}")
        save_answers()
        
        
        notification = f"📚 Администратор добавил ответы для предмета: {subject}"
        logger.info(f"Отправка уведомлений в чаты: {CHATS_SET}")
        for chat_id in CHATS_SET:
            try:
                await context.bot.send_message(chat_id=chat_id, text=notification)
                logger.info(f"Уведомление отправлено в чат {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления в чат {chat_id}: {e}")
        
        
        del adding_answers_states[user_id]
        logger.info(f"Завершено добавление ответов для предмета {subject}")
        await update.message.reply_text("✅ Ответы успешно сохранены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении добавления ответов: {e}")
        await update.message.reply_text("❌ Произошла ошибка при сохранении ответов")

async def handle_answer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка входящих сообщений при добавлении ответов"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    add_chat(chat_id)  
    
    if update.message.text and update.message.text.startswith('/'):
        return
    
    logger.info(f"Получено сообщение от пользователя {user_id}. Текст: {update.message.text if update.message.text else 'фото'}")
    logger.info(f"Текущие состояния добавления ответов: {adding_answers_states}")
    
   
    if user_id not in ADMIN_IDS:
        logger.info(f"Сообщение проигнорировано - пользователь не администратор")
        return
    
    
    if user_id not in adding_answers_states:
        logger.info(f"Сообщение проигнорировано - пользователь не в режиме добавления ответов")
        return
    
    logger.info(f"Обработка сообщения в режиме добавления ответов для предмета: {adding_answers_states[user_id]['subject']}")
    
    try:
        
        if update.message.text and not update.message.text.startswith('/'):
            adding_answers_states[user_id]['answers'].append({"type": "text", "content": update.message.text})
            logger.info(f"Добавлен текстовый ответ: {update.message.text[:50]}...")
        elif update.message.photo:
            photo_id = update.message.photo[-1].file_id
            adding_answers_states[user_id]['answers'].append({"type": "photo", "content": photo_id})
            logger.info(f"Добавлено фото с ID: {photo_id}")
        
        await update.message.reply_text("✅ Ответ добавлен. Отправьте еще или /done для завершения")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке ответа: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке ответа")

async def get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получение ответов по предмету"""
    try:
        logger.info("Запрос на получение ответов")
        args = context.args
        if not args:
            await update.message.reply_text("❗️ Укажите предмет после команды, например:\n/get_answer Математика")
            return
        
        subject = ' '.join(args)
        logger.info(f"Поиск ответов для предмета: {subject}")
        
        
        logger.info(f"Текущие ответы в базе: {answers_dict}")
        
        if subject not in answers_dict:
            logger.warning(f"Ответы не найдены для предмета: {subject}")
            await update.message.reply_text(f"❌ Ответы для предмета '{subject}' не найдены")
            return
        
        await update.message.reply_text(f"📚 Ответы по предмету: {subject}")
        
       
        for answer in answers_dict[subject]:
            logger.info(f"Отправка ответа типа: {answer['type']}")
            if answer["type"] == "text":
                await update.message.reply_text(answer["content"])
            elif answer["type"] == "photo":
                await update.message.reply_photo(answer["content"])
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении ответов: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении ответов")

async def list_answers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список всех доступных предметов с ответами"""
    try:
        if not answers_dict:
            await update.message.reply_text("📚 Список ответов пуст")
            return
        
        message = "📚 Доступные предметы с ответами:\n\n"
        for subject in answers_dict.keys():
            message += f"• {subject}\n"
        
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении списка ответов: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении списка ответов")

async def del_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление ответов для предмета"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Эта команда доступна только администратору")
        return
    
    try:
        args = context.args
        if not args:
            await update.message.reply_text("❗️ Укажите предмет после команды, например:\n/del_answer Математика")
            return
        
        subject = ' '.join(args)
        
        if subject in answers_dict:
            del answers_dict[subject]
            save_answers()
            await update.message.reply_text(f"✅ Ответы для предмета '{subject}' удалены")
            
            notification = f"🗑 Администратор удалил ответы для предмета: {subject}"
            logger.info(f"Отправка уведомлений в чаты: {CHATS_SET}")
            for chat_id in CHATS_SET:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=notification)
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления в чат {chat_id}: {e}")
        else:
            await update.message.reply_text(f"❌ Ответы для предмета '{subject}' не найдены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении ответов: {e}")
        await update.message.reply_text("❌ Произошла ошибка при удалении ответов")

async def get_weather(city: str) -> str:
    """Получение погоды для указанного города"""
    try:
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city}/today?unitGroup=metric&include=current&key={WEATHER_API_KEY}&contentType=json"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                current = data['currentConditions']
                return f"{city}: {current['temp']}°C, {current['conditions']}"
    except Exception as e:
        logger.error(f"Ошибка при получении погоды для {city}: {e}")
        return f"Не удалось получить погоду для {city}"

def get_random_image() -> str:
    """Получение случайного изображения из папки images"""
    try:
        images_dir = Path('images')
        images = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.png'))
        if images:
            return str(random.choice(images))
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении изображения: {e}")
        return None

async def send_morning_message(context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Отправка утреннего сообщения"""
    try:
        if not hasattr(context, '_chat_id'):
            logger.error("Chat ID не найден")
            return

        moscow_weather = await get_weather("Moscow")
        podolsk_weather = await get_weather("Podolsk")
        
        message = f"🌅 Доброе утро! Пусть этот день будет замечательным! ✨\n\n"
        message += f"🌤 Погода сегодня:\n🏙 {moscow_weather}\n🌆 {podolsk_weather}\n\n"
        message += f"💫 Вдохновляющая цитата дня:\n✨ {random.choice(motivational_quotes)} ✨\n\n"
        
        weekday = datetime.now().strftime('%A')
        if weekday in schedule_dict:
            message += "📚 Расписание на сегодня:\n\n"
            for time, lesson in schedule_dict[weekday]:
                message += f"⏰ {time} - 📖 {lesson}\n"
            message += "\n🎯 Удачного учебного дня! 🌟"
        else:
            message += "🎉 Сегодня выходной! Отличного отдыха! ✨"
        
        image_path = get_random_image()
        if image_path:
            await context.bot.send_photo(
                chat_id=context._chat_id,
                photo=open(image_path, 'rb'),
                caption=message
            )
        else:
            await context.bot.send_message(
                chat_id=context._chat_id,
                text=message
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке утреннего сообщения: {e}")

async def send_lesson_notification(context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Отправка уведомления перед уроком"""
    try:
        if not hasattr(context, '_chat_id'):
            logger.error("Chat ID не найден")
            return

        weekday = datetime.now().strftime('%A')
        current_time = datetime.now().strftime('%H:%M')
        
        if weekday in schedule_dict:
            for time, lesson in schedule_dict[weekday]:
                lesson_time = datetime.strptime(time, '%H:%M').time()
                notification_time = (lesson_time - timedelta(minutes=5)).strftime('%H:%M')
                
                if current_time == notification_time:
                    message = f"⏰ Через 5 минут начинается урок!\n\n📚 {lesson}\n⏱ Начало в {time}"
                    await context.bot.send_message(
                        chat_id=context._chat_id,
                        text=message
                    )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о уроке: {e}")

class ChatIdStore:
    def __init__(self):
        self.chat_ids = set()
        self.filename = 'chat_ids.txt'
        self.load_chat_ids()

    def add_chat_id(self, chat_id):
        self.chat_ids.add(chat_id)
        self.save_chat_ids()

    def get_chat_ids(self):
        return self.chat_ids

    def load_chat_ids(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    self.chat_ids = set(int(line.strip()) for line in f if line.strip())
        except Exception as e:
            logger.error(f"Ошибка при загрузке chat_ids: {e}")

    def save_chat_ids(self):
        try:
            with open(self.filename, 'w') as f:
                for chat_id in self.chat_ids:
                    f.write(f"{chat_id}\n")
        except Exception as e:
            logger.error(f"Ошибка при сохранении chat_ids: {e}")

chat_id_store = ChatIdStore()

async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать расписание на сегодня или указанный день"""
    weekday = datetime.now().strftime('%A')
    message = "🎯 Расписание уроков:\n\n"
    
    if len(context.args) > 0:
        day = context.args[0].capitalize()
        if day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            weekday = day
        else:
            await update.message.reply_text(
                "⚠️ Пожалуйста, укажи день недели на английском:\n\n"
                "✨ Monday - Понедельник\n"
                "✨ Tuesday - Вторник\n"
                "✨ Wednesday - Среда\n"
                "✨ Thursday - Четверг\n"
                "✨ Friday - Пятница"
            )
            return
    
    if weekday in schedule_dict:
        message += f"📅 День: {weekday}\n\n"
        for time, lesson in schedule_dict[weekday]:
            message += f"⏰ {time} - 📚 {lesson}\n"
    else:
        message += "🌟 Сегодня выходной день! Отдыхаем! 🎉"
    
    await update.message.reply_text(message)

async def week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает расписание на всю неделю"""
    message = "🗓 Расписание на неделю:\n\n"
    
    for day, lessons in schedule_dict.items():
        message += f"✨ {day}\n"
        for time, subject in lessons:
            message += f"⏰ {time} - 📚 {subject}\n"
        message += "\n"
    
    if len(message) > 4096:
        parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    try:
        chat_id = update.effective_chat.id
        add_chat(chat_id)
  
        message = (
            "👋 Привет! Я бот для управления расписанием.\n\n"
            "📚 Доступные команды:\n"
            "• /week - показать расписание на всю неделю\n"
            "• /current - информация о текущем уроке\n"
            "• /break - информация о перемене\n"
            "• /next - информация о следующем уроке\n"
            "• /find предмет - найти уроки по предмету\n"
            "• /stats - статистика по предметам\n"
            "• /homework - показать домашнее задание\n"
            "• /homework_add - добавить домашнее задание\n"
            "• /homework_del - удалить домашнее задание\n\n"
            "📝 Работа с ответами:\n"
            "• /get_answer предмет - получить ответы по предмету\n"
            "• /list_answer - список предметов с ответами\n"
            "👨‍💼 Команды администратора:\n"
            "• /add_answer предмет - добавить ответы для предмета\n"
            "• /del_answer предмет - удалить ответы для предмета\n"
        )
        
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде start: {e}")
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды")

async def test_morning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Тестовая команда для проверки утреннего сообщения"""
    context._chat_id = update.effective_chat.id
    await send_morning_message(context)
    
async def test_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Тестовая команда для проверки уведомления об уроке"""
    context._chat_id = update.effective_chat.id
    current_time = datetime.now()
    next_lesson = None
    weekday = current_time.strftime('%A')
    
    if weekday in schedule_dict:
        for time, lesson in schedule_dict[weekday]:
            lesson_time = datetime.strptime(time, '%H:%M').time()
            if lesson_time > current_time.time():
                next_lesson = (time, lesson)
                break
        
        if next_lesson:
            message = (
                f"⏰ Внимание! Через 10 минут начинается урок!\n\n"
                f"📚 Предмет: {next_lesson[1]}\n"
                f"⏱ Начало в {next_lesson[0]}\n\n"
                f"✨ Желаю успешного урока! 🌟"
            )
            await context.bot.send_message(
                chat_id=context._chat_id,
                text=message
            )
        else:
            await context.bot.send_message(
                chat_id=context._chat_id,
                text="🌟 На сегодня уроков больше нет!\n\n🎉 Можно отдыхать! ✨"
            )
    else:
        await context.bot.send_message(
            chat_id=context._chat_id,
            text="🎊 Сегодня выходной день!\n\n✨ Наслаждайся отдыхом! 🌟"
        )

async def next_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о следующем уроке"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    current_time = datetime.now(moscow_tz)
    weekday = current_time.strftime('%A')
    
    if weekday in schedule_dict:
        next_lesson_info = None
        for time, lesson in schedule_dict[weekday]:
            lesson_time = datetime.strptime(time, '%H:%M').time()
            if lesson_time > current_time.time():
                next_lesson_info = (time, lesson)
                break
        
        if next_lesson_info:
            lesson_time = datetime.strptime(next_lesson_info[0], '%H:%M')
            time_until = lesson_time - current_time.replace(microsecond=0)
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            message = (
                f"🎯 Следующий урок:\n\n"
                f"📚 Предмет: {next_lesson_info[1]}\n"
                f"⏰ Начало в {next_lesson_info[0]}\n"
                f"⏳ До начала: {hours} ч. {minutes} мин.\n"
                f"💫 Удачи на уроке! ✨"
            )
        else:
            message = "🌟 На сегодня уроков больше нет!\n\n🎉 Можно отдыхать!"
    else:
        message = "🎊 Сегодня выходной день!\n\n✨ Наслаждайся отдыхом! 🌟"
    
    await update.message.reply_text(message)

def is_bot_running():
    """Проверка, запущен ли уже экземпляр бота"""
    pid_file = "bot.pid"
    try:
        if os.path.exists(pid_file):
            file_age = time.time() - os.path.getmtime(pid_file)
            if file_age > 300:  
                os.remove(pid_file)
                logger.info("Удален устаревший PID файл")
                return False
            
            try:
                with open(pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                    os.remove(pid_file)
                    logger.info("Удален существующий PID файл")
                    return False
            except (ValueError, IOError) as e:
                logger.error(f"Ошибка при чтении PID файла: {e}")
                os.remove(pid_file)
                return False
        
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке запущенных экземпляров: {e}")
        return False

def cleanup():
    """Очистка PID файла при завершении"""
    try:
        pid_file = "bot.pid"
        if os.path.exists(pid_file):
            os.remove(pid_file)
            logger.info("PID файл успешно удален при завершении работы")
    except Exception as e:
        logger.error(f"Ошибка при удалении PID файла: {e}")

async def send_scheduled_message(application: Application) -> None:
    """Обертка для отправки запланированных сообщений"""
    try:
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz)
        weekday = current_time.strftime('%A')
        
        logger.info(f"Проверка расписания: {current_time.strftime('%H:%M')} {weekday}")
        
        
        notification_times = {
            (8, 20): (0, "8:30"),    # Первый урок
            (9, 15): (1, "9:25"),    # Второй урок
            (10, 20): (2, "10:30"),  # Третий урок
            (11, 15): (3, "11:25"),  # Четвертый урок
            (12, 10): (4, "12:20"),  # Пятый урок
            (13, 5): (5, "13:15"),   # Шестой урок
            (14, 10): (6, "14:20")   # Седьмой урок
        }
        
        if current_time.hour == 7 and current_time.minute == 30:
            logger.info("Отправка утреннего сообщения...")
            for chat_id in chat_id_store.get_chat_ids():
                try:
                    context = ContextTypes.DEFAULT_TYPE(application=application)
                    context._chat_id = chat_id
                    await send_morning_message(context)
                    logger.info(f"Утреннее сообщение отправлено для chat_id {chat_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке утреннего сообщения для chat_id {chat_id}: {e}")
        
        current_time_tuple = (current_time.hour, current_time.minute)
        if current_time_tuple in notification_times and weekday in schedule_dict:
            lesson_index, start_time = notification_times[current_time_tuple]
            if lesson_index < len(schedule_dict[weekday]):
                time, lesson = schedule_dict[weekday][lesson_index]
                logger.info(f"Отправка уведомления о уроке {lesson} ({weekday}, {time})")
                
                for chat_id in chat_id_store.get_chat_ids():
                    try:
                        message = (
                            f"⏰ Через 10 минут начинается {lesson_index + 1}-й урок!\n\n"
                            f"📅 {weekday}\n"
                            f"📚 Предмет: {lesson}\n"
                            f"⏱ Начало в {time}\n"
                            f"💫 Удачи на уроке! ✨"
                        )
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=message
                        )
                        logger.info(f"Уведомление о уроке отправлено для chat_id {chat_id}")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления об уроке для chat_id {chat_id}: {e}")
    
    except Exception as e:
        logger.error(f"Ошибка в send_scheduled_message: {e}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статистику по предметам"""
    subject_count = {}
    total_lessons = 0
    
    for day, lessons in schedule_dict.items():
        for _, subject in lessons:
            subject_count[subject] = subject_count.get(subject, 0) + 1
            total_lessons += 1
    
    sorted_subjects = sorted(subject_count.items(), key=lambda x: x[1], reverse=True)
    
    message = "✨ Статистика по предметам ✨\n\n"
    for subject, count in sorted_subjects:
        percentage = (count / total_lessons) * 100
        message += f"📚 {subject}:\n   {count} уроков ({percentage:.1f}%) {'🌟' * (count // 2)}\n\n"
    
    message += f"🎯 Всего {total_lessons} уроков в неделю! 🎉"
    await update.message.reply_text(message)

async def find_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск уроков по предмету"""
    if not context.args:
        await update.message.reply_text(
            "✨ Как использовать поиск:\n\n"
            "🔍 Напиши: /find [название предмета]\n"
            "📝 Например: /find Математика\n\n"
            "💫 И я найду все уроки по этому предмету!"
        )
        return
    
    search_term = ' '.join(context.args).lower()
    found_lessons = []
    
    for day, lessons in schedule_dict.items():
        for time, subject in lessons:
            if search_term in subject.lower():
                found_lessons.append((day, time, subject))
    
    if found_lessons:
        message = f"🔍 Результаты поиска '{search_term}':\n\n"
        for day, time, subject in found_lessons:
            message += f"📅 {day}\n⏰ {time} - 📚 {subject}\n\n"
        message += "✨ Удачи в учебе! 🌟"
    else:
        message = f"❌ По запросу '{search_term}' ничего не найдено\n\n💡 Попробуй другой запрос!"
    
    await update.message.reply_text(message)

async def ping_server() -> None:
    """Функция для поддержания бота в активном состоянии"""
    try:
        logger.info("🔄 Пинг для поддержания активности...")
    except Exception as e:
        logger.error(f"Ошибка при отправке пинга: {e}")

def main() -> None:
    """Основная функция запуска бота"""
    try:
        load_answers()
        load_chats()
        is_bot_running()
        
        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("test_morning", test_morning))
        application.add_handler(CommandHandler("test_lesson", test_lesson))
        application.add_handler(CommandHandler("schedule", show_schedule))
        application.add_handler(CommandHandler("week", week_schedule))
        application.add_handler(CommandHandler("next", next_lesson))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("find", find_subject))
        application.add_handler(CommandHandler("add_answer", add_answer))
        application.add_handler(CommandHandler("get_answer", get_answer))
        application.add_handler(CommandHandler("list_answer", list_answers))
        application.add_handler(CommandHandler("del_answer", del_answer))
        application.add_handler(CommandHandler("done", handle_done))

        application.add_handler(MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            handle_answer_input,
            block=False
        ))

        scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
        
        scheduler.add_job(
            send_scheduled_message,
            'cron',
            minute='*',
            args=[application],
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None
        )
        
        scheduler.add_job(
            ping_server,
            'interval',
            minutes=5,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None
        )
        
        scheduler.start()

        logger.info(f"✨ Бот запущен и готов к работе! Текущее время МСК: {datetime.now(pytz.timezone('Europe/Moscow')).strftime('%H:%M:%S')}")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        cleanup()
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    finally:
        cleanup() 