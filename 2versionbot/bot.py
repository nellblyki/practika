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

# Состояния
WAITING_USERNAME = "waiting_username"
WAITING_PASSWORD = "waiting_password"
WAITING_LESSON_TITLE = "waiting_lesson_title"
WAITING_LESSON_CONTENT = "waiting_lesson_content"
WAITING_CARD_QUESTION = "waiting_card_question"
WAITING_CARD_ANSWER = "waiting_card_answer"
WAITING_TEST_TITLE = "waiting_test_title"
WAITING_TEST_QUESTION = "waiting_test_question"
WAITING_TEST_ANSWER = "waiting_test_answer"
WAITING_CARD_LESSON = "waiting_card_lesson"
WAITING_TEST_LESSON = "waiting_test_lesson"
WAITING_TEST_MORE = "waiting_test_more"
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

# Настройки админ-панели
ADMIN_SETTINGS = {
    'total_subjects': 30,  # Общее количество предметов
    'subjects_per_page': 4,  # Количество предметов на одной странице
    'lessons_per_page': 4,  # Количество уроков на одной странице
    'total_lessons': 10  # Общее количество уроков
}

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
            for user_id, auth_teacher_id in authenticated_users.items():
                if auth_teacher_id == teacher_id:
                    bot.send_message(user_id, f"🎉 Вам предоставлен доступ к предмету '{subject_name}'! Используйте кнопку '📚 Предметы' для просмотра.")
                    break
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
            for user_id, auth_teacher_id in authenticated_users.items():
                if auth_teacher_id == teacher_id:
                    bot.send_message(user_id, f"⚠️ У вас отозван доступ к предмету '{subject_name}'.")
                    break
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
        user_states[message.from_user.id] = "teacher"
        show_subjects(message)
    else:
        bot.send_message(message.chat.id, "Неверное имя пользователя или пароль. Попробуйте снова.")
        user_states[message.from_user.id] = WAITING_USERNAME
        bot.send_message(message.chat.id, "Введите имя пользователя:")

@bot.message_handler(func=lambda message: message.text == "👨‍🎓 Войти как ученик")
def student_login(message):
    """Обработчик входа ученика"""
    user_states[message.from_user.id] = "student"
    show_subjects(message)

