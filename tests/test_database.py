import unittest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from sysbot_helper.cogs.models import Base, TelegramMapping, User, Experience


class TestDatabaseIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Database URL pointing to our temporary local Podman Postgres container
        self.db_url = (
            "postgresql+asyncpg://sysbot_user:sysbot_pass@localhost:5432/sysbot_test"
        )
        self.engine = create_async_engine(self.db_url)
        self.Session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

        # Drop tables if they exist and recreate them cleanly for isolation
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        # Clean up database tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_telegram_mapping_crud(self):
        """Test Creating, Reading, Updating, and Deleting TelegramMapping records."""
        async with self.Session() as session:
            # 1. Create (Insert)
            mapping = TelegramMapping(
                telegram_chat=111111111,
                telegram_message=222222222,
                discord_channel=333333333,
                discord_message=444444444,
                discord_attachment=555555555,
            )
            session.add(mapping)
            await session.commit()

        async with self.Session() as session:
            # 2. Read (Query)
            stmt = select(TelegramMapping).where(
                TelegramMapping.telegram_chat == 111111111
            )
            result = await session.execute(stmt)
            inserted = result.scalars().first()

            self.assertIsNotNone(inserted)
            self.assertEqual(inserted.telegram_message, 222222222)
            self.assertEqual(inserted.discord_channel, 333333333)
            self.assertEqual(inserted.discord_message, 444444444)
            self.assertEqual(inserted.discord_attachment, 555555555)
            self.assertIsInstance(inserted.created_at, datetime)

            # 3. Update
            inserted.telegram_message = 999999999
            await session.commit()

        async with self.Session() as session:
            # Verify Update
            stmt = select(TelegramMapping).where(
                TelegramMapping.telegram_chat == 111111111
            )
            result = await session.execute(stmt)
            updated = result.scalars().first()
            self.assertEqual(updated.telegram_message, 999999999)

            # 4. Delete
            await session.delete(updated)
            await session.commit()

        async with self.Session() as session:
            # Verify Delete
            stmt = select(TelegramMapping).where(
                TelegramMapping.telegram_chat == 111111111
            )
            result = await session.execute(stmt)
            deleted = result.scalars().first()
            self.assertIsNone(deleted)

    async def test_user_crud(self):
        """Test Creating, Reading, and Updating User records."""

        # Create a mock Context class to test classmethod User.update
        class MockAuthor:
            def __init__(self, id, name):
                self.id = id
                self.name = name

        class MockContext:
            def __init__(self, author_id, author_name):
                self.author = MockAuthor(author_id, author_name)

        ctx = MockContext(123456789, "TestUser")

        async with self.Session() as session:
            # 1. Create / Merge via classmethod
            await User.update(ctx, session)
            await session.commit()

        async with self.Session() as session:
            # 2. Read
            stmt = select(User).where(User.user_id == 123456789)
            result = await session.execute(stmt)
            user = result.scalars().first()

            self.assertIsNotNone(user)
            self.assertEqual(user.name, "TestUser")

            # 3. Update name
            ctx_updated = MockContext(123456789, "UpdatedTestUser")
            await User.update(ctx_updated, session)
            await session.commit()

        async with self.Session() as session:
            # Verify Update
            stmt = select(User).where(User.user_id == 123456789)
            result = await session.execute(stmt)
            user_updated = result.scalars().first()
            self.assertEqual(user_updated.name, "UpdatedTestUser")

    async def test_experience_crud(self):
        """Test Creating, Reading, and Updating Experience records."""
        async with self.Session() as session:
            # 1. Create
            exp = Experience(
                user_id=987654321, guild_id=111222333, experience=100, level=2
            )
            session.add(exp)
            await session.commit()

        async with self.Session() as session:
            # 2. Read
            stmt = select(Experience).where(
                Experience.user_id == 987654321, Experience.guild_id == 111222333
            )
            result = await session.execute(stmt)
            loaded_exp = result.scalars().first()

            self.assertIsNotNone(loaded_exp)
            self.assertEqual(loaded_exp.experience, 100)
            self.assertEqual(loaded_exp.level, 2)

            # 3. Update
            loaded_exp.experience += 50
            loaded_exp.level = 3
            await session.commit()

        async with self.Session() as session:
            # Verify Update
            stmt = select(Experience).where(
                Experience.user_id == 987654321, Experience.guild_id == 111222333
            )
            result = await session.execute(stmt)
            updated_exp = result.scalars().first()
            self.assertEqual(updated_exp.experience, 150)
            self.assertEqual(updated_exp.level, 3)
