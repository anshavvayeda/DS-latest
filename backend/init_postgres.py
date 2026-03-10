"""
Initialize PostgreSQL Database Schema
Creates all tables from SQLAlchemy models
"""
import asyncio
import os
import sys

# Set DB_TYPE to postgresql for this script
os.environ['DB_TYPE'] = 'postgresql'

from app.models.database import Base, engine, init_db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_postgresql():
    """Initialize PostgreSQL database with all tables"""
    try:
        logger.info("🐘 Initializing PostgreSQL database...")
        
        # Create all tables
        async with engine.begin() as conn:
            logger.info("📋 Dropping existing tables (if any)...")
            await conn.run_sync(Base.metadata.drop_all)
            
            logger.info("🏗️  Creating all tables from models...")
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ PostgreSQL schema created successfully!")
        
        # Initialize default data
        logger.info("📚 Initializing default subjects...")
        await init_db()
        
        logger.info("🎉 PostgreSQL database ready!")
        
        # Verify tables
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
                """)
            )
            tables = result.fetchall()
            logger.info(f"📊 Created {len(tables)} tables:")
            for table in tables:
                logger.info(f"   - {table[0]}")
        
    except Exception as e:
        logger.error(f"❌ Error initializing PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_postgresql())
