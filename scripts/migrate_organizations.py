"""
Migration script to add organizations, update users and events tables.

This migration adds:
1. organizations table
2. organization_id to users table
3. organization_id to events table (required)
4. event_access table for photographer permissions
5. Update Event model: rename organizer_id logic
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
    """Add organizations and update schema"""
    async with AsyncSessionLocal() as db:
        try:
            print("Starting migration to organizations system...")
            
            # 1. Создание таблицы organizations
            print("\n[1/6] Creating organizations table...")
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS organizations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(200) NOT NULL UNIQUE,
                    slug VARCHAR(200) NOT NULL UNIQUE,
                    description TEXT,
                    logo_path VARCHAR(255),
                    website VARCHAR(255),
                    contact_email VARCHAR(255),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("OK: Organizations table created")
            
            # 2. Добавление organization_id в users
            print("\n[2/6] Adding organization_id to users...")
            try:
                await db.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL
                """))
                print("OK: organization_id added to users")
            except Exception as e:
                print(f"WARNING: organization_id might already exist: {e}")
            
            # 3. Добавление organization_id в events
            print("\n[3/6] Adding organization_id to events...")
            try:
                await db.execute(text("""
                    ALTER TABLE events 
                    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE
                """))
                print("OK: organization_id added to events")
            except Exception as e:
                print(f"WARNING: organization_id might already exist: {e}")
            
            # 4. Добавление новых полей в events
            print("\n[4/6] Adding event assets fields...")
            try:
                await db.execute(text("""
                    ALTER TABLE events 
                    ADD COLUMN IF NOT EXISTS map_image_path VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS partners_data JSONB
                """))
                print("OK: Event assets fields added")
            except Exception as e:
                print(f"WARNING: Fields might already exist: {e}")
            
            # 5. Создание таблицы event_access
            print("\n[5/6] Creating event_access table...")
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS event_access (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    photographer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    granted_by UUID REFERENCES users(id),
                    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(event_id, photographer_id)
                )
            """))
            print("OK: Event_access table created")
            
            # 6. Создание индексов
            print("\n[6/6] Creating indexes...")
            await db.execute(text("CREATE INDEX IF NOT EXISTS idx_users_organization_id ON users(organization_id)"))
            await db.execute(text("CREATE INDEX IF NOT EXISTS idx_events_organization_id ON events(organization_id)"))
            await db.execute(text("CREATE INDEX IF NOT EXISTS idx_event_access_event_id ON event_access(event_id)"))
            await db.execute(text("CREATE INDEX IF NOT EXISTS idx_event_access_photographer_id ON event_access(photographer_id)"))
            print("OK: Indexes created")
            
            await db.commit()
            
            print("\n=== Migration completed successfully! ===")
            print("\nNext steps:")
            print("   1. Create a default organization (if needed)")
            print("   2. Assign existing users to organizations")
            print("   3. Update existing events with organization_id")
            print("   4. Update user roles (organizer/photographer)")
            
        except Exception as e:
            print(f"\nERROR: Migration failed: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate())