def show_teacher_menu(message):
    """Показать меню преподавателя"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 Предметы"))
    markup.add(types.KeyboardButton("Выйти"))
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

def show_subjects(message):
    """Показать список предметов"""
    session = get_session()
    try:
        # Проверяем, является ли пользователь преподавателем
        if message.from_user.id in authenticated_users:
            # Преподаватель видит только предметы, к которым у него есть доступ
            teacher_id = authenticated_users[message.from_user.id]
            subjects = get_teacher_subjects(teacher_id)
        else:
            # Ученик видит все предметы
            subjects = session.query(Subject).all()
        
        if not subjects:
            if message.from_user.id in authenticated_users:
                bot.send_message(message.chat.id, "У вас нет доступа ни к одному предмету. Обратитесь к администратору.")
            else:
                bot.send_message(message.chat.id, "Пока нет доступных предметов.")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = []
        for subject in subjects:
            buttons.append(types.KeyboardButton(f"📚 {subject.name}"))
        
        # Добавляем кнопки по 2 в ряд
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.add(buttons[i], buttons[i + 1])
            else:
                markup.add(buttons[i])
        
        markup.add(types.KeyboardButton("◀️ В главное меню"))
        bot.send_message(message.chat.id, "Выберите предмет:", reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text.startswith("📚") and message.text != "📚 Добавить предмет")
def handle_subject(message):
    """Обработчик выбора предмета"""
    # Проверяем, что пользователь не в состоянии админа или ожидания доступа/отзыва
    if (user_states.get(message.from_user.id) == "admin" or 
        user_states.get(message.from_user.id) == WAITING_ACCESS_SUBJECT or
        user_states.get(message.from_user.id) == WAITING_REVOKE_SUBJECT):
        return
    
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return

    subject_name = message.text[2:]  # Убираем эмодзи
    
    # Сохраняем выбранный предмет
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]["selected_subject"] = subject_name
    
    # Показываем уроки этого предмета
    session = get_session()
    try:
        subject = get_subject_by_name(subject_name)
        if not subject:
            bot.send_message(message.chat.id, "Предмет не найден.")
            return
        
        lessons = session.query(Lesson).filter(Lesson.subject_id == subject.id).all()
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        if not lessons:
            # Если уроков нет, показываем сообщение и кнопку для добавления урока
            bot.send_message(message.chat.id, f"В предмете '{subject.name}' пока нет уроков.")
            markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
            bot.send_message(message.chat.id, f"Выберите действие для предмета '{subject.name}':", reply_markup=markup)
        else:
            # Если уроки есть, показываем их список
            buttons = []
            for lesson in lessons:
                buttons.append(types.KeyboardButton(f"📖 {lesson.title}"))
            
            # Добавляем кнопки по 2 в ряд
            for i in range(0, len(buttons), 2):
                if i + 1 < len(buttons):
                    markup.add(buttons[i], buttons[i + 1])
                else:
                    markup.add(buttons[i])
            
            markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
            bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text.startswith("📖"))
def handle_lesson(message):
    """Обработчик выбора урока"""
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return

    lesson_title = message.text[2:]  # Убираем эмодзи
    
    # Сохраняем выбранный урок
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]["selected_lesson"] = lesson_title
    
    # Проверяем, является ли пользователь преподавателем этого урока
    if message.from_user.id in authenticated_users:
        teacher_id = authenticated_users[message.from_user.id]
        session = get_session()
        try:
            # Получаем выбранный предмет
            selected_subject = user_data[message.from_user.id].get("selected_subject")
            if not selected_subject:
                bot.send_message(message.chat.id, "Ошибка: предмет не выбран.")
                return
            
            # Находим предмет
            subject = get_subject_by_name(selected_subject)
            if not subject:
                bot.send_message(message.chat.id, "Ошибка: предмет не найден.")
                return
            
            # Ищем урок по названию, предмету и преподавателю
            lesson = session.query(Lesson).filter(
                Lesson.title == lesson_title, 
                Lesson.subject_id == subject.id,
                Lesson.teacher_id == teacher_id
            ).first()
            
            if lesson:
                # Преподаватель может редактировать свой урок
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add(types.KeyboardButton("📝 Карточки"), types.KeyboardButton("📋 Тесты"))
                markup.add(types.KeyboardButton("✏️ Редактировать урок"), types.KeyboardButton("🗑️ Удалить урок"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"Выбран урок: {lesson_title}. Выберите действие:", reply_markup=markup)
            else:
                # Преподаватель не является владельцем этого урока
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add(types.KeyboardButton("📝 Карточки"), types.KeyboardButton("📋 Тесты"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"Выбран урок: {lesson_title}. Выберите действие:", reply_markup=markup)
        finally:
            session.close()
    else:
        # Ученик
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("📝 Карточки"), types.KeyboardButton("📋 Тесты"))
        markup.add(types.KeyboardButton("◀️ Назад к урокам"))
        bot.send_message(message.chat.id, f"Выбран урок: {lesson_title}. Выберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📚 Добавить предмет")
def add_subject_start(message):
    """Начало процесса добавления предмета - только для администратора"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "Только администратор может добавлять предметы.")
        return

    user_states[message.from_user.id] = WAITING_SUBJECT_NAME
    bot.send_message(message.chat.id, "Введите название предмета:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_SUBJECT_NAME)
def handle_subject_name(message):
    """Обработчик ввода названия предмета"""
    if message.from_user.id != ADMIN_ID:
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
    """Начало процесса добавления урока"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    # Проверяем, есть ли выбранный предмет
    user_id = message.from_user.id
    if user_id in user_data and "selected_subject" in user_data[user_id]:
        # Есть выбранный предмет, сразу запрашиваем название урока
        subject_name = user_data[user_id]["selected_subject"]
        user_data[user_id]["subject_name"] = subject_name
        user_states[user_id] = WAITING_LESSON_TITLE
        bot.send_message(message.chat.id, f"Введите название урока для предмета '{subject_name}':")
    else:
        # Нужно выбрать предмет из доступных
        teacher_id = authenticated_users[user_id]
        subjects = get_teacher_subjects(teacher_id)
        
        if not subjects:
            bot.send_message(message.chat.id, "У вас нет доступа ни к одному предмету. Обратитесь к администратору.")
            return
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = []
        for subject in subjects:
            buttons.append(types.KeyboardButton(f"📚 {subject.name}"))
        
        # Добавляем кнопки по 2 в ряд
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.add(buttons[i], buttons[i + 1])
            else:
                markup.add(buttons[i])
        
        markup.add(types.KeyboardButton("◀️ В главное меню"))
        
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
    """Обработчик ввода названия урока"""
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
    """Начало процесса добавления карточки"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    user_id = message.from_user.id
    # Если выбран урок, сразу переходим к вводу вопроса
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

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for lesson in lessons:
        buttons.append(types.KeyboardButton(f"📖 {lesson.title}"))
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.KeyboardButton("◀️ В главное меню"))
    
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

