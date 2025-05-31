from db import Base, engine
import asyncio

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Database initialized!')

if __name__ == "__main__":
    asyncio.run(init_models()) 