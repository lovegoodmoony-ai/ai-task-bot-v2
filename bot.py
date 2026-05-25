#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Telegram Task Tracker Bot v2.0
С интеграцией Notion, AI-анализом и голосовым вводом
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from threading import Thread
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import anthropic
import requests

# Flask для Render Web Service
from flask import Flask

# Создаём Flask приложение
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running! ✅"

@flask_app.route('/health')
def health():
    return {"status": "ok"}

def run_flask():
    """Запуск Flask в отдельном потоке"""
    port = int(os.environ.get('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')  # Опционально
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', '')  # Опционально
TIMEZONE = 'Europe/Amsterdam'
MORNING_DIGEST_HOUR = 9

# Категории задач
CATEGORIES = [
    'Встречи', 'Личное', 'Работа', 'IPG', 'Китаец', 
    'Сиклисити', 'Синицы', 'Блог', 'Покупки', 'Отдых'
]

# Приоритеты (матрица Эйзенхауэра)
PRIORITIES = {
    'urgent_important': '🔴 Важное и срочное',
    'important': '🟠 Важное, не срочное',
    'urgent': '🟡 Срочное, не важное',
    'low': '🟢 Не важное, не срочное'
}

# Хранилище данных
class TaskStorage:
    def __init__(self):
        self.file_path = 'tasks.json'
        self.data = self.load()
    
    def load(self) -> Dict:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
        return {}
    
    def save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def get_user_tasks(self, user_id: int) -> List[Dict]:
        user_key = str(user_id)
        if user_key not in self.data:
            self.data[user_key] = {'tasks': [], 'settings': {}}
        return self.data[user_key]['tasks']
    
    def add_task(self, user_id: int, task: Dict):
        user_key = str(user_id)
        if user_key not in self.data:
            self.data[user_key] = {'tasks': [], 'settings': {}}
        self.data[user_key]['tasks'].append(task)
        self.save()
    
    def complete_task(self, user_id: int, task_id: int):
        tasks = self.get_user_tasks(user_id)
        for task in tasks:
            if task['id'] == task_id:
                task['completed'] = True
                self.save()
                return True
        return False
    
    def delete_task(self, user_id: int, task_id: int):
        user_key = str(user_id)
        tasks = self.get_user_tasks(user_id)
        self.data[user_key]['tasks'] = [t for t in tasks if t['id'] != task_id]
        self.save()

storage = TaskStorage()

# AI Агент для анализа задач
class AITaskAnalyzer:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    async def analyze_task(self, text: str) -> Optional[Dict]:
        try:
            categories_str = ', '.join(CATEGORIES)
            current_time = datetime.now(pytz.timezone(TIMEZONE))
            
            system_prompt = f"""Ты AI-агент для анализа задач. Извлеки из текста:
1. Название задачи (title)
2. Приоритет (priority): urgent_important, important, urgent или low
   - urgent_important: важное И срочное
   - important: важное, но не срочное
   - urgent: срочное, но не важное
   - low: не важное и не срочное
3. Категорию (category): {categories_str}
4. Дедлайн (deadline) в ISO 8601 или null

Текущая дата и время: {current_time.isoformat()}

Верни ТОЛЬКО JSON:
{{
  "title": "название",
  "priority": "urgent_important|important|urgent|low",
  "category": "одна из категорий",
  "deadline": "ISO 8601 или null"
}}"""
            
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": text}]
            )
            
            response_text = message.content[0].text.strip()
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            return json.loads(response_text)
        
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return None

ai_analyzer = AITaskAnalyzer(ANTHROPIC_API_KEY)

