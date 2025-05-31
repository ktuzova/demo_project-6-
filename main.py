from fastapi import FastAPI, Query, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from db import SessionLocal, User as DBUser, Course as DBCourse, Material as DBMaterial, Activity as DBActivity
from collections import Counter
from fastapi.responses import StreamingResponse
from io import StringIO
import csv
from fastapi.middleware.cors import CORSMiddleware

SECRET_KEY = "supersecretkey"  # Замените на свой ключ в проде
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

app = FastAPI(title="Online Courses Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth helpers ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(lambda: SessionLocal())):
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

# --- Pydantic Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    name: str
    role: str
    class Config:
        orm_mode = True

class UserCreate(BaseModel):
    name: str
    role: str
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class Course(BaseModel):
    id: int
    title: str
    category: str
    level: str
    teacher_id: int
    class Config:
        orm_mode = True

class CourseCreate(BaseModel):
    title: str
    category: str
    level: str
    teacher_id: int

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    level: Optional[str] = None
    teacher_id: Optional[int] = None

class Material(BaseModel):
    id: int
    course_id: int
    title: str
    type: str
    class Config:
        orm_mode = True

class MaterialCreate(BaseModel):
    course_id: int
    title: str
    type: str

class MaterialUpdate(BaseModel):
    course_id: Optional[int] = None
    title: Optional[str] = None
    type: Optional[str] = None

class Activity(BaseModel):
    id: int
    user_id: int
    material_id: int
    action: str
    timestamp: datetime
    duration: Optional[float] = None
    score: Optional[float] = None
    class Config:
        orm_mode = True

class ActivityEvent(BaseModel):
    user_id: int
    material_id: int
    action: str  # 'view', 'complete', 'test_passed', 'like', etc.
    timestamp: datetime
    duration: Optional[float] = None
    score: Optional[float] = None
    meta: Optional[dict] = None  # Дополнительные данные

# --- Dependency ---
async def get_db():
    async with SessionLocal() as session:
        yield session

# --- AUTH ---
@app.post("/register", response_model=User)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    db_user = DBUser(name=user.name, role=user.role, password_hash=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBUser).where(DBUser.name == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# --- CRUD USERS ---
@app.get("/users", response_model=List[User])
async def get_users(db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    result = await db.execute(select(DBUser))
    return result.scalars().all()

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    result = await db.execute(select(DBUser).where(DBUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.patch("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: UserUpdate, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin"))):
    result = await db.execute(select(DBUser).where(DBUser.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.name:
        db_user.name = user.name
    if user.role:
        db_user.role = user.role
    if user.password:
        db_user.password_hash = get_password_hash(user.password)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin"))):
    result = await db.execute(select(DBUser).where(DBUser.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(db_user)
    await db.commit()
    return {"ok": True}

# --- CRUD COURSES ---
@app.get("/courses", response_model=List[Course])
async def get_courses(db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    result = await db.execute(select(DBCourse))
    return result.scalars().all()

@app.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    result = await db.execute(select(DBCourse).where(DBCourse.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@app.post("/courses", response_model=Course)
async def create_course(course: CourseCreate, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    db_course = DBCourse(**course.dict())
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course

@app.patch("/courses/{course_id}", response_model=Course)
async def update_course(course_id: int, course: CourseUpdate, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    result = await db.execute(select(DBCourse).where(DBCourse.id == course_id))
    db_course = result.scalar_one_or_none()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    for field, value in course.dict(exclude_unset=True).items():
        setattr(db_course, field, value)
    await db.commit()
    await db.refresh(db_course)
    return db_course

@app.delete("/courses/{course_id}")
async def delete_course(course_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    result = await db.execute(select(DBCourse).where(DBCourse.id == course_id))
    db_course = result.scalar_one_or_none()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    await db.delete(db_course)
    await db.commit()
    return {"ok": True}

# --- CRUD MATERIALS ---
@app.get("/materials", response_model=List[Material])
async def get_materials(db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    result = await db.execute(select(DBMaterial))
    return result.scalars().all()

@app.get("/materials/{material_id}", response_model=Material)
async def get_material(material_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    result = await db.execute(select(DBMaterial).where(DBMaterial.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material

@app.post("/materials", response_model=Material)
async def create_material(material: MaterialCreate, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    db_material = DBMaterial(**material.dict())
    db.add(db_material)
    await db.commit()
    await db.refresh(db_material)
    return db_material

@app.patch("/materials/{material_id}", response_model=Material)
async def update_material(material_id: int, material: MaterialUpdate, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    result = await db.execute(select(DBMaterial).where(DBMaterial.id == material_id))
    db_material = result.scalar_one_or_none()
    if not db_material:
        raise HTTPException(status_code=404, detail="Material not found")
    for field, value in material.dict(exclude_unset=True).items():
        setattr(db_material, field, value)
    await db.commit()
    await db.refresh(db_material)
    return db_material

@app.delete("/materials/{material_id}")
async def delete_material(material_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    result = await db.execute(select(DBMaterial).where(DBMaterial.id == material_id))
    db_material = result.scalar_one_or_none()
    if not db_material:
        raise HTTPException(status_code=404, detail="Material not found")
    await db.delete(db_material)
    await db.commit()
    return {"ok": True}

# --- API Endpoints ---
@app.get("/search", response_model=dict)
async def search(
    query: Optional[str] = Query(None),
    category: Optional[str] = None,
    level: Optional[str] = None,
    material_type: Optional[str] = None,
    teacher_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Поиск курсов
    stmt_courses = select(DBCourse)
    if query:
        stmt_courses = stmt_courses.where(or_(DBCourse.title.ilike(f"%{query}%"), DBCourse.category.ilike(f"%{query}%")))
    if category:
        stmt_courses = stmt_courses.where(DBCourse.category == category)
    if level:
        stmt_courses = stmt_courses.where(DBCourse.level == level)
    if teacher_name:
        subq = select(DBUser.id).where(DBUser.name.ilike(f"%{teacher_name}%"))
        stmt_courses = stmt_courses.where(DBCourse.teacher_id.in_(subq))
    courses = (await db.execute(stmt_courses)).scalars().all()

    # Поиск материалов
    stmt_materials = select(DBMaterial)
    if query:
        stmt_materials = stmt_materials.where(DBMaterial.title.ilike(f"%{query}%"))
    if material_type:
        stmt_materials = stmt_materials.where(DBMaterial.type == material_type)
    if category or level or teacher_name:
        # фильтрация материалов по курсам
        course_ids = [c.id for c in courses]
        if course_ids:
            stmt_materials = stmt_materials.where(DBMaterial.course_id.in_(course_ids))
    materials = (await db.execute(stmt_materials)).scalars().all()

    # Поиск преподавателей
    stmt_teachers = select(DBUser).where(DBUser.role == "teacher")
    if teacher_name or query:
        name_query = teacher_name or query
        stmt_teachers = stmt_teachers.where(DBUser.name.ilike(f"%{name_query}%"))
    teachers = (await db.execute(stmt_teachers)).scalars().all()

    return {
        "courses": courses,
        "materials": materials,
        "teachers": teachers
    }

@app.post("/activity/log", response_model=Activity)
async def log_activity(activity: Activity, db: AsyncSession = Depends(get_db)):
    db_activity = DBActivity(**activity.dict())
    db.add(db_activity)
    await db.commit()
    await db.refresh(db_activity)
    return db_activity

@app.get("/analytics/progress", response_model=List[Activity])
async def analytics_progress(user_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(DBActivity).where(DBActivity.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@app.get("/etl/export")
async def etl_export(db: AsyncSession = Depends(get_db)):
    stmt = select(DBActivity)
    result = await db.execute(stmt)
    return [a.__dict__ for a in result.scalars().all()]

@app.get("/etl/export_full")
async def etl_export_full(db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(require_role("admin", "teacher"))):
    stmt = select(DBActivity, DBUser, DBMaterial, DBCourse).join(DBUser, DBActivity.user_id == DBUser.id).join(DBMaterial, DBActivity.material_id == DBMaterial.id).join(DBCourse, DBMaterial.course_id == DBCourse.id)
    result = await db.execute(stmt)
    data = []
    for activity, user, material, course in result.all():
        data.append({
            "user_id": user.id,
            "user_name": user.name,
            "course_id": course.id,
            "course_title": course.title,
            "material_id": material.id,
            "material_title": material.title,
            "material_type": material.type,
            "action": activity.action,
            "timestamp": activity.timestamp,
            "duration": activity.duration,
            "score": activity.score
        })
    return data

@app.get("/courses/{course_id}/materials", response_model=List[Material])
async def get_course_materials(course_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBMaterial).where(DBMaterial.course_id == course_id))
    return result.scalars().all()

# Аналитика по курсу
@app.get("/analytics/course/{course_id}")
async def analytics_course(course_id: int, db: AsyncSession = Depends(get_db)):
    # Количество студентов, средний балл, среднее время
    result = await db.execute(select(DBActivity).where(DBActivity.material_id.in_(
        select(DBMaterial.id).where(DBMaterial.course_id == course_id)
    )))
    activities = result.scalars().all()
    students = set(a.user_id for a in activities)
    avg_score = (sum(a.score for a in activities if a.score is not None) / max(1, sum(1 for a in activities if a.score is not None))) if activities else 0
    avg_time = (sum(a.duration for a in activities if a.duration is not None) / max(1, sum(1 for a in activities if a.duration is not None))) if activities else 0
    return {
        "students_count": len(students),
        "avg_score": avg_score,
        "avg_time": avg_time
    }

# Аналитика по пользователю
@app.get("/analytics/user/{user_id}")
async def analytics_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBActivity).where(DBActivity.user_id == user_id))
    activities = result.scalars().all()
    courses = set()
    for a in activities:
        mat_result = await db.execute(select(DBMaterial).where(DBMaterial.id == a.material_id))
        material = mat_result.scalar_one_or_none()
        if material:
            courses.add(material.course_id)
    avg_score = (sum(a.score for a in activities if a.score is not None) / max(1, sum(1 for a in activities if a.score is not None))) if activities else 0
    avg_time = (sum(a.duration for a in activities if a.duration is not None) / max(1, sum(1 for a in activities if a.duration is not None))) if activities else 0
    return {
        "courses_count": len(courses),
        "avg_score": avg_score,
        "avg_time": avg_time
    }

@app.get("/analytics/course/{course_id}/progress")
async def course_progress_dynamics(course_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    # Динамика прогресса по курсу: сколько студентов завершили материалы по дням
    stmt = select(DBActivity).join(DBMaterial, DBActivity.material_id == DBMaterial.id).where(DBMaterial.course_id == course_id, DBActivity.action == "complete")
    result = await db.execute(stmt)
    activities = result.scalars().all()
    progress_by_day = {}
    for a in activities:
        day = a.timestamp.date().isoformat()
        progress_by_day[day] = progress_by_day.get(day, 0) + 1
    return progress_by_day

@app.get("/analytics/course/{course_id}/top-materials")
async def course_top_materials(course_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    # Топ-материалы по количеству активности (просмотров/завершений)
    stmt = select(DBActivity, DBMaterial).join(DBMaterial, DBActivity.material_id == DBMaterial.id).where(DBMaterial.course_id == course_id)
    result = await db.execute(stmt)
    counter = Counter()
    for activity, material in result.all():
        counter[material.title] += 1
    top_materials = counter.most_common(5)
    return [{"material_title": title, "activity_count": count} for title, count in top_materials]

@app.get("/analytics/course/{course_id}/avg-test-score")
async def course_avg_test_score(course_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    # Средний балл по тестам для курса
    stmt = select(DBActivity, DBMaterial).join(DBMaterial, DBActivity.material_id == DBMaterial.id).where(DBMaterial.course_id == course_id, DBMaterial.type == "quiz", DBActivity.score != None)
    result = await db.execute(stmt)
    scores = [activity.score for activity, _ in result.all() if activity.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    return {"avg_test_score": avg_score}

@app.get("/analytics/user/{user_id}/avg-test-score")
async def user_avg_test_score(user_id: int, db: AsyncSession = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    # Средний балл по тестам для пользователя
    stmt = select(DBActivity, DBMaterial).join(DBMaterial, DBActivity.material_id == DBMaterial.id).where(DBActivity.user_id == user_id, DBMaterial.type == "quiz", DBActivity.score != None)
    result = await db.execute(stmt)
    scores = [activity.score for activity, _ in result.all() if activity.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    return {"avg_test_score": avg_score}

@app.post("/activity/log_event")
async def log_event(event: ActivityEvent, db: AsyncSession = Depends(get_db)):
    db_activity = DBActivity(
        user_id=event.user_id,
        material_id=event.material_id,
        action=event.action,
        timestamp=event.timestamp,
        duration=event.duration,
        score=event.score,
        meta=event.meta
    )
    db.add(db_activity)
    await db.commit()
    await db.refresh(db_activity)
    return db_activity

@app.get("/etl/export_csv")
async def etl_export_csv(db: AsyncSession = Depends(get_db)):
    stmt = select(DBActivity, DBUser, DBMaterial, DBCourse).join(DBUser, DBActivity.user_id == DBUser.id).join(DBMaterial, DBActivity.material_id == DBMaterial.id).join(DBCourse, DBMaterial.course_id == DBCourse.id)
    result = await db.execute(stmt)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "user_name", "course_id", "course_title", "material_id", "material_title", "material_type", "action", "timestamp", "duration", "score"])
    for activity, user, material, course in result.all():
        writer.writerow([
            user.id, user.name, course.id, course.title, material.id, material.title, material.type,
            activity.action, activity.timestamp, activity.duration, activity.score
        ])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=etl_export.csv"})

@app.get("/recommendation/raw_data")
async def recommendation_raw_data(db: AsyncSession = Depends(get_db)):
    stmt = select(DBActivity)
    result = await db.execute(stmt)
    data = []
    for a in result.scalars().all():
        data.append({
            "user_id": a.user_id,
            "material_id": a.material_id,
            "action": a.action,
            "timestamp": a.timestamp,
            "duration": a.duration,
            "score": a.score
        })
    return data

@app.get("/activity/my")
async def my_activity(current_user: DBUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(DBActivity).where(DBActivity.user_id == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@app.get("/progress/my")
async def my_progress(current_user: DBUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(DBActivity, DBMaterial, DBCourse).join(DBMaterial, DBActivity.material_id == DBMaterial.id).join(DBCourse, DBMaterial.course_id == DBCourse.id).where(DBActivity.user_id == current_user.id)
    result = await db.execute(stmt)
    progress = {}
    for activity, material, course in result.all():
        c = progress.setdefault(course.title, {"course_id": course.id, "materials": set(), "completed": 0})
        c["materials"].add(material.title)
        if activity.action == "complete":
            c["completed"] += 1
    # Преобразуем set в list для сериализации
    for c in progress.values():
        c["materials"] = list(c["materials"])
    return list(progress.values())

@app.get("/etl/recommendation_data")
async def etl_recommendation_data(db: AsyncSession = Depends(get_db)):
    # Собираем: user_id, course_id, completed_materials, total_time, avg_score, progress
    stmt = select(DBActivity, DBMaterial, DBCourse).join(DBMaterial, DBActivity.material_id == DBMaterial.id).join(DBCourse, DBMaterial.course_id == DBCourse.id)
    result = await db.execute(stmt)
    data = {}
    for activity, material, course in result.all():
        key = (activity.user_id, course.id)
        if key not in data:
            data[key] = {
                "user_id": activity.user_id,
                "course_id": course.id,
                "course_title": course.title,
                "completed_materials": set(),
                "total_time": 0.0,
                "scores": [],
                "all_materials": set(),
            }
        d = data[key]
        d["all_materials"].add(material.id)
        if activity.action == "complete":
            d["completed_materials"].add(material.id)
        if activity.duration:
            d["total_time"] += activity.duration
        if activity.score is not None:
            d["scores"].append(activity.score)
    # Формируем итоговую таблицу
    result_list = []
    for d in data.values():
        progress = len(d["completed_materials"]) / max(1, len(d["all_materials"]))
        avg_score = sum(d["scores"]) / len(d["scores"]) if d["scores"] else None
        result_list.append({
            "user_id": d["user_id"],
            "course_id": d["course_id"],
            "course_title": d["course_title"],
            "completed_materials_count": len(d["completed_materials"]),
            "total_materials_count": len(d["all_materials"]),
            "progress": progress,
            "total_time": d["total_time"],
            "avg_score": avg_score
        })
    return result_list

@app.get("/analytics/student/{user_id}/activity")
async def student_activity_analytics(user_id: int, db: AsyncSession = Depends(get_db)):
    # Аналитика: общее время, прогресс по курсам, средний балл по тестам
    stmt = select(DBActivity, DBMaterial, DBCourse).join(DBMaterial, DBActivity.material_id == DBMaterial.id).join(DBCourse, DBMaterial.course_id == DBCourse.id).where(DBActivity.user_id == user_id)
    result = await db.execute(stmt)
    courses = {}
    total_time = 0.0
    all_scores = []
    for activity, material, course in result.all():
        c = courses.setdefault(course.id, {"course_title": course.title, "completed": set(), "all": set(), "scores": [], "time": 0.0})
        c["all"].add(material.id)
        if activity.action == "complete":
            c["completed"].add(material.id)
        if activity.duration:
            c["time"] += activity.duration
            total_time += activity.duration
        if activity.score is not None:
            c["scores"].append(activity.score)
            all_scores.append(activity.score)
    # Формируем результат
    analytics = []
    for cid, c in courses.items():
        progress = len(c["completed"]) / max(1, len(c["all"]))
        avg_score = sum(c["scores"]) / len(c["scores"]) if c["scores"] else None
        analytics.append({
            "course_id": cid,
            "course_title": c["course_title"],
            "progress": progress,
            "total_time": c["time"],
            "avg_score": avg_score
        })
    return {
        "total_time": total_time,
        "avg_score": sum(all_scores) / len(all_scores) if all_scores else None,
        "courses": analytics
    } 