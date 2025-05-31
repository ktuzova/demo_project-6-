from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON

DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    role = Column(String, index=True)  # 'student' or 'teacher' or 'admin'
    password_hash = Column(String, nullable=False)
    courses = relationship('Course', back_populates='teacher')

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String, index=True)
    level = Column(String, index=True)
    teacher_id = Column(Integer, ForeignKey('users.id'))
    teacher = relationship('User', back_populates='courses')
    materials = relationship('Material', back_populates='course')

class Material(Base):
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    title = Column(String)
    type = Column(String)
    course = relationship('Course', back_populates='materials')

class Activity(Base):
    __tablename__ = 'activities'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    material_id = Column(Integer, ForeignKey('materials.id'))
    action = Column(String)
    timestamp = Column(DateTime)
    duration = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    meta = Column(JSON, nullable=True) 