# Notion Integration
class NotionIntegration:
    def __init__(self, api_key: str, database_id: str):
        self.api_key = api_key
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    def is_configured(self) -> bool:
        return bool(self.api_key and self.database_id)
    
    async def get_tasks(self) -> List[Dict]:
        """Получить задачи из Notion"""
        if not self.is_configured():
            return []
        
        try:
            url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
            response = requests.post(url, headers=self.headers, json={})
            
            if response.status_code == 200:
                results = response.json().get('results', [])
                tasks = []
                
                for page in results:
                    task = self._parse_notion_page(page)
                    if task:
                        tasks.append(task)
                
                return tasks
        except Exception as e:
            logger.error(f"Notion get tasks error: {e}")
        
        return []
    
    async def create_task(self, task: Dict) -> bool:
        """Создать задачу в Notion"""
        if not self.is_configured():
            return False
        
        try:
            url = "https://api.notion.com/v1/pages"
            
            properties = {
                "Name": {
                    "title": [{"text": {"content": task['title']}}]
                },
                "Priority": {
                    "select": {"name": PRIORITIES.get(task['priority'], 'Низкий')}
                },
                "Category": {
                    "select": {"name": task['category']}
                },
                "Status": {
                    "select": {"name": "To Do"}
                }
            }
            
            if task.get('deadline'):
                properties["Deadline"] = {
                    "date": {"start": task['deadline']}
                }
            
            data = {
                "parent": {"database_id": self.database_id},
                "properties": properties
            }
            
            response = requests.post(url, headers=self.headers, json=data)
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Notion create task error: {e}")
            return False
    
    def _parse_notion_page(self, page: Dict) -> Optional[Dict]:
        """Парсинг страницы Notion в задачу"""
        try:
            props = page.get('properties', {})
            
            title = ''
            if 'Name' in props and props['Name'].get('title'):
                title = props['Name']['title'][0]['text']['content']
            
            priority = 'low'
            if 'Priority' in props and props['Priority'].get('select'):
                priority_name = props['Priority']['select']['name']
                for key, val in PRIORITIES.items():
                    if val == priority_name:
                        priority = key
                        break
            
            category = 'Другое'
            if 'Category' in props and props['Category'].get('select'):
                category = props['Category']['select']['name']
            
            deadline = None
            if 'Deadline' in props and props['Deadline'].get('date'):
                deadline = props['Deadline']['date']['start']
            
            return {
                'id': int(datetime.now().timestamp() * 1000),
                'title': title,
                'priority': priority,
                'category': category,
                'deadline': deadline,
                'completed': False,
                'created_at': page.get('created_time'),
                'notion_id': page['id']
            }
        except Exception as e:
            logger.error(f"Parse Notion page error: {e}")
            return None

notion = NotionIntegration(NOTION_API_KEY, NOTION_DATABASE_ID)

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🤖 <b>Привет! Я AI Task Tracker v2.0</b>

<b>Что я умею:</b>
✅ Добавлять задачи голосом или текстом
🎯 Автоматически определять приоритет и категорию
📅 Синхронизация с Notion
🌅 Утренний дайджест в 9:00
⏰ Напоминания о дедлайнах

<b>Команды:</b>
/help - Справка
/today - Задачи на сегодня
/tomorrow - Задачи на завтра
/week - Задачи на неделю
/all - Все задачи
/notion - Синхронизация с Notion
/stats - Статистика