@bot.message_handler(func=lambda message: message.text == "Выйти")
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

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            buttons = []
            for lesson in lessons:
                buttons.append(types.KeyboardButton(f"📖 {lesson.title}"))
            
            # Добавляем кнопки по 2 в ряд
            for i in range(0, len(buttons), 2):
                if i + 1 < len(buttons):
                    markup.add(buttons[i], buttons[i + 1])
                else:
                    markup.add(buttons[i])
            
            markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
            bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
        finally:
            session.close()
    else:
        # Если нет выбранного предмета, возвращаемся к предметам
        show_subjects(message)

@bot.message_handler(func=lambda message: message.text == "◀️ В главное меню" and message.from_user.id == ADMIN_ID)
def admin_return_to_main(message):
    """Возврат в главное меню из панели администратора"""
    user_id = message.from_user.id
    
    # Очищаем данные
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_data:
        del user_data[user_id]
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("👨‍🏫 Войти как преподаватель"), types.KeyboardButton("👨‍🎓 Войти как ученик"))
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📝 Карточки")
def show_lesson_cards(message):
    """Показать карточки урока"""
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return

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
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        if message.from_user.id in authenticated_users:
            # Преподаватель
            if not cards:
                markup.add(types.KeyboardButton("Добавить карточку"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"В уроке '{lesson.title}' пока нет карточек.", reply_markup=markup)
            else:
                response = f"📝 Карточки урока '{lesson.title}':\n\n"
                for i, card in enumerate(cards, 1):
                    if card.answer:
                        response += f"{i}. Вопрос: {card.question}\n   Ответ: {card.answer}\n\n"
                    else:
                        response += f"{i}. {card.question}\n\n"
                markup.add(types.KeyboardButton("Добавить карточку"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, response, reply_markup=markup)
        else:
            # Ученик
            if not cards:
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"В уроке '{lesson.title}' пока нет карточек.", reply_markup=markup)
            else:
                response = f"📝 Карточки урока '{lesson.title}':\n\n"
                for i, card in enumerate(cards, 1):
                    if card.answer:
                        response += f"{i}. Вопрос: {card.question}\n   Ответ: {card.answer}\n\n"
                    else:
                        response += f"{i}. {card.question}\n\n"
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, response, reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == "📋 Тесты")
def show_lesson_tests(message):
    """Показать тесты урока"""
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return

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
        tests = session.query(Test).filter(Test.lesson_id == lesson.id).all()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        if message.from_user.id in authenticated_users:
            # Преподаватель
            if not tests:
                markup.add(types.KeyboardButton("Создать тест"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"В уроке '{lesson.title}' пока нет тестов.", reply_markup=markup)
            else:
                for test in tests:
                    markup.add(types.KeyboardButton(f"📋 {test.title}"))
                markup.add(types.KeyboardButton("Создать тест"))
                # Здесь можно добавить кнопки для редактирования/удаления тестов, если нужно
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"📋 Тесты урока '{lesson.title}':", reply_markup=markup)
        else:
            # Ученик
            if not tests:
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"В уроке '{lesson.title}' пока нет тестов.", reply_markup=markup)
            else:
                for test in tests:
                    markup.add(types.KeyboardButton(f"📋 {test.title}"))
                markup.add(types.KeyboardButton("◀️ Назад к урокам"))
                bot.send_message(message.chat.id, f"📋 Тесты урока '{lesson.title}':", reply_markup=markup)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text.startswith("📋") and message.text != "📋 Тесты" and message.text != "📋 Список преподавателей")
