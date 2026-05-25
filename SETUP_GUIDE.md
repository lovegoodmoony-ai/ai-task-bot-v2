# 🚀 AI Task Tracker Bot v2.0 - Полная инструкция

## ✨ Новые возможности

- ✅ **AI-анализ задач** через Claude
- ✅ **Интеграция с Notion** - синхронизация задач
- ✅ **Голосовой ввод** (уведомление о получении голосового)
- ✅ **Утренний дайджест** в 9:00
- ✅ **Напоминания** за час до дедлайна
- ✅ **10 категорий** задач
- ✅ **Матрица Эйзенхауэра** (приоритеты)

---

## 📋 Что нужно для запуска

### Обязательно:
1. **Telegram Bot Token** - от @BotFather
2. **Anthropic API Key** - для AI-анализа

### Опционально (для Notion):
3. **Notion API Key** - для синхронизации
4. **Notion Database ID** - ID вашей базы задач

---

## 🔑 Шаг 1: Получение ключей

### 1.1 Telegram Bot Token

1. Найдите **@BotFather** в Telegram
2. Отправьте `/newbot`
3. Придумайте имя и username
4. **Сохраните токен** (строка вида `1234567890:ABC...`)

### 1.2 Anthropic API Key

1. Перейдите: https://console.anthropic.com/
2. Зарегистрируйтесь
3. API Keys → Create Key
4. **Сохраните ключ** (начинается с `sk-ant-api03-`)

### 1.3 Notion Integration (опционально)

#### Создание интеграции:

1. Перейдите: https://www.notion.so/my-integrations
2. Нажмите **"New integration"**
3. Название: "Task Tracker Bot"
4. Associated workspace: выберите ваш workspace
5. Нажмите **Submit**
6. **Скопируйте Internal Integration Token** - это ваш `NOTION_API_KEY`

#### Создание базы данных:

1. Откройте Notion
2. Создайте новую страницу
3. Добавьте **Database** (Table)
4. Назовите: "Tasks"
5. Добавьте следующие свойства (columns):
   - **Name** (Title) - уже есть
   - **Priority** (Select) - варианты: 🔴 Важное и срочное, 🟠 Важное не срочное, 🟡 Срочное не важное, 🟢 Не важное не срочное
   - **Category** (Select) - варианты: Встречи, Личное, Работа, IPG, Китаец, Сиклисити, Синицы, Блог, Покупки, Отдых
   - **Status** (Select) - варианты: To Do, In Progress, Done
   - **Deadline** (Date)

#### Подключение интеграции к базе:

1. Откройте вашу базу данных Tasks
2. Нажмите **"..."** (три точки справа вверху)
3. **Connections** → **Connect to**
4. Выберите вашу интеграцию "Task Tracker Bot"

#### Получение Database ID:

1. Откройте базу данных в браузере
2. URL выглядит так: `https://www.notion.so/123abc...?v=456def...`
3. **Database ID** - это часть между `notion.so/` и `?v=`
4. Например: `https://www.notion.so/12345abcde67890fghij?v=...`
   - Database ID: `12345abcde67890fghij`

---

## 📦 Шаг 2: Подготовка файлов

Вам нужны 4 файла:

1. **bot.py** - основной код бота
2. **requirements.txt** - зависимости
3. **.python-version** - версия Python
4. **README.md** - описание (опционально)

Все файлы я уже создал для вас ⬆️ Скачайте их!

---

## 🌐 Шаг 3: Загрузка на GitHub

1. Зайдите на https://github.com/
2. Создайте **новый репозиторий**:
   - Название: `ai-task-bot` (или любое)
   - Public
   - БЕЗ README, .gitignore
3. Нажмите **"uploading an existing file"**
4. Перетащите все 4 файла
5. **Commit changes**

---

## 🚀 Шаг 4: Деплой на Render

### 4.1 Создание сервиса

1. Откройте https://render.com/
2. Войдите через GitHub
3. **New +** → **Web Service**
4. Подключите репозиторий
5. Настройки:
   - **Name:** `ai-task-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** `Free`

### 4.2 Environment Variables

Добавьте переменные окружения:

**Обязательные:**
```
TELEGRAM_BOT_TOKEN = ваш_токен_от_BotFather
ANTHROPIC_API_KEY = ваш_ключ_от_Anthropic
```

**Опциональные (для Notion):**
```
NOTION_API_KEY = ваш_notion_integration_token
NOTION_DATABASE_ID = ваш_database_id
```

### 4.3 Запуск

1. Нажмите **"Create Web Service"**
2. Ждите 3-5 минут
3. В логах должно появиться: **"Bot started!"** ✅

---

## 🎉 Шаг 5: Использование

### Откройте Telegram

1. Найдите вашего бота
2. Нажмите **Start**
3. Отправьте `/help`

### Примеры использования

**Текстом:**
```
Срочно позвонить китайцу завтра в 15:00
Написать пост в блог на следующей неделе
Встреча IPG в пятницу
```

**Голосовым:**
Отправьте голосовое сообщение (бот пока попросит написать текстом, но получит уведомление)

**Команды:**
- `/today` - задачи на сегодня
- `/tomorrow` - задачи на завтра
- `/week` - задачи на неделю
- `/all` - все задачи
- `/notion` - синхронизация с Notion
- `/stats` - статистика

---

## 🔗 Notion Sync

Если настроили Notion:

1. Добавляйте задачи в бота - они **автоматически** появятся в Notion
2. Команда `/notion` - загрузит задачи **из Notion в бота**

---

## ⚙️ Настройка

### Изменить время утреннего дайджеста

В `bot.py` найдите:
```python
MORNING_DIGEST_HOUR = 9  # Измените на нужное
```

### Изменить часовой пояс

В `bot.py` найдите:
```python
TIMEZONE = 'Europe/Amsterdam'  # Ваш timezone
```

### Добавить категории

В `bot.py` найдите:
```python
CATEGORIES = [
    'Встречи', 'Личное', 'Работа',
    # Добавьте свои
]
```

---

## ❓ Решение проблем

### Бот не отвечает
- Проверьте логи на Render
- Убедитесь что Environment Variables заданы

### AI не работает
- Проверьте `ANTHROPIC_API_KEY`
- Убедитесь что есть кредиты на аккаунте Anthropic

### Notion не синхронизируется
- Проверьте что интеграция подключена к базе
- Database ID правильный
- Свойства базы совпадают с кодом

### Python 3.14 ошибки
- Файл `.python-version` должен быть в репозитории
- Render должен использовать Python 3.11.9

---

## 💡 Дополнительные возможности

### В следующих версиях:

- 🎤 Полноценное распознавание голоса
- 📊 Графики и аналитика
- 🔔 Кастомные напоминания
- 🤝 Работа в группах
- 📱 PWA версия

---

## 📞 Поддержка

Если что-то не работает:
1. Проверьте логи в Render
2. Убедитесь все ключи правильные
3. Проверьте что файлы загружены на GitHub

---

## 🎊 Готово!

Ваш AI-бот готов к работе! 

**Полезные ссылки:**
- Render: https://dashboard.render.com/
- Anthropic: https://console.anthropic.com/
- Notion: https://www.notion.so/my-integrations
- Telegram BotFather: @BotFather

Удачи! 🚀
