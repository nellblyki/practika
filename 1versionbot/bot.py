import telebot
from telebot import types
import math

# Инициализация бота
bot = telebot.TeleBot('7898996873:AAGsxvGiivcMSISQOMMO11dQFuUBINPjXII')

# Словари для хранения состояний пользователей
user_pages = {}  # Для хранения текущей страницы предметов
user_states = {}  # Для хранения текущего состояния пользователя
selected_subjects = {}  # Для хранения выбранного предмета
lesson_pages = {}  # Для хранения текущей страницы уроков
selected_lessons = {}  # Для хранения выбранного урока

# Настройки админ-панели
ADMIN_SETTINGS = {
    'total_subjects': 30,  # Общее количество предметов
    'subjects_per_page': 4,  # Количество предметов на одной странице
    'lessons_per_page': 4,  # Количество уроков на одной странице
    'total_lessons': 10  # Общее количество уроков
}

def get_subjects_markup(page=1):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Создаем кнопки для предметов
    start_idx = (page - 1) * ADMIN_SETTINGS['subjects_per_page']
    end_idx = min(start_idx + ADMIN_SETTINGS['subjects_per_page'], ADMIN_SETTINGS['total_subjects'])
    
    buttons = [types.KeyboardButton(f"Предмет {i}") for i in range(start_idx + 1, end_idx + 1)]
    
    # Добавляем кнопки навигации
    if page > 1:
        buttons.append(types.KeyboardButton("⬅️ Предыдущая страница"))
    if end_idx < ADMIN_SETTINGS['total_subjects']:
        buttons.append(types.KeyboardButton("➡️ Следующая страница"))
    
    markup.add(*buttons)
    markup.add(types.KeyboardButton("◀️ В главное меню"))
    return markup

def get_lessons_markup(subject_num, page=1):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Создаем кнопки для уроков
    start_idx = (page - 1) * ADMIN_SETTINGS['lessons_per_page']
    end_idx = min(start_idx + ADMIN_SETTINGS['lessons_per_page'], ADMIN_SETTINGS['total_lessons'])
    
    buttons = [types.KeyboardButton(f"Урок {i}") for i in range(start_idx + 1, end_idx + 1)]
    
    # Добавляем кнопки навигации
    if page > 1:
        buttons.append(types.KeyboardButton("⬅️ Предыдущая страница уроков"))
    if end_idx < ADMIN_SETTINGS['total_lessons']:
        buttons.append(types.KeyboardButton("➡️ Следующая страница уроков"))
    
    markup.add(*buttons)
    markup.add(types.KeyboardButton("◀️ Назад к предметам"))
    return markup

def get_lesson_options_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📝 Карточка")
    btn2 = types.KeyboardButton("📋 Тест")
    markup.add(btn1, btn2)
    markup.add(types.KeyboardButton("◀️ Назад к урокам"))
    return markup

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("👨‍🎓 Войти как ученик")
    btn2 = types.KeyboardButton("👨‍🏫 Войти как преподаватель")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, 
                     f"Привет, {message.from_user.first_name}! В этом боте вы можете узнавать различные термины по урокам в ITHUB",
                     reply_markup=markup)

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, 
                     "Доступные команды:\n"
                     "/start - начать общение\n"
                     "/help - показать это сообщение")

# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def echo(message):
    if message.text == "👨‍🎓 Войти как ученик":
        user_pages[message.chat.id] = 1
        user_states[message.chat.id] = "subjects"
        markup = get_subjects_markup(1)
        bot.send_message(message.chat.id, "Выберите предмет:", reply_markup=markup)
    
    elif message.text == "👨‍🏫 Войти как преподаватель":
        bot.send_message(message.chat.id, "Функционал преподавателя пока не реализован")
    
    elif message.text == "◀️ В главное меню":
        user_states[message.chat.id] = "main"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("👨‍🎓 Войти как ученик")
        btn2 = types.KeyboardButton("👨‍🏫 Войти как преподаватель")
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=markup)
    
    elif message.text.startswith("Предмет "):
        subject_num = int(message.text.split()[1])
        selected_subjects[message.chat.id] = subject_num
        user_states[message.chat.id] = "lessons"
        lesson_pages[message.chat.id] = 1
        markup = get_lessons_markup(subject_num, 1)
        bot.send_message(message.chat.id, f"Выбран предмет {subject_num}. Выберите урок:", reply_markup=markup)
    
    elif message.text.startswith("Урок "):
        lesson_num = int(message.text.split()[1])
        subject_num = selected_subjects.get(message.chat.id, 0)
        selected_lessons[message.chat.id] = lesson_num
        user_states[message.chat.id] = "lesson_options"
        markup = get_lesson_options_markup()
        bot.send_message(message.chat.id, f"Выбран урок {lesson_num} предмета {subject_num}. Выберите действие:", reply_markup=markup)
    
    elif message.text == "📝 Карточка":
        lesson_num = selected_lessons.get(message.chat.id, 0)
        subject_num = selected_subjects.get(message.chat.id, 0)
        bot.send_message(message.chat.id, f"Карточка для урока {lesson_num} предмета {subject_num} пока не создана")
    
    elif message.text == "📋 Тест":
        lesson_num = selected_lessons.get(message.chat.id, 0)
        subject_num = selected_subjects.get(message.chat.id, 0)
        bot.send_message(message.chat.id, f"Тест для урока {lesson_num} предмета {subject_num} пока не создан")
    
    elif message.text == "◀️ Назад к урокам":
        subject_num = selected_subjects.get(message.chat.id, 0)
        user_states[message.chat.id] = "lessons"
        markup = get_lessons_markup(subject_num, lesson_pages.get(message.chat.id, 1))
        bot.send_message(message.chat.id, f"Выберите урок для предмета {subject_num}:", reply_markup=markup)
    
    elif message.text == "◀️ Назад к предметам":
        user_states[message.chat.id] = "subjects"
        markup = get_subjects_markup(user_pages.get(message.chat.id, 1))
        bot.send_message(message.chat.id, "Выберите предмет:", reply_markup=markup)
    
    elif message.text == "⬅️ Предыдущая страница":
        if user_states.get(message.chat.id) == "subjects":
            current_page = user_pages.get(message.chat.id, 1)
            if current_page > 1:
                user_pages[message.chat.id] = current_page - 1
                markup = get_subjects_markup(current_page - 1)
                bot.send_message(message.chat.id, "Выберите предмет:", reply_markup=markup)
    
    elif message.text == "➡️ Следующая страница":
        if user_states.get(message.chat.id) == "subjects":
            current_page = user_pages.get(message.chat.id, 1)
            max_pages = math.ceil(ADMIN_SETTINGS['total_subjects'] / ADMIN_SETTINGS['subjects_per_page'])
            if current_page < max_pages:
                user_pages[message.chat.id] = current_page + 1
                markup = get_subjects_markup(current_page + 1)
                bot.send_message(message.chat.id, "Выберите предмет:", reply_markup=markup)
    
    elif message.text == "⬅️ Предыдущая страница уроков":
        if user_states.get(message.chat.id) == "lessons":
            current_page = lesson_pages.get(message.chat.id, 1)
            if current_page > 1:
                lesson_pages[message.chat.id] = current_page - 1
                subject_num = selected_subjects.get(message.chat.id, 0)
                markup = get_lessons_markup(subject_num, current_page - 1)
                bot.send_message(message.chat.id, f"Выберите урок для предмета {subject_num}:", reply_markup=markup)
    
    elif message.text == "➡️ Следующая страница уроков":
        if user_states.get(message.chat.id) == "lessons":
            current_page = lesson_pages.get(message.chat.id, 1)
            max_pages = math.ceil(ADMIN_SETTINGS['total_lessons'] / ADMIN_SETTINGS['lessons_per_page'])
            if current_page < max_pages:
                lesson_pages[message.chat.id] = current_page + 1
                subject_num = selected_subjects.get(message.chat.id, 0)
                markup = get_lessons_markup(subject_num, current_page + 1)
                bot.send_message(message.chat.id, f"Выберите урок для предмета {subject_num}:", reply_markup=markup)

# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True) 