def handle_test_selection(message):
    """Обработчик выбора теста для прохождения"""
    if message.from_user.id not in user_states:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return

    test_title = message.text[2:]  # Убираем эмодзи
    
    session = get_session()
    try:
        test = session.query(Test).filter(Test.title == test_title).first()
        if not test:
            bot.send_message(message.chat.id, "Тест не найден.")
            return
        
        questions = session.query(TestQuestion).filter(TestQuestion.test_id == test.id).all()
        if not questions:
            bot.send_message(message.chat.id, "В этом тесте нет вопросов.")
            return
        
        # Сохраняем информацию о тесте для пользователя
        user_data[message.from_user.id] = {
            "current_test": test.id,
            "current_question": 0,
            "questions": [(q.id, q.question, q.correct_answer) for q in questions],
            "score": 0
        }
        
        # Показываем первый вопрос
        show_test_question(message)
    finally:
        session.close()

def show_test_question(message):
    """Показать текущий вопрос теста"""
    user_id = message.from_user.id
    data = user_data[user_id]
    
    if data["current_question"] >= len(data["questions"]):
        # Тест завершен
        total_questions = len(data["questions"])
        score = data["score"]
        percentage = (score / total_questions) * 100
        
        result_text = f"🎉 Тест завершен!\n\n"
        result_text += f"Правильных ответов: {score} из {total_questions}\n"
        result_text += f"Процент правильных ответов: {percentage:.1f}%\n\n"
        
        if percentage >= 80:
            result_text += "Отлично! 🏆"
        elif percentage >= 60:
            result_text += "Хорошо! 👍"
        else:
            result_text += "Попробуйте еще раз! 📚"
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("◀️ Назад к урокам"))
        bot.send_message(message.chat.id, result_text, reply_markup=markup)
        
        # Очищаем данные теста
        if user_id in user_data:
            del user_data[user_id]
        return
    
    question_id, question_text, correct_answer = data["questions"][data["current_question"]]
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Пропустить вопрос"))
    markup.add(types.KeyboardButton("◀️ Назад к урокам"))
    
    bot.send_message(message.chat.id, f"Вопрос {data['current_question'] + 1}:\n\n{question_text}", reply_markup=markup)
    user_states[user_id] = "answering_test"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "answering_test")
def handle_test_answer(message):
    """Обработчик ответа на вопрос теста"""
    user_id = message.from_user.id
    
    if message.text == "Пропустить вопрос":
        # Переходим к следующему вопросу
        user_data[user_id]["current_question"] += 1
        show_test_question(message)
        return
    
    if message.text == "◀️ Назад к урокам":
        # Отменяем тест
        if user_id in user_data:
            del user_data[user_id]
        user_states[user_id] = "student"
        show_subjects(message)
        return
    
    # Проверяем ответ
    data = user_data[user_id]
    question_id, question_text, correct_answer = data["questions"][data["current_question"]]
    
    if message.text.lower().strip() == correct_answer.lower().strip():
        data["score"] += 1
        bot.send_message(message.chat.id, "✅ Правильно!")
    else:
        bot.send_message(message.chat.id, f"❌ Неправильно. Правильный ответ: {correct_answer}")
    
    # Переходим к следующему вопросу
    data["current_question"] += 1
    show_test_question(message)

