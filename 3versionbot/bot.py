import telebot
from telebot import types
import math
from database import Teacher, Subject, Lesson, Card, get_session
import os
from dotenv import load_dotenv
from sqlalchemy import func
from db_utils import (
    create_teacher,
    get_teacher_by_username,
    add_subject,
    get_all_subjects,
    get_subject_by_name,
    add_lesson,
    get_teacher_lessons,
    get_subject_lessons,
    edit_lesson,
    delete_lesson,
    add_card,
    get_lesson_cards,
    edit_card,
    delete_card,
    grant_subject_access,
    revoke_subject_access,
    get_teacher_subjects,
    get_subject_teachers,
    has_subject_access,
    get_all_teachers,
    get_teacher_by_id
)

# Загрузка переменных окружения
load_dotenv('tg.env')
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))  # ID администратора из переменных окружения

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Словари для хранения состояний пользователей
authenticated_users = {}  # {user_id: teacher_id}
user_states = {}  # {user_id: state}
user_data = {}  # {user_id: {key: value}}
# Сопоставление teacher_id -> user_id (последний активный чат преподавателя)
teacher_last_chat = {}  # {teacher_id: user_id}

# Состояния
WAITING_USERNAME = "waiting_username"
WAITING_PASSWORD = "waiting_password"
WAITING_LESSON_TITLE = "waiting_lesson_title"
WAITING_LESSON_CONTENT = "waiting_lesson_content"
WAITING_CARD_QUESTION = "waiting_card_question"
WAITING_CARD_ANSWER = "waiting_card_answer"
WAITING_CARD_LESSON = "waiting_card_lesson"
WAITING_LESSON_SUBJECT = "waiting_lesson_subject"
WAITING_SUBJECT_NAME = "waiting_subject_name"
WAITING_TEACHER_USERNAME = "waiting_teacher_username"
WAITING_TEACHER_PASSWORD = "waiting_teacher_password"
WAITING_ADMIN_USERNAME = "waiting_admin_username"
WAITING_ADMIN_PASSWORD = "waiting_admin_password"
WAITING_EDIT_LESSON_TITLE = "waiting_edit_lesson_title"
WAITING_EDIT_LESSON_CONTENT = "waiting_edit_lesson_content"
WAITING_ACCESS_TEACHER = "waiting_access_teacher"
WAITING_ACCESS_SUBJECT = "waiting_access_subject"
WAITING_REVOKE_TEACHER = "waiting_revoke_teacher"
WAITING_REVOKE_SUBJECT = "waiting_revoke_subject"
WAITING_SUGGEST_TERM = "waiting_suggest_term"

# Настройки админ-панели
ADMIN_SETTINGS = {
    'total_subjects': 30,  # Общее количество предметов
    'subjects_per_page': 4,  # Количество предметов на одной странице
    'lessons_per_page': 4,  # Количество уроков на одной странице
    'total_lessons': 10  # Общее количество уроков
}

# Универсальная функция для создания клавиатуры с пагинацией
# buttons: список telebot.types.KeyboardButton
# page: номер страницы (с 0)
# per_page: сколько кнопок на странице (по умолчанию 6)
# extra_buttons: список дополнительных кнопок (например, "Назад")
def create_paginated_keyboard(buttons, page=0, per_page=6, extra_buttons=None):
    # Основные кнопки (максимум 6)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    total = len(buttons)
    start = page * per_page
    end = start + per_page
    page_buttons = buttons[start:end]
    # Добавляем основные кнопки (2 ряда по 3)
    for i in range(0, len(page_buttons), 3):
        row = page_buttons[i:i+3]
        markup.add(*row)
    # Служебные кнопки (пагинация и навигация) — отдельный нижний ряд
    service_buttons = []
    if end < total:
        service_buttons.append(types.KeyboardButton("➡️ Следующая страница"))
    if page > 0:
        service_buttons.append(types.KeyboardButton("⬅️ Предыдущая страница"))
    if extra_buttons:
        service_buttons.extend(extra_buttons)
    if service_buttons:
        markup.add(*service_buttons)
    return markup

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_ACCESS_SUBJECT)
def handle_grant_access_subject(message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        if not message.text.startswith("📚"):
            bot.send_message(message.chat.id, "Пожалуйста, выберите предмет из списка.")
            return
        subject_name = message.text[2:].strip()  # Убираем эмодзи и пробелы
        subject = get_subject_by_name(subject_name)
        if not subject:
            bot.send_message(message.chat.id, "❌ Предмет не найден. Попробуйте ещё раз.")
            return
        teacher_id = user_data.get(message.from_user.id, {}).get("selected_teacher_id")
        if not teacher_id:
            bot.send_message(message.chat.id, "❌ Не удалось определить преподавателя. Начните процедуру заново.")
            user_states[message.from_user.id] = "admin"
            access_management(message)
            return
        teacher = get_teacher_by_id(teacher_id)
        if not teacher:
            bot.send_message(message.chat.id, "❌ Преподаватель не найден.")
            user_states[message.from_user.id] = "admin"
            access_management(message)
            return
        # Предоставляем доступ
        success = grant_subject_access(teacher_id, subject.id)
        if success:
            bot.send_message(message.chat.id, f"✅ Доступ к предмету '{subject_name}' предоставлен преподавателю {teacher.username}!")
            # --- Уведомление преподавателю ---
            notified = False
            for user_id, auth_teacher_id in authenticated_users.items():
                if auth_teacher_id == teacher_id:
                    bot.send_message(user_id, f"🎉 Вам предоставлен доступ к предмету '{subject_name}'! Используйте кнопку '📚 Предметы' для просмотра.")
                    notified = True
                    break
            if not notified:
                chat_id = teacher_last_chat.get(teacher_id)
                if chat_id:
                    bot.send_message(chat_id, f"🎉 Вам предоставлен доступ к предмету '{subject_name}'! Используйте кнопку '📚 Предметы' для просмотра.")
        else:
            bot.send_message(message.chat.id, f"❌ У преподавателя {teacher.username} уже есть доступ к предмету '{subject_name}'.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")
    finally:
        if message.from_user.id in user_data:
            del user_data[message.from_user.id]
        user_states[message.from_user.id] = "admin"
        access_management(message)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_REVOKE_SUBJECT)
