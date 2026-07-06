import os
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sysbot_helper.cogs.models import Base, Experience, TelegramMapping, User


@pytest.fixture
async def database_session_factory() -> AsyncGenerator[sessionmaker[AsyncSession], None]:
    """Provides an isolated database session factory using SQLite in-memory or Postgres from environment."""
    database_url: str = os.getenv("POSTGRES_TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    async_engine: AsyncEngine = create_async_engine(database_url)

    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory: sessionmaker[AsyncSession] = sessionmaker(
        async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    yield session_factory

    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await async_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_telegram_mapping_create_read_update_delete(
    database_session_factory: sessionmaker[AsyncSession],
) -> None:
    """Verifies Creating, Reading, Updating, and Deleting TelegramMapping records."""
    async with database_session_factory() as session:
        mapping: TelegramMapping = TelegramMapping(
            telegram_chat=111111111,
            telegram_message=222222222,
            discord_channel=333333333,
            discord_message=444444444,
            discord_attachment=555555555,
        )
        session.add(mapping)
        await session.commit()

    async with database_session_factory() as session:
        statement = select(TelegramMapping).where(TelegramMapping.telegram_chat == 111111111)
        query_result = await session.execute(statement)
        inserted_record: TelegramMapping | None = query_result.scalars().first()

        assert inserted_record is not None
        assert inserted_record.telegram_message == 222222222
        assert inserted_record.discord_channel == 333333333
        assert inserted_record.discord_message == 444444444
        assert inserted_record.discord_attachment == 555555555
        assert isinstance(inserted_record.created_at, datetime)

        inserted_record.telegram_message = 999999999
        await session.commit()

    async with database_session_factory() as session:
        statement = select(TelegramMapping).where(TelegramMapping.telegram_chat == 111111111)
        query_result = await session.execute(statement)
        updated_record: TelegramMapping | None = query_result.scalars().first()

        assert updated_record is not None
        assert updated_record.telegram_message == 999999999

        await session.delete(updated_record)
        await session.commit()

    async with database_session_factory() as session:
        statement = select(TelegramMapping).where(TelegramMapping.telegram_chat == 111111111)
        query_result = await session.execute(statement)
        deleted_record: TelegramMapping | None = query_result.scalars().first()

        assert deleted_record is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_user_record_upsert_logic(
    database_session_factory: sessionmaker[AsyncSession],
) -> None:
    """Verifies User updating and name modification."""

    class MockDiscordAuthor:
        def __init__(self, user_identifier: int, user_display_name: str) -> None:
            self.id = user_identifier
            self.name = user_display_name

    class MockCommandContext:
        def __init__(self, author_identifier: int, author_display_name: str) -> None:
            self.author = MockDiscordAuthor(author_identifier, author_display_name)

    command_context: MockCommandContext = MockCommandContext(123456789, "TestUser")

    async with database_session_factory() as session:
        await User.update(command_context, session)
        await session.commit()

    async with database_session_factory() as session:
        statement = select(User).where(User.user_id == 123456789)
        query_result = await session.execute(statement)
        user_record: User | None = query_result.scalars().first()

        assert user_record is not None
        assert user_record.name == "TestUser"

        updated_command_context: MockCommandContext = MockCommandContext(123456789, "UpdatedTestUser")
        await User.update(updated_command_context, session)
        await session.commit()

    async with database_session_factory() as session:
        statement = select(User).where(User.user_id == 123456789)
        query_result = await session.execute(statement)
        updated_user_record: User | None = query_result.scalars().first()

        assert updated_user_record is not None
        assert updated_user_record.name == "UpdatedTestUser"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_experience_record_crud(
    database_session_factory: sessionmaker[AsyncSession],
) -> None:
    """Verifies Creating, Reading, and Updating Experience records."""
    async with database_session_factory() as session:
        experience_record: Experience = Experience(
            user_id=987654321,
            guild_id=111222333,
            experience=100,
            level=2,
        )
        session.add(experience_record)
        await session.commit()

    async with database_session_factory() as session:
        statement = select(Experience).where(
            Experience.user_id == 987654321,
            Experience.guild_id == 111222333,
        )
        query_result = await session.execute(statement)
        loaded_experience: Experience | None = query_result.scalars().first()

        assert loaded_experience is not None
        assert loaded_experience.experience == 100
        assert loaded_experience.level == 2

        loaded_experience.experience += 50
        loaded_experience.level = 3
        await session.commit()

    async with database_session_factory() as session:
        statement = select(Experience).where(
            Experience.user_id == 987654321,
            Experience.guild_id == 111222333,
        )
        query_result = await session.execute(statement)
        updated_experience: Experience | None = query_result.scalars().first()

        assert updated_experience is not None
        assert updated_experience.experience == 150
        assert updated_experience.level == 3