@bot.message_handler(func=lambda message: message.text == "Список карточек")
def show_cards_list(message):
    """Показать список карточек преподавателя"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    teacher_id = authenticated_users[message.from_user.id]
    lessons = get_teacher_lessons(teacher_id)
    
    if not lessons:
        bot.send_message(message.chat.id, "У вас пока нет уроков.")
        return

    session = get_session()
    try:
        response = "📝 Ваши карточки:\n\n"
        for lesson in lessons:
            cards = session.query(Card).filter(Card.lesson_id == lesson.id).all()
            if cards:
                response += f"📖 {lesson.title}:\n"
                for i, card in enumerate(cards, 1):
                    response += f"  {i}. {card.question}\n"
                response += "\n"
        
        if response == "📝 Ваши карточки:\n\n":
            response = "У вас пока нет карточек."
        
        bot.send_message(message.chat.id, response)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == "Список тестов")
def show_tests_list(message):
    """Показать список тестов преподавателя"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    teacher_id = authenticated_users[message.from_user.id]
    lessons = get_teacher_lessons(teacher_id)
    
    if not lessons:
        bot.send_message(message.chat.id, "У вас пока нет уроков.")
        return

    session = get_session()
    try:
        response = "📋 Ваши тесты:\n\n"
        for lesson in lessons:
            tests = session.query(Test).filter(Test.lesson_id == lesson.id).all()
            if tests:
                response += f"📖 {lesson.title}:\n"
                for test in tests:
                    questions_count = session.query(TestQuestion).filter(TestQuestion.test_id == test.id).count()
                    response += f"  📋 {test.title} ({questions_count} вопросов)\n"
                response += "\n"
        
        if response == "📋 Ваши тесты:\n\n":
            response = "У вас пока нет тестов."
        
        bot.send_message(message.chat.id, response)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == "👥 Добавить преподавателя")
def admin_add_teacher(message):
    """Добавление преподавателя администратором"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return

    # Инициализируем user_data если его нет
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}

    user_states[message.from_user.id] = WAITING_TEACHER_USERNAME
    bot.send_message(message.chat.id, "Введите имя пользователя для нового преподавателя:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_TEACHER_USERNAME and message.from_user.id == ADMIN_ID)
def admin_handle_teacher_username(message):
    """Обработчик ввода имени пользователя для нового преподавателя (администратор)"""
    username = message.text
    
    # Проверяем, не существует ли уже такой пользователь
    existing_teacher = get_teacher_by_username(username)
    if existing_teacher:
        bot.send_message(message.chat.id, f"Преподаватель с именем пользователя '{username}' уже существует.")
        user_states[message.from_user.id] = "admin"
        admin_panel(message)
        return

    # Инициализируем user_data если его нет
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    
    user_data[message.from_user.id]["new_teacher_username"] = username
    user_states[message.from_user.id] = WAITING_TEACHER_PASSWORD
    bot.send_message(message.chat.id, "Введите пароль для нового преподавателя:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_TEACHER_PASSWORD and message.from_user.id == ADMIN_ID)
def admin_handle_teacher_password(message):
    """Обработчик ввода пароля для нового преподавателя (администратор)"""
    password = message.text
    username = user_data[message.from_user.id]["new_teacher_username"]
    
    try:
        teacher = create_teacher(username=username, password=password)
        bot.send_message(message.chat.id, f"Преподаватель '{username}' успешно создан!")
        user_states[message.from_user.id] = "admin"
        admin_panel(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при создании преподавателя: {str(e)}")
        user_states[message.from_user.id] = "admin"
        admin_panel(message)

@bot.message_handler(func=lambda message: message.text == "📋 Список преподавателей")
def admin_show_teachers(message):
    """Показать список преподавателей администратору"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return

    session = get_session()
    try:
        teachers = session.query(Teacher).all()
        
        if not teachers:
            bot.send_message(message.chat.id, "Пока нет преподавателей.")
            return

        response = "👥 Список преподавателей:\n\n"
        for i, teacher in enumerate(teachers, 1):
            lessons_count = len(get_teacher_lessons(teacher.id))
            response += f"{i}. {teacher.username} ({lessons_count} уроков)\n"
        
        bot.send_message(message.chat.id, response)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def admin_statistics(message):
    """Показать статистику администратору"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return

    session = get_session()
    try:
        teachers_count = session.query(Teacher).count()
        subjects_count = session.query(Subject).count()
        lessons_count = session.query(Lesson).count()
        cards_count = session.query(Card).count()
        tests_count = session.query(Test).count()
        questions_count = session.query(TestQuestion).count()
        
        response = "📊 Статистика системы:\n\n"
        response += f"👥 Преподавателей: {teachers_count}\n"
        response += f"📚 Предметов: {subjects_count}\n"
        response += f"📖 Уроков: {lessons_count}\n"
        response += f"📝 Карточек: {cards_count}\n"
        response += f"📋 Тестов: {tests_count}\n"
        response += f"❓ Вопросов в тестах: {questions_count}\n"
        
        bot.send_message(message.chat.id, response)
    finally:
        session.close()

@bot.message_handler(func=lambda message: message.text == "◀️ В главное меню" and message.from_user.id != ADMIN_ID)
def return_to_main_menu(message):
    """Возврат в главное меню"""
    if message.from_user.id in authenticated_users:
        del authenticated_users[message.from_user.id]
    if message.from_user.id in user_states:
        del user_states[message.from_user.id]
    if message.from_user.id in user_data:
        del user_data[message.from_user.id]
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("👨‍🏫 Войти как преподаватель"), types.KeyboardButton("👨‍🎓 Войти как ученик"))
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Список предметов")
def show_subjects_list(message):
    """Показать список предметов преподавателя"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    subjects = get_all_subjects()
    
    if not subjects:
        bot.send_message(message.chat.id, "Пока нет предметов.")
        return

    response = "📚 Список предметов:\n\n"
    for i, subject in enumerate(subjects, 1):
        lessons_count = len(get_subject_lessons(subject.id))
        response += f"{i}. {subject.name} ({lessons_count} уроков)\n"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(func=lambda message: message.text == "✏️ Редактировать урок")
