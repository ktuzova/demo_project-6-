# init_db.py - Улучшенная версия
import asyncio
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.append(str(Path(__file__).parent))

from db import Base, engine, SessionLocal
from fill_test_data import fill_with_sample_data

async def init_models():
    """Инициализация базы данных"""
    try:
        async with engine.begin() as conn:
            # Удаляем все таблицы (осторожно!)
            await conn.run_sync(Base.metadata.drop_all)
            # Создаем все таблицы
            await conn.run_sync(Base.metadata.create_all)
        
        print('✅ База данных успешно инициализирована!')
        
        # Заполняем тестовыми данными
        choice = input('Заполнить базу тестовыми данными? (y/N): ')
        if choice.lower() in ['y', 'yes', 'д', 'да']:
            await fill_with_sample_data()
            print('✅ Тестовые данные добавлены!')
        
    except Exception as e:
        print(f'❌ Ошибка инициализации базы данных: {e}')
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_models())
