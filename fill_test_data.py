# fill_test_data.py - Расширенная версия
import asyncio
from datetime import datetime, timedelta
from db import SessionLocal, User, Course, Material, Activity
from passlib.context import CryptContext
import random

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def fill_with_sample_data():
    """Заполнение базы тестовыми данными"""
    async with SessionLocal() as db:
        # Создаем пользователей
        users_data = [
            {"name": "Иван Иванов", "email": "ivan@example.com", "role": "teacher"},
            {"name": "Анна Петрова", "email": "anna@example.com", "role": "student"},
            {"name": "Петр Сидоров", "email": "petr@example.com", "role": "student"},
            {"name": "Мария Смирнова", "email": "maria@example.com", "role": "admin"},
            {"name": "Алексей Козлов", "email": "alexey@example.com", "role": "teacher"},
            {"name": "Елена Волкова", "email": "elena@example.com", "role": "student"},
        ]
        
        users = []
        for user_data in users_data:
            user = User(
                name=user_data["name"],
                email=user_data["email"],
                role=user_data["role"],
                password_hash=pwd_context.hash("password123")
            )
            users.append(user)
        
        db.add_all(users)
        await db.commit()
        
        # Обновляем объекты пользователей
        for user in users:
            await db.refresh(user)
        
        # Создаем курсы
        teachers = [user for user in users if user.role == "teacher"]
        courses_data = [
            {
                "title": "Python для начинающих",
                "description": "Изучите основы программирования на Python с нуля",
                "category": "Программирование",
                "level": "beginner",
                "teacher_id": teachers[0].id
            },
            {
                "title": "Data Science и машинное обучение",
                "description": "Анализ данных и построение ML моделей",
                "category": "Аналитика",
                "level": "intermediate",
                "teacher_id": teachers[0].id
            },
            {
                "title": "Веб-разработка с FastAPI",
                "description": "Создание современных API с помощью FastAPI",
                "category": "Программирование",
                "level": "intermediate",
                "teacher_id": teachers[1].id
            },
            {
                "title": "Математический анализ",
                "description": "Основы математического анализа для программистов",
                "category": "Математика",
                "level": "beginner",
                "teacher_id": teachers[0].id
            },
            {
                "title": "История технологий",
                "description": "Развитие информационных технологий",
                "category": "Гуманитарные науки",
                "level": "beginner",
                "teacher_id": teachers[1].id
            }
        ]
        
        courses = []
        for course_data in courses_data:
            course = Course(**course_data)
            courses.append(course)
        
        db.add_all(courses)
        await db.commit()
        
        # Обновляем объекты курсов
        for course in courses:
            await db.refresh(course)
        
        # Создаем материалы
        materials_data = [
            # Python для начинающих
            {"course_id": courses[0].id, "title": "Введение в Python", "type": "video", "order_index": 1},
            {"course_id": courses[0].id, "title": "Переменные и типы данных", "type": "text", "order_index": 2},
            {"course_id": courses[0].id, "title": "Практика: первая программа", "type": "assignment", "order_index": 3},
            {"course_id": courses[0].id, "title": "Тест по основам Python", "type": "quiz", "order_index": 4},
            
            # Data Science
            {"course_id": courses[1].id, "title": "Введение в Data Science", "type": "video", "order_index": 1},
            {"course_id": courses[1].id, "title": "Работа с pandas", "type": "text", "order_index": 2},
            {"course_id": courses[1].id, "title": "Анализ данных проекта", "type": "assignment", "order_index": 3},
            
            # FastAPI
            {"course_id": courses[2].id, "title": "Основы FastAPI", "type": "video", "order_index": 1},
            {"course_id": courses[2].id, "title": "Создание API endpoints", "type": "text", "order_index": 2},
            {"course_id": courses[2].id, "title": "Проект: TODO API", "type": "assignment", "order_index": 3},
            
            # Математика
            {"course_id": courses[3].id, "title": "Основы алгебры", "type": "text", "order_index": 1},
            {"course_id": courses[3].id, "title": "Функции и пределы", "type": "video", "order_index": 2},
            
            # История технологий
            {"course_id": courses[4].id, "title": "Развитие компьютеров", "type": "text", "order_index": 1},
            {"course_id": courses[4].id, "title": "Интернет и web", "type": "video", "order_index": 2}
        ]
        
        materials = []
        for material_data in materials_data:
            material = Material(**material_data)
            materials.append(material)
        
        db.add_all(materials)
        await db.commit()
        
        # Обновляем объекты материалов
        for material in materials:
            await db.refresh(material)
        
        # Создаем активности студентов
        students = [user for user in users if user.role == "student"]
        activities = []
        
        for student in students:
            # Каждый студент взаимодействует с несколькими материалами
            for _ in range(random.randint(5, 15)):
                material = random.choice(materials)
                action = random.choice(["view", "complete", "start", "pause"])
                
                activity = Activity(
                    user_id=student.id,
                    material_id=material.id,
                    action=action,
                    timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                    duration=random.uniform(5, 120) if action in ["view", "complete"] else None,
                    score=random.uniform(70, 100) if material.type == "quiz" and action == "complete" else None,
                    meta={"device": random.choice(["desktop", "mobile", "tablet"])}
                )
                activities.append(activity)
        
        db.add_all(activities)
        await db.commit()
        
        print(f"Создано:")
        print(f"  - Пользователей: {len(users)}")
        print(f"  - Курсов: {len(courses)}")
        print(f"  - Материалов: {len(materials)}")
        print(f"  - Активностей: {len(activities)}")

if __name__ == "__main__":
    asyncio.run(fill_with_sample_data())
