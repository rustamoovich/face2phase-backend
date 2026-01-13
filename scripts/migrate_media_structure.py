"""
Migration script to add new media structure fields to existing database.

This script:
1. Adds new columns to media_items table:
   - small_thumbnail_path
   - medium_thumbnail_path
   - preview_path
   - file_type
2. Does NOT migrate existing data (existing files remain in old structure)
"""
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def migrate():
    """Add new columns to media_items table"""
    async with AsyncSessionLocal() as db:
        try:
            print("🔄 Starting migration...")
            
            # Check if columns already exist
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'media_items' 
                AND column_name IN ('small_thumbnail_path', 'medium_thumbnail_path', 'preview_path', 'file_type')
            """)
            result = await db.execute(check_query)
            existing_columns = {row[0] for row in result.fetchall()}
            
            # Add small_thumbnail_path if not exists
            if 'small_thumbnail_path' not in existing_columns:
                print("  ➕ Adding column: small_thumbnail_path")
                await db.execute(text("""
                    ALTER TABLE media_items 
                    ADD COLUMN small_thumbnail_path VARCHAR(255)
                """))
            else:
                print("  ✅ Column already exists: small_thumbnail_path")
            
            # Add medium_thumbnail_path if not exists
            if 'medium_thumbnail_path' not in existing_columns:
                print("  ➕ Adding column: medium_thumbnail_path")
                await db.execute(text("""
                    ALTER TABLE media_items 
                    ADD COLUMN medium_thumbnail_path VARCHAR(255)
                """))
            else:
                print("  ✅ Column already exists: medium_thumbnail_path")
            
            # Add preview_path if not exists
            if 'preview_path' not in existing_columns:
                print("  ➕ Adding column: preview_path")
                await db.execute(text("""
                    ALTER TABLE media_items 
                    ADD COLUMN preview_path VARCHAR(255)
                """))
            else:
                print("  ✅ Column already exists: preview_path")
            
            # Add file_type if not exists
            if 'file_type' not in existing_columns:
                print("  ➕ Adding column: file_type")
                await db.execute(text("""
                    ALTER TABLE media_items 
                    ADD COLUMN file_type VARCHAR(50)
                """))
            else:
                print("  ✅ Column already exists: file_type")
            
            await db.commit()
            
            print("✅ Migration completed successfully!")
            print("\n📝 Note: Existing media files are NOT migrated to the new structure.")
            print("   New uploads will use the new structure automatically.")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(migrate())