def edit_lesson_start(message):
    """Начало редактирования урока"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    lesson_title = user_data[message.from_user.id]["selected_lesson"]
    user_data[message.from_user.id]["editing_lesson"] = lesson_title
    user_states[message.from_user.id] = WAITING_EDIT_LESSON_TITLE
    bot.send_message(message.chat.id, f"Введите новое название для урока '{lesson_title}':")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_EDIT_LESSON_TITLE)
def handle_edit_lesson_title(message):
    """Обработчик ввода нового названия урока"""
    new_title = message.text
    lesson_title = user_data[message.from_user.id]["editing_lesson"]
    teacher_id = authenticated_users[message.from_user.id]
    
    # Находим урок
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.title == lesson_title, Lesson.teacher_id == teacher_id).first()
        if lesson:
            lesson.title = new_title
            session.commit()
            bot.send_message(message.chat.id, f"Название урока изменено на '{new_title}'!")
            user_data[message.from_user.id]["selected_lesson"] = new_title
        else:
            bot.send_message(message.chat.id, "Урок не найден.")
    finally:
        session.close()
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
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                if not lessons:
                    bot.send_message(message.chat.id, f"В предмете '{subject.name}' пока нет уроков.")
                    markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
                    bot.send_message(message.chat.id, f"Выберите действие для предмета '{subject.name}':", reply_markup=markup)
                else:
                    buttons = []
                    for lesson in lessons:
                        buttons.append(types.KeyboardButton(f"📖 {lesson.title}"))
                    for i in range(0, len(buttons), 2):
                        if i + 1 < len(buttons):
                            markup.add(buttons[i], buttons[i + 1])
                        else:
                            markup.add(buttons[i])
                    markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
                    bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
            else:
                show_subjects(message)
        finally:
            session.close()
    else:
        show_subjects(message)

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить урок")
def delete_lesson_confirm(message):
    """Подтверждение удаления урока"""
    if message.from_user.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему как преподаватель.")
        return

    lesson_title = user_data[message.from_user.id]["selected_lesson"]
    teacher_id = authenticated_users[message.from_user.id]
    
    # Находим урок
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.title == lesson_title, Lesson.teacher_id == teacher_id).first()
        if lesson:
            # Удаляем урок и все связанные карточки и тесты
            cards = session.query(Card).filter(Card.lesson_id == lesson.id).all()
            for card in cards:
                session.delete(card)
            
            tests = session.query(Test).filter(Test.lesson_id == lesson.id).all()
            for test in tests:
                questions = session.query(TestQuestion).filter(TestQuestion.test_id == test.id).all()
                for question in questions:
                    session.delete(question)
                session.delete(test)
            
            session.delete(lesson)
            session.commit()
            bot.send_message(message.chat.id, f"Урок '{lesson_title}' и все связанные материалы удалены!")
        else:
            bot.send_message(message.chat.id, "Урок не найден.")
    finally:
        session.close()
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
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                if not lessons:
                    bot.send_message(message.chat.id, f"В предмете '{subject.name}' пока нет уроков.")
                    markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
                    bot.send_message(message.chat.id, f"Выберите действие для предмета '{subject.name}':", reply_markup=markup)
                else:
                    buttons = []
                    for lesson in lessons:
                        buttons.append(types.KeyboardButton(f"📖 {lesson.title}"))
                    for i in range(0, len(buttons), 2):
                        if i + 1 < len(buttons):
                            markup.add(buttons[i], buttons[i + 1])
                        else:
                            markup.add(buttons[i])
                    markup.add(types.KeyboardButton("Добавить урок"), types.KeyboardButton("◀️ Назад к предметам"))
                    bot.send_message(message.chat.id, f"Уроки предмета '{subject.name}':", reply_markup=markup)
            else:
                show_subjects(message)
        finally:
            session.close()
    else:
        show_subjects(message)

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
    markup.add(types.KeyboardButton("👥 Доступы преподавателей"), types.KeyboardButton("📚 Доступы предметов"))
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    bot.send_message(message.chat.id, "🔐 Управление доступом к предметам\nВыберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➕ Предоставить доступ")
def grant_access_start(message):
    """Начало процесса предоставления доступа"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    # Получаем список преподавателей
    teachers = get_all_teachers()
    if not teachers:
        bot.send_message(message.chat.id, "Нет доступных преподавателей.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for teacher in teachers:
        buttons.append(types.KeyboardButton(f"👤 {teacher.username}"))
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    
    user_states[message.from_user.id] = WAITING_ACCESS_TEACHER
    bot.send_message(message.chat.id, "Выберите преподавателя для предоставления доступа:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_ACCESS_TEACHER)
def handle_grant_access_teacher(message):
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
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for subject in subjects:
        if subject.id not in teacher_subject_ids:  # Показываем только предметы без доступа
            buttons.append(types.KeyboardButton(f"📚 {subject.name}"))
    
    if not buttons:
        bot.send_message(message.chat.id, f"У преподавателя {teacher_username} уже есть доступ ко всем предметам.")
        user_states[message.from_user.id] = "admin"
        access_management(message)
        return
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    
    user_states[message.from_user.id] = WAITING_ACCESS_SUBJECT
    bot.send_message(message.chat.id, f"Выберите предмет для предоставления доступа преподавателю {teacher_username}:", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "➖ Отозвать доступ")
def revoke_access_start(message):
    """Начало процесса отзыва доступа"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    # Получаем список преподавателей
    teachers = get_all_teachers()
    if not teachers:
        bot.send_message(message.chat.id, "Нет доступных преподавателей.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for teacher in teachers:
        buttons.append(types.KeyboardButton(f"👤 {teacher.username}"))
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    
    user_states[message.from_user.id] = WAITING_REVOKE_TEACHER
    bot.send_message(message.chat.id, "Выберите преподавателя для отзыва доступа:", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_REVOKE_TEACHER)
def handle_revoke_access_teacher(message):
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
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for subject in teacher_subjects:
        buttons.append(types.KeyboardButton(f"📚 {subject.name}"))
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    
    user_states[message.from_user.id] = WAITING_REVOKE_SUBJECT
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
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📚 Доступы предметов")
def show_subject_accesses(message):
    """Показать доступы всех предметов"""
    if message.from_user.id != ADMIN_ID or user_states.get(message.from_user.id) != "admin":
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    subjects = get_all_subjects()
    if not subjects:
        bot.send_message(message.chat.id, "Нет доступных предметов.")
        return
    
    response = "📚 Доступы предметов:\n\n"
    
    for subject in subjects:
        subject_teachers = get_subject_teachers(subject.id)
        response += f"📚 {subject.name}:\n"
        
        if subject_teachers:
            for teacher in subject_teachers:
                response += f"  👤 {teacher.username}\n"
        else:
            response += f"  ❌ Нет преподавателей с доступом\n"
        
        response += "\n"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("◀️ В админ-панель"))
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "◀️ В админ-панель")
def return_to_admin_panel(message):
    """Возврат в админ-панель"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет доступа к этой функции.")
        return
    
    user_states[message.from_user.id] = "admin"
    admin_panel(message)

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