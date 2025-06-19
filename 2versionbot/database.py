from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import bcrypt

Base = declarative_base()

class Teacher(Base):
    __tablename__ = 'teachers'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    
    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Subject(Base):
    __tablename__ = 'subjects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    lessons = relationship("Lesson", back_populates="subject", cascade="all, delete-orphan")

class Lesson(Base):
    __tablename__ = 'lessons'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    subject_id = Column(Integer, ForeignKey('subjects.id'))
    
    teacher = relationship("Teacher", backref="lessons")
    subject = relationship("Subject", back_populates="lessons")
    cards = relationship("Card", back_populates="lesson", cascade="all, delete-orphan")

class Card(Base):
    __tablename__ = 'cards'
    
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    lesson_id = Column(Integer, ForeignKey('lessons.id'))
    
    lesson = relationship("Lesson", back_populates="cards")

class TeacherSubject(Base):
    __tablename__ = 'teacher_subjects'
    
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    
    # Связи
    teacher = relationship("Teacher", backref="teacher_subjects")
    subject = relationship("Subject", backref="teacher_subjects")
    
    # Уникальное ограничение: один преподаватель не может быть привязан к одному предмету дважды
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

# Создание базы данных
engine = create_engine('sqlite:///bot_database.db', 
                      connect_args={'check_same_thread': False},
                      pool_pre_ping=True,
                      pool_recycle=300)
Base.metadata.create_all(engine)

# Создание сессии
Session = sessionmaker(bind=engine)

def get_session():
    return Session() 