def handle_revoke_access_subject(message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        if not message.text.startswith("📚"):
            bot.send_message(message.chat.id, "Пожалуйста, выберите предмет из списка.")
            return
        subject_name = message.text[2:].strip()
        subject = get_subject_by_name(subject_name)
        if not subject:
            bot.send_message(message.chat.id, "❌ Предмет не найден. Попробуйте ещё раз.")
            return
        teacher_id = user_data.get(message.from_user.id, {}).get("selected_teacher_id")
        if not teacher_id:
            bot.send_message(message.chat.id, "❌ Не удалось определить преподавателя. Начните процедуру заново.")
            user_states[message.from_user.id] = "admin"
            access_management(message)
            return
        teacher = get_teacher_by_id(teacher_id)
        if not teacher:
            bot.send_message(message.chat.id, "❌ Преподаватель не найден.")
            user_states[message.from_user.id] = "admin"
            access_management(message)
            return
        # Отзываем доступ
        success = revoke_subject_access(teacher_id, subject.id)
        if success:
            bot.send_message(message.chat.id, f"✅ Доступ к предмету '{subject_name}' отозван у преподавателя {teacher.username}!")
            # --- Уведомление преподавателю ---
            notified = False
            for user_id, auth_teacher_id in authenticated_users.items():
                if auth_teacher_id == teacher_id:
                    bot.send_message(user_id, f"⚠️ У вас отозван доступ к предмету '{subject_name}'.")
                    notified = True
                    break
            if not notified:
                chat_id = teacher_last_chat.get(teacher_id)
                if chat_id:
                    bot.send_message(chat_id, f"⚠️ У вас отозван доступ к предмету '{subject_name}'.")
        else:
            bot.send_message(message.chat.id, f"❌ У преподавателя {teacher.username} нет доступа к предмету '{subject_name}'.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")
    finally:
        if message.from_user.id in user_data:
            del user_data[message.from_user.id]
        user_states[message.from_user.id] = "admin"
        access_management(message)

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("👨‍🏫 Войти как преподаватель"), types.KeyboardButton("👨‍🎓 Войти как ученик"))
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите, как вы хотите войти:", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Панель администратора"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет доступа к панели администратора.")
        return
    
    # Устанавливаем состояние администратора
    user_states[message.from_user.id] = "admin"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👥 Добавить преподавателя"), types.KeyboardButton("📋 Список преподавателей"))
    markup.add(types.KeyboardButton("📚 Добавить предмет"), types.KeyboardButton("🔐 Управление доступом"))
    markup.add(types.KeyboardButton("📊 Статистика"), types.KeyboardButton("◀️ В главное меню"))
    bot.send_message(message.chat.id, "🔧 Панель администратора\nВыберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "👨‍🏫 Войти как преподаватель")
def teacher_login(message):
    """Обработчик входа преподавателя"""
    user_states[message.from_user.id] = WAITING_USERNAME
    bot.send_message(message.chat.id, "Введите имя пользователя:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_USERNAME)
def handle_username(message):
    """Обработчик ввода имени пользователя"""
    user_data[message.from_user.id] = {"username": message.text}
    user_states[message.from_user.id] = WAITING_PASSWORD
    bot.send_message(message.chat.id, "Введите пароль:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_PASSWORD)
def handle_password(message):
    """Обработчик ввода пароля"""
    username = user_data[message.from_user.id]["username"]
    password = message.text
    # Ищем преподавателя в базе данных
    teacher = get_teacher_by_username(username)
    if teacher and teacher.check_password(password):
        authenticated_users[message.from_user.id] = teacher.id  # ID преподавателя из БД
        teacher_last_chat[teacher.id] = message.from_user.id  # Сохраняем последний chat_id для teacher_id
        user_states[message.from_user.id] = "teacher"
        show_subjects(message)
    else:
        bot.send_message(message.chat.id, "Неверное имя пользователя или пароль. Попробуйте снова.")
        user_states[message.from_user.id] = WAITING_USERNAME
        bot.send_message(message.chat.id, "Введите имя пользователя:")

@bot.message_handler(func=lambda message: message.text == "👨‍🎓 Войти как ученик")
def student_login(message):
    """Обработчик входа ученика"""
    # Очищаем все данные пользователя, чтобы не было пересечений с преподавателем
    if message.from_user.id in authenticated_users:
        del authenticated_users[message.from_user.id]
    if message.from_user.id in user_states:
        del user_states[message.from_user.id]
    if message.from_user.id in user_data:
        del user_data[message.from_user.id]
    user_states[message.from_user.id] = "student"
    show_subjects(message)

def show_teacher_menu(message):
    """Показать меню преподавателя"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 Предметы"))
    markup.add(types.KeyboardButton("Выйти"))
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

def show_subjects(message, page=0):
    session = get_session()
    try:
        if message.from_user.id in authenticated_users:
            teacher_id = authenticated_users[message.from_user.id]
            subjects = get_teacher_subjects(teacher_id)
        else:
            subjects = session.query(Subject).all()
        if not subjects:
            if message.from_user.id in authenticated_users:
                bot.send_message(message.chat.id, "У вас нет доступа ни к одному предмету. Обратитесь к администратору.")
            else:
                bot.send_message(message.chat.id, "Пока нет доступных предметов.")
            return
        # Сохраняем список предметов для текущей страницы
        user_data.setdefault(message.from_user.id, {})["subjects_list"] = [s.name for s in subjects]
        user_data[message.from_user.id]["subjects_page"] = page
        buttons = [types.KeyboardButton(f"📚 {subject.name}") for subject in subjects]
        markup = create_paginated_keyboard(buttons, page=page)
        bot.send_message(message.chat.id, "Выберите предмет:", reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text.startswith("📚") and message.text != "📚 Добавить предмет")
def handle_subject(message):
    # Получаем список предметов для текущей страницы
    subjects_list = user_data.get(message.from_user.id, {}).get("subjects_list")
    if subjects_list:
        # Проверяем, что выбранный предмет есть в списке
        subject_name = message.text[2:].strip()
        if subject_name not in subjects_list:
            bot.send_message(message.chat.id, "Предмет не найден (возможно, устарела страница). Пожалуйста, выберите предмет заново.")
            show_subjects(message, page=user_data.get(message.from_user.id, {}).get("subjects_page", 0))
            return
    handle_subject_core(message, page=0)

def handle_subject_core(message, page=0):
    if (user_states.get(message.from_user.id) == "admin" or 
        user_states.get(message.from_user.id) == WAITING_ACCESS_SUBJECT or
        user_states.get(message.from_user.id) == WAITING_REVOKE_SUBJECT):
        return
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return
    subject_name = message.text[2:]
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]["selected_subject"] = subject_name
    session = get_session()
    try:
        subject = get_subject_by_name(subject_name)
        if not subject:
            bot.send_message(message.chat.id, "Предмет не найден.")
            return
        lessons = session.query(Lesson).filter(Lesson.subject_id == subject.id).all()
        # Сохраняем список уроков для текущей страницы
        user_data[message.from_user.id]["lessons_list"] = [l.title for l in lessons]
        user_data[message.from_user.id]["lessons_page"] = page
        buttons = [types.KeyboardButton(f"📖 {lesson.title}") for lesson in lessons]
        markup = create_paginated_keyboard(buttons, page=page)
        if not lessons:
            bot.send_message(message.chat.id, f"В предмете '{subject.name}' пока нет уроков.")
            if message.from_user.id in authenticated_users:
                markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
                bot.send_message(message.chat.id, f"Выберите действие для предмета '{subject.name}':", reply_markup=markup)
            else:
                markup.add(types.KeyboardButton("◀️ Назад к предметам"))
                bot.send_message(message.chat.id, f"", reply_markup=markup)
            return
        else:
            if message.from_user.id in authenticated_users:
                markup = create_paginated_keyboard(buttons, page=page, extra_buttons=[types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам")])
            else:
                markup = create_paginated_keyboard(buttons, page=page, extra_buttons=[types.KeyboardButton("◀️ Назад к предметам")])
            bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text.startswith("📖"))
def handle_lesson(message):
    handle_lesson_core(message, page=0)

def handle_lesson_core(message, page=0):
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return
    lesson_title = message.text[2:]
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]["selected_lesson"] = lesson_title
    if message.from_user.id in authenticated_users:
        teacher_id = authenticated_users[message.from_user.id]
        session = get_session()
        try:
            selected_subject = user_data[message.from_user.id].get("selected_subject")
            if not selected_subject:
                bot.send_message(message.chat.id, "Ошибка: предмет не выбран.")
                return
            subject = get_subject_by_name(selected_subject)
            if not subject:
                bot.send_message(message.chat.id, "Ошибка: предмет не найден.")
                return
            lesson = session.query(Lesson).filter(
                Lesson.title == lesson_title, 
                Lesson.subject_id == subject.id,
                Lesson.teacher_id == teacher_id
            ).first()
            if lesson:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add(types.KeyboardButton("📝 Карточки"))
                markup.add(types.KeyboardButton("✏️ Редактировать урок"), types.KeyboardButton("🗑️ Удалить урок"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"Выбран урок: {lesson_title}. Выберите действие:", reply_markup=markup)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add(types.KeyboardButton("📝 Карточки"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"Выбран урок: {lesson_title}. Выберите действие:", reply_markup=markup)
        finally:
            session.close()
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("📝 Карточки"))
        markup.add(types.KeyboardButton("◀️ Назад к урокам"))
        bot.send_message(message.chat.id, f"Выбран урок: {lesson_title}. Выберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📚 Добавить предмет")
def add_subject_start(message):
    """
    Начало процесса добавления предмета - только для администратора.
    ВАЖНО: По нажатию кнопки ничего не создаётся! Только перевод в состояние ожидания ввода названия.
    """
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "Только администратор может добавлять предметы.")
        return
    # Только переводим в состояние ожидания названия
    user_states[message.from_user.id] = WAITING_SUBJECT_NAME
    bot.send_message(message.chat.id, "Введите название предмета:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_SUBJECT_NAME)
def handle_subject_name(message):
    """
    Обработчик ввода названия предмета. Если пользователь нажал служебную кнопку — отменяем создание и возвращаем в админ-панель.
    """
    if message.from_user.id != ADMIN_ID:
        return
    service_buttons = [
        "📋 Список преподавателей",
        "🔧 Панель администратора",
        "📚 Добавить предмет",
        "📊 Статистика",
        "◀️ В главное меню",
        "🔐 Управление доступом",
        "👥 Добавить преподавателя"
    ]
    if message.text in service_buttons:
        user_states[message.from_user.id] = "admin"
        admin_panel(message)
        return
    subject_name = message.text
    # Проверяем, не существует ли уже такой предмет
    existing_subject = get_subject_by_name(subject_name)
    if existing_subject:
        bot.send_message(message.chat.id, f"Предмет '{subject_name}' уже существует.")
        user_states[message.from_user.id] = "admin"
        admin_panel(message)
        return
    subject = add_subject(name=subject_name)
    bot.send_message(message.chat.id, f"Предмет '{subject_name}' успешно добавлен!")
    user_states[message.from_user.id] = "admin"
    admin_panel(message)

@bot.message_handler(func=lambda message: message.text == "Добавить урок")
def add_lesson_start(message):
    """
    Начало процесса добавления урока.
    ВАЖНО: По нажатию кнопки ничего не создаётся! Только перевод в состояние ожидания ввода названия.
    """
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return
    # Только переводим в состояние ожидания названия урока
    user_id = message.from_user.id
    if user_id in user_data and "selected_subject" in user_data[user_id]:
        subject_name = user_data[user_id]["selected_subject"]
        user_data[user_id]["subject_name"] = subject_name
        user_states[user_id] = WAITING_LESSON_TITLE
        bot.send_message(message.chat.id, f"Введите название урока для предмета '{subject_name}':")
    else:
        teacher_id = authenticated_users[user_id]
        subjects = get_teacher_subjects(teacher_id)
        if not subjects:
            bot.send_message(message.chat.id, "У вас нет доступа ни к одному предмету. Обратитесь к администратору.")
            return
        markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"📚 {subject.name}") for subject in subjects])
        user_states[message.from_user.id] = WAITING_LESSON_SUBJECT
        bot.send_message(message.chat.id, "Выберите предмет для урока:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_LESSON_SUBJECT)
def handle_lesson_subject(message):
    """Обработчик выбора предмета для урока"""
    if not message.text.startswith("📚"):
        bot.send_message(message.chat.id, "Пожалуйста, выберите предмет из списка.")
        return

    subject_name = message.text[2:]
    user_data[message.from_user.id]["subject_name"] = subject_name
    user_states[message.from_user.id] = WAITING_LESSON_TITLE
    bot.send_message(message.chat.id, "Введите название урока:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_LESSON_TITLE)
def handle_lesson_title(message):
    """
    Обработчик ввода названия урока. Если пользователь нажал служебную кнопку — отменяем создание и возвращаем к списку уроков/предметов.
    """
    service_buttons = [
        "◀️ Назад к предметам",
        "Добавить урок",
        "◀️ В главное меню"
    ]
    if message.text in service_buttons:
        user_states[message.from_user.id] = "teacher"
        # Возвращаем к списку уроков выбранного предмета
        user_id = message.from_user.id
        if user_id in user_data and "selected_subject" in user_data[user_id]:
            subject_name = user_data[user_id]["selected_subject"]
            session = get_session()
            try:
                subject = session.query(Subject).filter(Subject.name == subject_name).first()
                if subject:
                    lessons = session.query(Lesson).filter(Lesson.subject_id == subject.id).all()
                    markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"📖 {lesson.title}") for lesson in lessons])
                    if not lessons:
                        bot.send_message(message.chat.id, f"В предмете '{subject.name}' пока нет уроков.")
                        if message.from_user.id in authenticated_users:
                            markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
                            bot.send_message(message.chat.id, f"Выберите действие для предмета '{subject.name}':", reply_markup=markup)
                        else:
                            markup.add(types.KeyboardButton("◀️ Назад к предметам"))
                            bot.send_message(message.chat.id, f"", reply_markup=markup)
                        return
                    else:
                        markup = create_paginated_keyboard(buttons=markup.keyboard[0], extra_buttons=[types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам")])
                        bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
                else:
                    show_subjects(message)
            finally:
                session.close()
        else:
            show_subjects(message)
        return
    teacher_id = authenticated_users[message.from_user.id]
    title = message.text
    subject_name = user_data[message.from_user.id]["subject_name"]
    # Находим предмет по названию
    subject = get_subject_by_name(subject_name)
    if not subject:
        bot.send_message(message.chat.id, "Ошибка: предмет не найден.")
        user_states[message.from_user.id] = "teacher"
        show_teacher_menu(message)
        return
    # Проверяем, есть ли у преподавателя доступ к этому предмету
    if not has_subject_access(teacher_id, subject.id):
        bot.send_message(message.chat.id, "Ошибка: у вас нет доступа к этому предмету.")
        user_states[message.from_user.id] = "teacher"
        show_teacher_menu(message)
        return
    lesson = add_lesson(title=title, content="", teacher_id=teacher_id, subject_id=subject.id)
    bot.send_message(message.chat.id, f"Урок '{title}' успешно добавлен к предмету '{subject_name}'!")
    user_states[message.from_user.id] = "teacher"
    # Очищаем временные данные
    if "subject_name" in user_data[message.from_user.id]:
        user_data[message.from_user.id]["selected_subject"] = user_data[message.from_user.id]["subject_name"]
        del user_data[message.from_user.id]["subject_name"]
    if "selected_lesson" in user_data[message.from_user.id]:
        del user_data[message.from_user.id]["selected_lesson"]
    # Показываем список уроков выбранного предмета
    from types import SimpleNamespace
    fake_message = SimpleNamespace()
    fake_message.chat = message.chat
    fake_message.from_user = message.from_user
    fake_message.text = f"📚 {subject.name}"
    handle_subject(fake_message)

@bot.message_handler(func=lambda message: message.text == "Добавить карточку")
def add_card_start(message):
    """
    Начало процесса добавления карточки.
    ВАЖНО: По нажатию кнопки ничего не создаётся! Только перевод в состояние ожидания ввода вопроса/ответа.
    """
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return
    user_id = message.from_user.id
    if user_id in user_data and "selected_lesson" in user_data[user_id]:
        lesson_title = user_data[user_id]["selected_lesson"]
        user_data[user_id]["lesson_title"] = lesson_title
        user_states[user_id] = WAITING_CARD_QUESTION
        bot.send_message(
            message.chat.id,
            f"Введите вопрос и ответ для карточки по уроку '{lesson_title}':\n\n"
            "- Для одной карточки: Вопрос%Ответ\n"
            "- Для нескольких: Вопрос1%Ответ1;Вопрос2%Ответ2\n"
            "(Вопрос и ответ разделяются %, карточки — ;)")
        return
    teacher_id = authenticated_users[user_id]
    lessons = get_teacher_lessons(teacher_id)
    if not lessons:
        bot.send_message(message.chat.id, "У вас пока нет уроков. Сначала создайте урок.")
        return
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"📖 {lesson.title}") for lesson in lessons])
    user_states[user_id] = WAITING_CARD_LESSON
    bot.send_message(message.chat.id, "Выберите урок для добавления карточки:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_CARD_LESSON)
def handle_card_lesson(message):
    """Обработчик выбора урока для карточки"""
    if not message.text.startswith("📖"):
        bot.send_message(message.chat.id, "Пожалуйста, выберите урок из списка.")
        return

    lesson_title = message.text[2:]
    user_data[message.from_user.id]["lesson_title"] = lesson_title
    user_states[message.from_user.id] = WAITING_CARD_QUESTION
    bot.send_message(message.chat.id, "Введите вопрос для карточки:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_CARD_QUESTION)
def handle_card_question(message):
    """Обработчик ввода вопроса или сразу нескольких карточек"""
    user_id = message.from_user.id
    teacher_id = authenticated_users[user_id]
    lesson_title = user_data[user_id]["lesson_title"]

    text = message.text.strip()
    if ";" in text or "%" in text:
        # Формат: Вопрос%Ответ;Вопрос2%Ответ2
        pairs = [p.strip() for p in text.split(";") if p.strip()]
        added = 0
        lessons = get_teacher_lessons(teacher_id)
        lesson = next((l for l in lessons if l.title == lesson_title), None)
        if lesson:
            for pair in pairs:
                if "%" in pair:
                    q, a = pair.split("%", 1)
                    q, a = q.strip(), a.strip()
                    if q:
                        add_card(question=q, answer=a, lesson_id=lesson.id)
                        added += 1
                else:
                    # Если только вопрос, без ответа
                    q = pair.strip()
                    if q:
                        add_card(question=q, answer="", lesson_id=lesson.id)
                        added += 1
            if added:
                bot.send_message(message.chat.id, f"Добавлено карточек: {added} к уроку '{lesson.title}'!")
            else:
                bot.send_message(message.chat.id, "Не удалось добавить ни одной карточки. Проверьте формат.")
            from types import SimpleNamespace
            fake_message = SimpleNamespace()
            fake_message.chat = message.chat
            fake_message.from_user = message.from_user
            fake_message.text = f"📖 {lesson.title}"
            show_lesson_cards(fake_message)
            return
        else:
            bot.send_message(message.chat.id, "Ошибка: урок не найден.")
            user_states[user_id] = "teacher"
            show_teacher_menu(message)
            return
    else:
        # Обычный режим: ввод вопроса, затем ответа
        user_data[user_id]["question"] = text
        user_states[user_id] = WAITING_CARD_ANSWER
        bot.send_message(message.chat.id, "Введите ответ для карточки:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_CARD_ANSWER)
def handle_card_answer(message):
    """Обработчик ввода ответа карточки"""
    user_id = message.from_user.id
    teacher_id = authenticated_users[user_id]
    lesson_title = user_data[user_id]["lesson_title"]
    question = user_data[user_id]["question"]
    answer = message.text.strip()

    lessons = get_teacher_lessons(teacher_id)
    lesson = next((l for l in lessons if l.title == lesson_title), None)
    if lesson:
        add_card(question=question, answer=answer, lesson_id=lesson.id)
        bot.send_message(message.chat.id, f"Карточка успешно добавлена к уроку '{lesson.title}'!")
        from types import SimpleNamespace
        fake_message = SimpleNamespace()
        fake_message.chat = message.chat
        fake_message.from_user = message.from_user
        fake_message.text = f"📖 {lesson.title}"
        show_lesson_cards(fake_message)
    else:
        bot.send_message(message.chat.id, "Ошибка: урок не найден.")
        user_states[user_id] = "teacher"
        show_teacher_menu(message)

@bot.message_handler(commands=['logout'])
def logout(message):
    """Выход из системы"""
    if message.from_user.id in authenticated_users:
        del authenticated_users[message.from_user.id]
    if message.from_user.id in user_states:
        del user_states[message.from_user.id]
    if message.from_user.id in user_data:
        del user_data[message.from_user.id]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("👨‍🏫 Войти как преподаватель"), types.KeyboardButton("👨‍🎓 Войти как ученик"))
    bot.send_message(message.chat.id, "Вы вышли из системы. Выберите, как вы хотите войти:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "◀️ Назад к предметам")
def return_to_subjects(message):
    """Возврат к списку предметов"""
    user_id = message.from_user.id
    
    # Очищаем данные выбранного предмета
    if user_id in user_data and "selected_subject" in user_data[user_id]:
        del user_data[user_id]["selected_subject"]
    
    show_subjects(message)

@bot.message_handler(func=lambda message: message.text == "◀️ Назад к урокам")
def return_to_lessons(message):
    """Возврат к списку уроков"""
    user_id = message.from_user.id
    
    # Очищаем данные выбранного урока
    if user_id in user_data and "selected_lesson" in user_data[user_id]:
        del user_data[user_id]["selected_lesson"]
    
    # Проверяем, есть ли выбранный предмет
    if user_id in user_data and "selected_subject" in user_data[user_id]:
        # Возвращаемся к урокам выбранного предмета
        subject_name = user_data[user_id]["selected_subject"]
        session = get_session()
        try:
            subject = session.query(Subject).filter(Subject.name == subject_name).first()
            if not subject:
                bot.send_message(message.chat.id, "Предмет не найден.")
                return
            
            lessons = session.query(Lesson).filter(Lesson.subject_id == subject.id).all()
            
            if not lessons:
                bot.send_message(message.chat.id, f"В предмете '{subject.name}' пока нет уроков.")
                return

            markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"📖 {lesson.title}") for lesson in lessons])
            markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
            bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
        finally:
            session.close()
    else:
        # Если нет выбранного предмета, возвращаемся к предметам
        show_subjects(message)

@bot.message_handler(func=lambda message: message.text == "📝 Карточки")
def show_lesson_cards(message, page=0):
    user_id = message.from_user.id
    if user_id not in user_data or "selected_lesson" not in user_data[user_id]:
        bot.send_message(message.chat.id, "Пожалуйста, сначала выберите урок.")
        return
    lesson_title = user_data[user_id]["selected_lesson"]
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.title == lesson_title).first()
        if not lesson:
            bot.send_message(message.chat.id, "Урок не найден.")
            return
        cards = session.query(Card).filter(Card.lesson_id == lesson.id).all()
        if not cards:
            text = f"В уроке '{lesson.title}' пока нет карточек."
        else:
            text = f"Вот карточки этого урока:\n"
            for i, card in enumerate(cards, 1):
                answer = card.answer if card.answer else "(нет ответа)"
                text += f"{i}. {card.question} - {answer}\n"
        # Пагинация: максимум 7 кнопок на странице, включая служебные
        # 1 — "Добавить карточку", 1 — "Назад к урокам", 1 — "Следующая страница" (если есть)
        # Остальные — пары "Редактировать/Удалить"
        max_buttons = 7
        service_buttons = 2 # "Добавить карточку" и "Назад к урокам"
        per_page = (max_buttons - service_buttons) // 2 # по 2 на карточку
        total_pairs = (len(cards) + per_page - 1) // per_page
        page = int(page) if isinstance(page, int) or (isinstance(page, str) and page.isdigit()) else 0
        page = max(0, page)
        user_data[user_id]["cards_page"] = page
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Добавить карточку"))
        if cards:
            start = page * per_page
            end = start + per_page
            for i, card in enumerate(cards[start:end], start + 1):
                markup.add(
                    types.KeyboardButton(f"✏️ Редактировать {i}"),
                    types.KeyboardButton(f"🗑️ Удалить {i}")
                )
        nav_buttons = []
        if (end < len(cards)):
            nav_buttons.append(types.KeyboardButton("➡️ Следующая страница"))
        nav_buttons.append(types.KeyboardButton("◀️ Назад к урокам"))
        markup.add(*nav_buttons)
        bot.send_message(message.chat.id, text, reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text in ["➡️ Следующая страница", "⬅️ Предыдущая страница"])
def handle_cards_pagination(message):
    user_id = message.from_user.id
    # Явно сохраняем выбранный урок, если он был
    if user_id not in user_data:
        user_data[user_id] = {}
    if "selected_lesson" not in user_data[user_id]:
        # Пытаемся восстановить из последнего сообщения, если возможно (или просто не даём переходить)
        bot.send_message(message.chat.id, "Пожалуйста, сначала выберите урок.")
        return
    page = user_data[user_id].get("cards_page", 0)
    if message.text == "➡️ Следующая страница":
        page += 1
    elif message.text == "⬅️ Предыдущая страница":
        page = max(0, page - 1)
    # selected_lesson не сбрасывается
    show_lesson_cards(message, page=page)

@bot.message_handler(func=lambda message: message.text.startswith("🗑️ Удалить "))
def handle_delete_card(message):
    user_id = message.from_user.id
    if user_id not in user_data or "selected_lesson" not in user_data[user_id]:
        bot.send_message(message.chat.id, "Пожалуйста, сначала выберите урок.")
        return
    lesson_title = user_data[user_id]["selected_lesson"]
    page = user_data[user_id].get("cards_page", 0)
    try:
        idx = int(message.text.replace("🗑️ Удалить ", "").strip()) - 1
    except Exception:
        bot.send_message(message.chat.id, "Некорректный номер карточки.")
        return
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.title == lesson_title).first()
        cards = session.query(Card).filter(Card.lesson_id == lesson.id).all()
        if idx < 0 or idx >= len(cards):
            bot.send_message(message.chat.id, "Некорректный номер карточки.")
            return
        card = cards[idx]
        session.delete(card)
        session.commit()
        bot.send_message(message.chat.id, "Карточка успешно удалена!")
    finally:
        session.close()
    # После удаления остаёмся на той же странице (или предыдущей, если удалили последнюю на странице)
    total_pages = (len(cards) - 1 + 7 - 1) // 7
    if page >= total_pages:
        page = max(0, total_pages - 1)
    show_lesson_cards(message, page=page)

@bot.message_handler(func=lambda message: message.text.startswith("✏️ Редактировать "))
def handle_edit_card_start(message):
    user_id = message.from_user.id
    if user_id not in user_data or "selected_lesson" not in user_data[user_id]:
        bot.send_message(message.chat.id, "Пожалуйста, сначала выберите урок.")
        return
    lesson_title = user_data[user_id]["selected_lesson"]
    page = user_data[user_id].get("cards_page", 0)
    try:
        idx = int(message.text.replace("✏️ Редактировать ", "").strip()) - 1
    except Exception:
        bot.send_message(message.chat.id, "Некорректный номер карточки.")
        return
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.title == lesson_title).first()
        cards = session.query(Card).filter(Card.lesson_id == lesson.id).all()
        if idx < 0 or idx >= len(cards):
            bot.send_message(message.chat.id, "Некорректный номер карточки.")
            return
        card = cards[idx]
        user_data[user_id]["edit_card_id"] = card.id
        user_states[user_id] = "waiting_edit_card"
        bot.send_message(message.chat.id, f"Введите новый вопрос и ответ для карточки (формат: Вопрос%Ответ):\nТекущее значение:\n{card.question} - {card.answer}")
    finally:
        session.close()

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_edit_card")
def handle_edit_card(message):
    user_id = message.from_user.id
    card_id = user_data[user_id].get("edit_card_id")
    if not card_id:
        bot.send_message(message.chat.id, "Ошибка: карточка не выбрана.")
        user_states[user_id] = "teacher"
        return
    if "%" not in message.text:
        bot.send_message(message.chat.id, "Неверный формат. Введите в формате: Вопрос%Ответ")
        return
    q, a = message.text.split("%", 1)
    q, a = q.strip(), a.strip()
    session = get_session()
    try:
        card = session.query(Card).filter(Card.id == card_id).first()
        if not card:
            bot.send_message(message.chat.id, "Ошибка: карточка не найдена.")
            user_states[user_id] = "teacher"
            return
        card.question = q
        card.answer = a
        session.commit()
        bot.send_message(message.chat.id, "Карточка успешно отредактирована!")
    finally:
        session.close()
    page = user_data[user_id].get("cards_page", 0)
    user_states[user_id] = "teacher"
    show_lesson_cards(message, page=page)

@bot.message_handler(func=lambda message: message.text == "📚 Предметы")
def handle_teacher_subjects(message):
    """Обработчик кнопки "📚 Предметы" для преподавателя"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    # Показываем доступные предметы из базы данных
    show_subjects(message)

@bot.message_handler(func=lambda message: message.text == "🔐 Управление доступом")
def access_management(message):
    """Управление доступом преподавателей к предметам"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("➕ Предоставить доступ"), types.KeyboardButton("➖ Отозвать доступ"))
    markup.add(types.KeyboardButton("👥 Доступы преподавателей"))
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    bot.send_message(message.chat.id, "🔐 Управление доступом к предметам\nВыберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➕ Предоставить доступ")
def grant_access_start(message, page=0):
    """Начало процесса предоставления доступа"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    # Получаем список преподавателей
    teachers = get_all_teachers()
    if not teachers:
        bot.send_message(message.chat.id, "Нет доступных преподавателей.")
        return
    
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"👤 {teacher.username}") for teacher in teachers])
    
    user_states[message.from_user.id] = WAITING_ACCESS_TEACHER
    user_data.setdefault(message.from_user.id, {})["teachers_page"] = page
    bot.send_message(message.chat.id, "Выберите преподавателя для предоставления доступа:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_ACCESS_TEACHER)
def handle_grant_access_teacher(message, page=0):
    """Обработчик выбора преподавателя для предоставления доступа"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.text.startswith("👤"):
        bot.send_message(message.chat.id, "Пожалуйста, выберите преподавателя из списка.")
        return
    
    teacher_username = message.text[2:]  # Убираем эмодзи
    teacher = get_teacher_by_username(teacher_username)
    
    if not teacher:
        bot.send_message(message.chat.id, "Преподаватель не найден.")
        return
    
    # Сохраняем выбранного преподавателя
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]["selected_teacher_id"] = teacher.id
    
    # Получаем список предметов
    subjects = get_all_subjects()
    if not subjects:
        bot.send_message(message.chat.id, "Нет доступных предметов.")
        return
    
    # Получаем предметы, к которым у преподавателя уже есть доступ
    teacher_subjects = get_teacher_subjects(teacher.id)
    teacher_subject_ids = [s.id for s in teacher_subjects]
    
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"📚 {subject.name}") for subject in subjects if subject.id not in teacher_subject_ids])
    
    if not markup.keyboard[0]:
        bot.send_message(message.chat.id, f"У преподавателя {teacher_username} уже есть доступ ко всем предметам.")
        user_states[message.from_user.id] = "admin"
        access_management(message)
        return
    
    user_states[message.from_user.id] = WAITING_ACCESS_SUBJECT
    user_data.setdefault(message.from_user.id, {})["subjects_access_page"] = page
    bot.send_message(message.chat.id, f"Выберите предмет для предоставления доступа преподавателю {teacher_username}:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➖ Отозвать доступ")
def revoke_access_start(message, page=0):
    """Начало процесса отзыва доступа"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    # Получаем список преподавателей
    teachers = get_all_teachers()
    if not teachers:
        bot.send_message(message.chat.id, "Нет доступных преподавателей.")
        return
    
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"👤 {teacher.username}") for teacher in teachers])
    
    user_states[message.from_user.id] = WAITING_REVOKE_TEACHER
    user_data.setdefault(message.from_user.id, {})["teachers_page"] = page
    bot.send_message(message.chat.id, "Выберите преподавателя для отзыва доступа:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_REVOKE_TEACHER)
def handle_revoke_access_teacher(message, page=0):
    """Обработчик выбора преподавателя для отзыва доступа"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.text.startswith("👤"):
        bot.send_message(message.chat.id, "Пожалуйста, выберите преподавателя из списка.")
        return
    
    teacher_username = message.text[2:]  # Убираем эмодзи
    teacher = get_teacher_by_username(teacher_username)
    
    if not teacher:
        bot.send_message(message.chat.id, "Преподаватель не найден.")
        return
    
    # Получаем предметы, к которым у преподавателя есть доступ
    teacher_subjects = get_teacher_subjects(teacher.id)
    
    if not teacher_subjects:
        bot.send_message(message.chat.id, f"У преподавателя {teacher_username} нет доступа ни к одному предмету.")
        user_states[message.from_user.id] = "admin"
        access_management(message)
        return
    
    # Сохраняем выбранного преподавателя
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]["selected_teacher_id"] = teacher.id
    
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton(f"📚 {subject.name}") for subject in teacher_subjects])
    
    user_states[message.from_user.id] = WAITING_REVOKE_SUBJECT
    user_data.setdefault(message.from_user.id, {})["subjects_access_page"] = page
    bot.send_message(message.chat.id, f"Выберите предмет для отзыва доступа у преподавателя {teacher_username}:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "👥 Доступы преподавателей")
def show_teacher_accesses(message):
    """Показать доступы всех преподавателей"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    teachers = get_all_teachers()
    if not teachers:
        bot.send_message(message.chat.id, "Нет доступных преподавателей.")
        return
    
    response = "👥 Доступы преподавателей:\n\n"
    
    for teacher in teachers:
        teacher_subjects = get_teacher_subjects(teacher.id)
        response += f"👤 {teacher.username}:\n"
        
        if teacher_subjects:
            for subject in teacher_subjects:
                response += f"  ✅ {subject.name}\n"
        else:
            response += f"  ❌ Нет доступа к предметам\n"
        
        response += "\n"
    
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton("◀️ В админ-панель")])
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "◀️ В админ-панель")
def return_to_admin_panel(message):
    """Возврат в админ-панель"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    user_states[message.from_user.id] = "admin"
    admin_panel(message)

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def show_statistics(message):
    """Показать статистику по базе данных (только для администратора)"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    session = get_session()
    try:
        teachers_count = session.query(Teacher).count()
        subjects_count = session.query(Subject).count()
        lessons_count = session.query(Lesson).count()
        cards_count = session.query(Card).count()
        response = (
            f"📊 Статистика:\n\n"
            f"👥 Преподавателей: {teachers_count}\n"
            f"📚 Предметов: {subjects_count}\n"
            f"📖 Уроков: {lessons_count}\n"
            f"📝 Карточек: {cards_count}"
        )
        markup = create_paginated_keyboard(buttons=[types.KeyboardButton("◀️ В админ-панель")])
        bot.send_message(message.chat.id, response, reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == "📋 Список преподавателей")