<b>Просто отправьте:</b>
🎤 Голосовое сообщение
💬 Текст задачи
"""
    await update.message.reply_text(welcome_text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
<b>📖 Справка</b>

<b>Примеры задач:</b>
🎤 "Срочно позвонить китайцу завтра в 15:00"
💬 "Написать пост в блог на следующей неделе"
💬 "Встреча с командой IPG в пятницу"

<b>Категории:</b>
• Встречи • Личное • Работа • IPG
• Китаец • Сиклисити • Синицы • Блог
• Покупки • Отдых

<b>Приоритеты:</b>
🔴 Важное и срочное
🟠 Важное, не срочное
🟡 Срочное, не важное
🟢 Не важное, не срочное

<b>Команды:</b>
/today - Задачи на сегодня
/tomorrow - Задачи на завтра
/week - Задачи на неделю
/notion - Синхронизация с Notion
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

def format_task(task: Dict, show_buttons: bool = True) -> tuple:
    priority_emoji = PRIORITIES.get(task['priority'], '⚪')
    
    text = f"{priority_emoji} <b>{task['title']}</b>\n"
    text += f"📁 {task['category']}\n"
    
    if task.get('deadline'):
        try:
            deadline = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
            deadline_str = deadline.strftime('%d.%m.%Y %H:%M')
            text += f"⏰ {deadline_str}\n"
        except:
            pass
    
    if task.get('completed'):
        text += "✅ <i>Выполнено</i>\n"
    
    keyboard = None
    if show_buttons and not task.get('completed'):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task['id']}"),
                InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{task['id']}")
            ]
        ])
    
    return text, keyboard

async def show_tasks_for_date(update: Update, context: ContextTypes.DEFAULT_TYPE, target_date: datetime):
    user_id = update.effective_user.id
    tasks = storage.get_user_tasks(user_id)
    
    filtered_tasks = []
    for task in tasks:
        if task.get('completed'):
            continue
        
        if task.get('deadline'):
            try:
                deadline = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
                if deadline.date() == target_date.date():
                    filtered_tasks.append(task)
            except:
                pass
    
    date_str = target_date.strftime('%d.%m.%Y')
    
    if not filtered_tasks:
        await update.message.reply_text(f"📅 На {date_str} задач нет", parse_mode='HTML')
        return
    
    priority_order = {'urgent_important': 0, 'important': 1, 'urgent': 2, 'low': 3}
    filtered_tasks.sort(key=lambda x: (
        priority_order.get(x['priority'], 99),
        x.get('deadline', '9999')
    ))
    
    response = f"📅 <b>Задачи на {date_str}:</b>\n\n"
    
    for i, task in enumerate(filtered_tasks, 1):
        task_text, _ = format_task(task, show_buttons=False)
        response += f"{i}. {task_text}\n"
    
    await update.message.reply_text(response, parse_mode='HTML')

async def today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(pytz.timezone(TIMEZONE))
    await show_tasks_for_date(update, context, now)

async def tomorrow_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(pytz.timezone(TIMEZONE))
    tomorrow = now + timedelta(days=1)
    await show_tasks_for_date(update, context, tomorrow)

async def week_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = storage.get_user_tasks(user_id)
    
    now = datetime.now(pytz.timezone(TIMEZONE))
    week_later = now + timedelta(days=7)
    
    filtered_tasks = []
    for task in tasks:
        if task.get('completed'):
            continue
        
        if task.get('deadline'):
            try:
                deadline = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
                if now <= deadline <= week_later:
                    filtered_tasks.append(task)
            except:
                pass
    
    if not filtered_tasks:
        await update.message.reply_text("📅 На неделю задач нет", parse_mode='HTML')
        return
    
    tasks_by_day = {}
    for task in filtered_tasks:
        deadline = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
        day_key = deadline.date()
        if day_key not in tasks_by_day:
            tasks_by_day[day_key] = []
        tasks_by_day[day_key].append(task)
    
    response = "📅 <b>Задачи на неделю:</b>\n\n"
    
    for day in sorted(tasks_by_day.keys()):
        day_str = day.strftime('%d.%m (%a)')
        response += f"<b>{day_str}</b>\n"
        
        for task in tasks_by_day[day]:
            task_text, _ = format_task(task, show_buttons=False)
            response += f"  • {task_text}\n"
        
        response += "\n"
    
    await update.message.reply_text(response, parse_mode='HTML')

async def all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = storage.get_user_tasks(user_id)
    
    active_tasks = [t for t in tasks if not t.get('completed')]
    
    if not active_tasks:
        await update.message.reply_text("✅ У вас нет активных задач!", parse_mode='HTML')
        return
    
    tasks_by_category = {}
    for task in active_tasks:
        cat = task['category']
        if cat not in tasks_by_category:
            tasks_by_category[cat] = []
        tasks_by_category[cat].append(task)
    
    response = "📋 <b>Все активные задачи:</b>\n\n"
    
    for category in CATEGORIES:
        if category in tasks_by_category:
            response += f"<b>📁 {category}</b>\n"
            for task in tasks_by_category[category]:
                task_text, _ = format_task(task, show_buttons=False)
                response += f"  • {task_text}\n"
            response += "\n"
    
    await update.message.reply_text(response, parse_mode='HTML')

async def notion_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Синхронизация с Notion"""
    if not notion.is_configured():
        await update.message.reply_text(
            "❌ Notion не настроен.\n\n"
            "Для настройки добавьте переменные окружения:\n"
            "• NOTION_API_KEY\n"
            "• NOTION_DATABASE_ID"
        )
        return
    
    await update.message.reply_text("🔄 Синхронизация с Notion...")
    
    try:
        notion_tasks = await notion.get_tasks()
        user_id = update.effective_user.id
        
        added = 0
        for task in notion_tasks:
            storage.add_task(user_id, task)
            added += 1
        
        await update.message.reply_text(
            f"✅ Синхронизация завершена!\n\n"
            f"Добавлено задач из Notion: {added}"
        )
    except Exception as e:
        logger.error(f"Notion sync error: {e}")
        await update.message.reply_text("❌ Ошибка синхронизации с Notion")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = storage.get_user_tasks(user_id)
    
    total = len(tasks)
    completed = len([t for t in tasks if t.get('completed')])
    active = total - completed
    
    by_category = {}
    for task in tasks:
        if not task.get('completed'):
            cat = task['category']
            by_category[cat] = by_category.get(cat, 0) + 1
    
    by_priority = {}
    for task in tasks:
        if not task.get('completed'):
            pri = task['priority']
            by_priority[pri] = by_priority.get(pri, 0) + 1
    
    response = "📊 <b>Статистика:</b>\n\n"
    response += f"Всего задач: {total}\n"
    response += f"✅ Выполнено: {completed}\n"
    response += f"📝 Активных: {active}\n\n"
    
    if by_priority:
        response += "<b>По приоритетам:</b>\n"
        for pri, count in sorted(by_priority.items(), key=lambda x: list(PRIORITIES.keys()).index(x[0])):
            response += f"{PRIORITIES[pri]}: {count}\n"
        response += "\n"
    
    if by_category:
        response += "<b>По категориям:</b>\n"
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1])[:5]:
            response += f"📁 {cat}: {count}\n"
    
    await update.message.reply_text(response, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    await update.message.reply_text("⏳ Анализирую задачу...")
    
    analyzed = await ai_analyzer.analyze_task(text)
    
    if not analyzed:
        await update.message.reply_text("❌ Не удалось проанализировать. Попробуйте переформулировать.")
        return
    
    task = {
        'id': int(datetime.now().timestamp() * 1000),
        'title': analyzed['title'],
        'priority': analyzed['priority'],
        'category': analyzed['category'],
        'deadline': analyzed['deadline'],
        'completed': False,
        'created_at': datetime.now(pytz.timezone(TIMEZONE)).isoformat()
    }
    
    storage.add_task(user_id, task)
    
    # Синхронизация с Notion если настроено
    if notion.is_configured():
        await notion.create_task(task)
    
    task_text, keyboard = format_task(task)
    response = "✅ <b>Задача добавлена!</b>\n\n" + task_text
    
    if notion.is_configured():
        response += "\n🔗 Синхронизировано с Notion"
    
    await update.message.reply_text(response, parse_mode='HTML', reply_markup=keyboard)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голосовых через Telegram transcription API"""
    await update.message.reply_text("🎤 Распознаю голос...")
    
    try:
        # Получаем транскрипцию от Telegram (если доступна)
        voice = update.message.voice
        
        # Telegram не всегда предоставляет транскрипцию автоматически
        # Поэтому просим пользователя отправить текстом
        await update.message.reply_text(
            "🎤 Голосовое сообщение получено!\n\n"
            "К сожалению, автоматическое распознавание речи временно недоступно.\n"
            "Пожалуйста, отправьте задачу текстом, и я проанализирую её с помощью AI! ✨\n\n"
            "<i>Голосовое распознавание будет добавлено в следующем обновлении.</i>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Voice handling error: {e}")
        await update.message.reply_text("❌ Ошибка обработки голосового сообщения")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith('complete_'):
        task_id = int(data.split('_')[1])
        if storage.complete_task(user_id, task_id):
            await query.edit_message_text(
                query.message.text + "\n\n✅ <b>Выполнено!</b>",
                parse_mode='HTML'
            )
    
    elif data.startswith('delete_'):
        task_id = int(data.split('_')[1])
        storage.delete_task(user_id, task_id)
        await query.edit_message_text("🗑 Задача удалена")

async def send_morning_digest(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Sending morning digests...")
    
    for user_id_str in storage.data.keys():
        try:
            user_id = int(user_id_str)
            tasks = storage.get_user_tasks(user_id)
            
            now = datetime.now(pytz.timezone(TIMEZONE))
            today_tasks = []
            
            for task in tasks:
                if task.get('completed'):
                    continue
                
                if task.get('deadline'):
                    try:
                        deadline = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
                        if deadline.date() == now.date():
                            today_tasks.append(task)
                    except:
                        pass
            
            if not today_tasks:
                continue
            
            priority_order = {'urgent_important': 0, 'important': 1, 'urgent': 2, 'low': 3}
            today_tasks.sort(key=lambda x: (
                priority_order.get(x['priority'], 99),
                x.get('deadline', '9999')
            ))
            
            message = f"🌅 <b>Доброе утро! Задачи на сегодня ({now.strftime('%d.%m.%Y')}):</b>\n\n"
            
            for i, task in enumerate(today_tasks, 1):
                task_text, _ = format_task(task, show_buttons=False)
                message += f"{i}. {task_text}\n"
            
            message += "\n💪 Продуктивного дня!"
            
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error sending digest to {user_id}: {e}")

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Checking reminders...")
    
    for user_id_str in storage.data.keys():
        try:
            user_id = int(user_id_str)
            tasks = storage.get_user_tasks(user_id)
            
            now = datetime.now(pytz.timezone(TIMEZONE))
            
            for task in tasks:
                if task.get('completed') or task.get('reminded'):
                    continue
                
                if task.get('deadline'):
                    try:
                        deadline = datetime.fromisoformat(task['deadline'].replace('Z', '+00:00'))
                        time_diff = deadline - now
                        
                        if timedelta(minutes=45) <= time_diff <= timedelta(minutes=75):
                            task_text, _ = format_task(task, show_buttons=False)
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"⏰ <b>Напоминание!</b>\n\nЧерез час:\n{task_text}",
                                parse_mode='HTML'
                            )
                            task['reminded'] = True
                            storage.save()
                        
                    except Exception as e:
                        logger.error(f"Error processing task deadline: {e}")
                        
        except Exception as e:
            logger.error(f"Error checking reminders for {user_id}: {e}")

def main():
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        logger.error("Missing required environment variables!")
        return
    
    # Запускаем Flask в отдельном потоке для Render
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_tasks))
    app.add_handler(CommandHandler("tomorrow", tomorrow_tasks))
    app.add_handler(CommandHandler("week", week_tasks))
    app.add_handler(CommandHandler("all", all_tasks))
    app.add_handler(CommandHandler("notion", notion_sync))
    app.add_handler(CommandHandler("stats", stats))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("Bot started!")
    
    # Примечание: Утренний дайджест и напоминания временно отключены
    # Используйте команды /today и /tomorrow для просмотра задач
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

