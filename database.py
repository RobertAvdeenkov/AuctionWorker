from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
import os
from sqlalchemy.orm import sessionmaker

DATABASE_URL=os.getenv('DATABASE_URL','sqlite+aiosqlite:///auction.db')
engine=create_async_engine(DATABASE_URL, connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0})
SessionLocal=sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  #type:ignore

async def get_db():
    async with SessionLocal() as db: #type:ignore
        try:
            yield db
        finally:
            await db.close()