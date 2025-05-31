import asyncio
from datetime import datetime
from db import engine, SessionLocal, User, Course, Material
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def fill():
    async with SessionLocal() as db:
        # Пользователи
        users = [
            User(name="Иван Иванов", role="teacher", password_hash=pwd_context.hash("pass1")),
            User(name="Анна Петрова", role="student", password_hash=pwd_context.hash("pass2")),
            User(name="Петр Сидоров", role="student", password_hash=pwd_context.hash("pass3")),
            User(name="Мария Смирнова", role="admin", password_hash=pwd_context.hash("adminpass")),
        ]
        db.add_all(users)
        await db.commit()
        await db.refresh(users[0])
        await db.refresh(users[1])
        await db.refresh(users[2])
        await db.refresh(users[3])

        # Курсы
        courses = [
            Course(title="Python для начинающих", category="Программирование", level="beginner", teacher_id=users[0].id),
            Course(title="Data Science", category="Аналитика", level="intermediate", teacher_id=users[0].id),
            Course(title="Математика", category="Математика", level="beginner", teacher_id=users[0].id),
            Course(title="История", category="Гуманитарные науки", level="beginner", teacher_id=users[0].id),
        ]
        db.add_all(courses)
        await db.commit()
        for c in courses:
            await db.refresh(c)

        # Материалы
        materials = [
            Material(course_id=courses[0].id, title="Введение в Python", type="video"),
            Material(course_id=courses[0].id, title="Практика: переменные", type="text"),
            Material(course_id=courses[1].id, title="Введение в Data Science", type="video"),
            Material(course_id=courses[2].id, title="Основы алгебры", type="text"),
        ]
        db.add_all(materials)
        await db.commit()

if __name__ == "__main__":
    asyncio.run(fill()) 