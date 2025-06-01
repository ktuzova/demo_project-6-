# db.py - Улучшенная версия
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON, Index, Text
from datetime import datetime

DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"

engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    email = Column(String(255), unique=True, index=True)
    role = Column(String(20), index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)
    
    courses = relationship('Course', back_populates='teacher')
    activities = relationship('Activity', back_populates='user')

class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)
    level = Column(String(20), index=True)
    teacher_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)
    
    teacher = relationship('User', back_populates='courses')
    materials = relationship('Material', back_populates='course', cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_course_category_level', 'category', 'level'),
    )

class Material(Base):
    __tablename__ = 'materials'
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    title = Column(String(200), nullable=False)
    content = Column(Text)
    type = Column(String(20), index=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    course = relationship('Course', back_populates='materials')
    activities = relationship('Activity', back_populates='material')

class Activity(Base):
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    material_id = Column(Integer, ForeignKey('materials.id'))
    action = Column(String(50), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    duration = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    meta = Column(JSON, nullable=True)
    
    user = relationship('User', back_populates='activities')
    material = relationship('Material', back_populates='activities')
    
    __table_args__ = (
        Index('idx_activity_user_action', 'user_id', 'action'),
        Index('idx_activity_material_timestamp', 'material_id', 'timestamp'),
    )