def show_teachers_list(message):
    """Показать список всех преподавателей (только для администратора)"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    from db_utils import get_all_teachers
    teachers = get_all_teachers()
    if not teachers:
        bot.send_message(message.chat.id, "Нет зарегистрированных преподавателей.")
        return
    response = "📋 Список преподавателей:\n\n"
    for t in teachers:
        response += f"👤 {t.username} (ID: {t.id})\n"
    markup = create_paginated_keyboard(buttons=[types.KeyboardButton("◀️ В админ-панель")])
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "👥 Добавить преподавателя")
def add_teacher_start(message):
    """
    Начало процесса добавления преподавателя (только для администратора).
    """
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    user_states[message.from_user.id] = WAITING_TEACHER_USERNAME
    bot.send_message(message.chat.id, "Введите имя пользователя для нового преподавателя:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_TEACHER_USERNAME)
def handle_new_teacher_username(message):
    if message.from_user.id != ADMIN_ID:
        return
    username = message.text.strip()
    if not username:
        bot.send_message(message.chat.id, "Имя пользователя не может быть пустым. Введите имя пользователя:")
        return
    user_data[message.from_user.id] = {"new_teacher_username": username}
    user_states[message.from_user.id] = WAITING_TEACHER_PASSWORD
    bot.send_message(message.chat.id, f"Введите пароль для преподавателя {username}:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_TEACHER_PASSWORD)
def handle_new_teacher_password(message):
    if message.from_user.id != ADMIN_ID:
        return
    password = message.text.strip()
    username = user_data.get(message.from_user.id, {}).get("new_teacher_username")
    if not username:
        bot.send_message(message.chat.id, "Ошибка: имя пользователя не найдено. Попробуйте снова.")
        user_states[message.from_user.id] = "admin"
        admin_panel(message)
        return
    if not password:
        bot.send_message(message.chat.id, "Пароль не может быть пустым. Введите пароль:")
        return
    # Проверяем, не существует ли уже такой преподаватель
    from db_utils import get_teacher_by_username, create_teacher
    if get_teacher_by_username(username):
        bot.send_message(message.chat.id, f"Преподаватель с именем {username} уже существует.")
        user_states[message.from_user.id] = "admin"
        admin_panel(message)
        return
    create_teacher(username, password)
    bot.send_message(message.chat.id, f"Преподаватель {username} успешно добавлен!")
    user_states[message.from_user.id] = "admin"
    admin_panel(message)

@bot.message_handler(func=lambda message: message.text in ["➡️ Следующая страница", "⬅️ Предыдущая страница"])
def handle_pagination(message):
    user_id = message.from_user.id
    # --- Уроки ---
    if "selected_subject" in user_data.get(user_id, {}):
        page = user_data.get(user_id, {}).get("lessons_page", 0)
        if message.text == "➡️ Следующая страница":
            page += 1
        else:
            page = max(0, page - 1)
        user_data.setdefault(user_id, {})["lessons_page"] = page
        subject_name = user_data[user_id]["selected_subject"]
        from types import SimpleNamespace
        fake_message = SimpleNamespace()
        fake_message.chat = message.chat
        fake_message.from_user = message.from_user
        fake_message.text = f"📚 {subject_name}"
        handle_subject_core(fake_message, page=page)
        return
    state = user_states.get(user_id)
    # --- Предметы ---
    if state in ["teacher", "student"] or (state is None and user_id not in authenticated_users):
        page = user_data.get(user_id, {}).get("subjects_page", 0)
        if message.text == "➡️ Следующая страница":
            page += 1
        else:
            page = max(0, page - 1)
        user_data.setdefault(user_id, {})["subjects_page"] = page
        show_subjects(message, page=page)
        return
    # ... остальные ветки пагинации ...

if __name__ == "__main__":
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"Ошибка: {e}")
            print("Перезапуск через 5 секунд...")
            import time
            time.sleep(5)
            continue 