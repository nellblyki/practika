from database import Teacher, get_session
from typing import Optional

def is_authenticated(user_id: int) -> bool:
    """Проверка аутентификации преподавателя"""
    session = get_session()
    teacher = session.query(Teacher).filter_by(id=user_id).first()
    return bool(teacher)

def get_current_teacher(user_id: int) -> Optional[Teacher]:
    """Получение текущего аутентифицированного преподавателя"""
    session = get_session()
    return session.query(Teacher).filter_by(id=user_id).first() 