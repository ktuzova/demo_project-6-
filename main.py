# main.py - Полная корректная версия
from fastapi import FastAPI, Query, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, and_, func, desc
from collections import Counter
from io import StringIO
import csv
import json

from db import SessionLocal, User as DBUser, Course as DBCourse, Material as DBMaterial, Activity as DBActivity

# Настройки приложения
SECRET_KEY = "your-secret-key-here"  # В продакшене использовать переменные окружения
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

app = FastAPI(
    title="Online Courses Platform",
    description="Educational platform with course management and analytics",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Pydantic модели
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    role: str
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    name: str
    email: str
    role: str = Field(pattern="^(student|teacher|admin)$")
    password: str = Field(min_length=6)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class Course(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: str
    level: str
    teacher_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    level: str = Field(pattern="^(beginner|intermediate|advanced)$")
    teacher_id: int

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    level: Optional[str] = None

class Material(BaseModel):
    id: int
    course_id: int
    title: str
    content: Optional[str] = None
    type: str
    order_index: int = 0

    class Config:
        from_attributes = True

class MaterialCreate(BaseModel):
    course_id: int
    title: str
    content: Optional[str] = None
    type: str = Field(pattern="^(video|text|quiz|assignment)$")
    order_index: int = 0

class MaterialUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[str] = None
    order_index: Optional[int] = None

class Activity(BaseModel):
    id: int
    user_id: int
    material_id: int
    action: str
    timestamp: datetime
    duration: Optional[float] = None
    score: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class ActivityCreate(BaseModel):
    user_id: int
    material_id: int
    action: str
    duration: Optional[float] = None
    score: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None

# Dependency functions
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(DBUser).where(DBUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

def require_role(*roles):
    async def role_checker(current_user: DBUser = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker

# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Authentication endpoints
@app.post("/register", response_model=User)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Проверяем, существует ли пользователь с таким email
    result = await db.execute(select(DBUser).where(DBUser.email == user.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = DBUser(
        name=user.name,
        email=user.email,
        role=user.role,
        password_hash=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBUser).where(DBUser.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

# User management
@app.get("/users", response_model=List[User])
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(require_role("admin", "teacher")),
    skip: int = 0,
    limit: int = 100
):
    result = await db.execute(select(DBUser).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: DBUser = Depends(get_current_user)):
    return current_user

# Course management
@app.get("/courses", response_model=List[Course])
async def get_courses(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    level: Optional[str] = None
):
    stmt = select(DBCourse).offset(skip).limit(limit)
    if category:
        stmt = stmt.where(DBCourse.category == category)
    if level:
        stmt = stmt.where(DBCourse.level == level)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@app.post("/courses", response_model=Course)
async def create_course(
    course: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(require_role("admin", "teacher"))
):
    db_course = DBCourse(**course.dict())
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course

@app.get("/courses/{course_id}", response_model=Course)
async def get_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    result = await db.execute(select(DBCourse).where(DBCourse.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@app.get("/courses/{course_id}/materials", response_model=List[Material])
async def get_course_materials(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    result = await db.execute(
        select(DBMaterial)
        .where(DBMaterial.course_id == course_id)
        .order_by(DBMaterial.order_index)
    )
    return result.scalars().all()

# Material management
@app.get("/materials", response_model=List[Material])
async def get_materials(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
    course_id: Optional[int] = None
):
    stmt = select(DBMaterial)
    if course_id:
        stmt = stmt.where(DBMaterial.course_id == course_id)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@app.post("/materials", response_model=Material)
async def create_material(
    material: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(require_role("admin", "teacher"))
):
    db_material = DBMaterial(**material.dict())
    db.add(db_material)
    await db.commit()
    await db.refresh(db_material)
    return db_material

# Activity logging
@app.post("/activities", response_model=Activity)
async def create_activity(
    activity: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    db_activity = DBActivity(
        **activity.dict(),
        timestamp=datetime.utcnow()
    )
    db.add(db_activity)
    await db.commit()
    await db.refresh(db_activity)
    return db_activity

# Search functionality
@app.get("/search")
async def search(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = None,
    level: Optional[str] = None,
    material_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Поиск курсов
    courses_stmt = select(DBCourse)
    if q:
        courses_stmt = courses_stmt.where(
            or_(
                DBCourse.title.ilike(f"%{q}%"),
                DBCourse.description.ilike(f"%{q}%"),
                DBCourse.category.ilike(f"%{q}%")
            )
        )
    if category:
        courses_stmt = courses_stmt.where(DBCourse.category == category)
    if level:
        courses_stmt = courses_stmt.where(DBCourse.level == level)
    
    courses_result = await db.execute(courses_stmt)
    courses = courses_result.scalars().all()
    
    # Поиск материалов
    materials_stmt = select(DBMaterial)
    if q:
        materials_stmt = materials_stmt.where(
            or_(
                DBMaterial.title.ilike(f"%{q}%"),
                DBMaterial.content.ilike(f"%{q}%")
            )
        )
    if material_type:
        materials_stmt = materials_stmt.where(DBMaterial.type == material_type)
    
    materials_result = await db.execute(materials_stmt)
    materials = materials_result.scalars().all()
    
    return {
        "courses": courses,
        "materials": materials,
        "total_courses": len(courses),
        "total_materials": len(materials)
    }

# Analytics endpoints
@app.get("/analytics/user/{user_id}/progress")
async def get_user_progress(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Получаем все активности пользователя
    stmt = select(DBActivity, DBMaterial, DBCourse).join(
        DBMaterial, DBActivity.material_id == DBMaterial.id
    ).join(
        DBCourse, DBMaterial.course_id == DBCourse.id
    ).where(DBActivity.user_id == user_id)
    
    result = await db.execute(stmt)
    activities_data = result.all()
    
    # Группируем по курсам
    course_progress = {}
    for activity, material, course in activities_data:
        if course.id not in course_progress:
            course_progress[course.id] = {
                "course_title": course.title,
                "total_materials": 0,
                "completed_materials": 0,
                "total_time": 0.0,
                "avg_score": 0.0,
                "scores": []
            }
        
        progress = course_progress[course.id]
        progress["total_time"] += activity.duration or 0
        
        if activity.action == "complete":
            progress["completed_materials"] += 1
        
        if activity.score is not None:
            progress["scores"].append(activity.score)
    
    # Вычисляем процент прогресса и средние оценки
    for course_id, progress in course_progress.items():
        # Получаем общее количество материалов в курсе
        materials_count_stmt = select(func.count(DBMaterial.id)).where(
            DBMaterial.course_id == course_id
        )
        materials_count_result = await db.execute(materials_count_stmt)
        total_materials = materials_count_result.scalar()
        
        progress["total_materials"] = total_materials
        progress["completion_percentage"] = (
            progress["completed_materials"] / total_materials * 100
            if total_materials > 0 else 0
        )
        progress["avg_score"] = (
            sum(progress["scores"]) / len(progress["scores"])
            if progress["scores"] else 0
        )
        del progress["scores"]  # Удаляем массив оценок из ответа
    
    return course_progress

@app.get("/analytics/course/{course_id}/statistics")
async def get_course_statistics(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(require_role("admin", "teacher"))
):
    # Получаем все активности по курсу
    stmt = select(DBActivity, DBMaterial).join(
        DBMaterial, DBActivity.material_id == DBMaterial.id
    ).where(DBMaterial.course_id == course_id)
    
    result = await db.execute(stmt)
    activities_data = result.all()
    
    # Анализируем данные
    unique_students = set()
    total_time = 0.0
    scores = []
    completions = 0
    
    for activity, material in activities_data:
        unique_students.add(activity.user_id)
        total_time += activity.duration or 0
        
        if activity.score is not None:
            scores.append(activity.score)
        
        if activity.action == "complete":
            completions += 1
    
    return {
        "total_students": len(unique_students),
        "total_time_spent": total_time,
        "average_score": sum(scores) / len(scores) if scores else 0,
        "total_completions": completions,
        "engagement_rate": completions / len(unique_students) if unique_students else 0
    }

# ETL endpoints
@app.get("/etl/activities/export")
async def export_activities_csv(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(require_role("admin"))
):
    stmt = select(DBActivity, DBUser, DBMaterial, DBCourse).join(
        DBUser, DBActivity.user_id == DBUser.id
    ).join(
        DBMaterial, DBActivity.material_id == DBMaterial.id
    ).join(
        DBCourse, DBMaterial.course_id == DBCourse.id
    )
    
    result = await db.execute(stmt)
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "user_id", "user_name", "user_email", "course_id", "course_title",
        "material_id", "material_title", "material_type", "action",
        "timestamp", "duration", "score", "meta"
    ])
    
    for activity, user, material, course in result.all():
        writer.writerow([
            user.id, user.name, user.email, course.id, course.title,
            material.id, material.title, material.type, activity.action,
            activity.timestamp, activity.duration, activity.score,
            json.dumps(activity.meta) if activity.meta else None
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activities_export.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
