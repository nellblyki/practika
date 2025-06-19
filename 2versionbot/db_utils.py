from typing import List, Optional
from database import get_session, Teacher, Subject, Lesson, Card, TeacherSubject

# Функции для работы с предметами
def add_subject(name: str, description: str = None) -> Subject:
    """Добавление нового предмета"""
    session = get_session()
    try:
        subject = Subject(name=name, description=description)
        session.add(subject)
        session.commit()
        return subject
    finally:
        session.close()

def get_all_subjects() -> List[Subject]:
    """Получение всех предметов"""
    session = get_session()
    try:
        return session.query(Subject).all()
    finally:
        session.close()

def get_subject_by_id(subject_id: int) -> Optional[Subject]:
    """Получение предмета по ID"""
    session = get_session()
    try:
        return session.query(Subject).filter(Subject.id == subject_id).first()
    finally:
        session.close()

def get_subject_by_name(name: str) -> Optional[Subject]:
    """Получение предмета по названию"""
    session = get_session()
    try:
        return session.query(Subject).filter(
            Subject.name.ilike(name.strip())
        ).first()
    finally:
        session.close()

# Функции для работы с преподавателями
def create_teacher(username: str, password: str) -> Teacher:
    """Создание нового преподавателя"""
    session = get_session()
    try:
        teacher = Teacher(username=username)
        teacher.set_password(password)
        session.add(teacher)
        session.commit()
        return teacher
    finally:
        session.close()

def get_teacher_by_username(username: str) -> Optional[Teacher]:
    """Получение преподавателя по имени пользователя"""
    session = get_session()
    try:
        return session.query(Teacher).filter(Teacher.username == username).first()
    finally:
        session.close()

# Функции для работы с уроками
def add_lesson(title: str, content: str, teacher_id: int, subject_id: int) -> Lesson:
    """Добавление нового урока"""
    session = get_session()
    try:
        lesson = Lesson(title=title, content=content, teacher_id=teacher_id, subject_id=subject_id)
        session.add(lesson)
        session.commit()
        return lesson
    finally:
        session.close()

def get_teacher_lessons(teacher_id: int) -> List[Lesson]:
    """Получение уроков преподавателя"""
    session = get_session()
    try:
        return session.query(Lesson).filter(Lesson.teacher_id == teacher_id).all()
    finally:
        session.close()

def get_subject_lessons(subject_id: int) -> List[Lesson]:
    """Получение уроков предмета"""
    session = get_session()
    try:
        return session.query(Lesson).filter(Lesson.subject_id == subject_id).all()
    finally:
        session.close()

def edit_lesson(lesson_id: int, title: str, content: str) -> Optional[Lesson]:
    """Редактирование урока"""
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if lesson:
            lesson.title = title
            lesson.content = content
            session.commit()
        return lesson
    finally:
        session.close()

def delete_lesson(lesson_id: int) -> bool:
    """Удаление урока"""
    session = get_session()
    try:
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if lesson:
            session.delete(lesson)
            session.commit()
            return True
        return False
    finally:
        session.close()

# Функции для работы с карточками
def add_card(question: str, answer: str, lesson_id: int) -> Card:
    """Добавление новой карточки"""
    session = get_session()
    try:
        card = Card(question=question, answer=answer, lesson_id=lesson_id)
        session.add(card)
        session.commit()
        return card
    finally:
        session.close()

def get_lesson_cards(lesson_id: int) -> List[Card]:
    """Получение карточек урока"""
    session = get_session()
    try:
        return session.query(Card).filter(Card.lesson_id == lesson_id).all()
    finally:
        session.close()

def edit_card(card_id: int, question: str, answer: str) -> Optional[Card]:
    """Редактирование карточки"""
    session = get_session()
    try:
        card = session.query(Card).filter(Card.id == card_id).first()
        if card:
            card.question = question
            card.answer = answer
            session.commit()
        return card
    finally:
        session.close()

def delete_card(card_id: int) -> bool:
    """Удаление карточки"""
    session = get_session()
    try:
        card = session.query(Card).filter(Card.id == card_id).first()
        if card:
            session.delete(card)
            session.commit()
            return True
        return False
    finally:
        session.close()

# Функции для управления доступом преподавателей к предметам
def grant_subject_access(teacher_id: int, subject_id: int) -> bool:
    """Предоставление доступа преподавателя к предмету"""
    session = get_session()
    try:
        # Проверяем, не существует ли уже такая связь
        existing = session.query(TeacherSubject).filter(
            TeacherSubject.teacher_id == teacher_id,
            TeacherSubject.subject_id == subject_id
        ).first()
        
        if existing:
            return False  # Доступ уже предоставлен
        
        teacher_subject = TeacherSubject(teacher_id=teacher_id, subject_id=subject_id)
        session.add(teacher_subject)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        return False
    finally:
        session.close()

def revoke_subject_access(teacher_id: int, subject_id: int) -> bool:
    """Отзыв доступа преподавателя к предмету"""
    session = get_session()
    try:
        teacher_subject = session.query(TeacherSubject).filter(
            TeacherSubject.teacher_id == teacher_id,
            TeacherSubject.subject_id == subject_id
        ).first()
        
        if teacher_subject:
            session.delete(teacher_subject)
            session.commit()
            return True
        else:
            return False
    except Exception as e:
        session.rollback()
        return False
    finally:
        session.close()

def get_teacher_subjects(teacher_id: int) -> List[Subject]:
    """Получение предметов, к которым у преподавателя есть доступ"""
    session = get_session()
    try:
        teacher_subjects = session.query(TeacherSubject).filter(
            TeacherSubject.teacher_id == teacher_id
        ).all()
        
        subject_ids = [ts.subject_id for ts in teacher_subjects]
        return session.query(Subject).filter(Subject.id.in_(subject_ids)).all()
    finally:
        session.close()

def get_subject_teachers(subject_id: int) -> List[Teacher]:
    """Получение преподавателей, имеющих доступ к предмету"""
    session = get_session()
    try:
        teacher_subjects = session.query(TeacherSubject).filter(
            TeacherSubject.subject_id == subject_id
        ).all()
        
        teacher_ids = [ts.teacher_id for ts in teacher_subjects]
        return session.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()
    finally:
        session.close()

def has_subject_access(teacher_id: int, subject_id: int) -> bool:
    """Проверка, есть ли у преподавателя доступ к предмету"""
    session = get_session()
    try:
        teacher_subject = session.query(TeacherSubject).filter(
            TeacherSubject.teacher_id == teacher_id,
            TeacherSubject.subject_id == subject_id
        ).first()
        return teacher_subject is not None
    finally:
        session.close()

def get_all_teachers() -> List[Teacher]:
    """Получение всех преподавателей"""
    session = get_session()
    try:
        return session.query(Teacher).all()
    finally:
        session.close()

def get_teacher_by_id(teacher_id: int) -> Optional[Teacher]:
    """Получение преподавателя по ID"""
    session = get_session()
    try:
        return session.query(Teacher).filter(Teacher.id == teacher_id).first()
    finally:
        session.close() 