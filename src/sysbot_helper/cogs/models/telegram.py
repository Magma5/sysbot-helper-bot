from . import Base
from sqlalchemy import Column, BigInteger, DateTime, Integer, func


class TelegramMapping(Base):
    __tablename__ = "telegram_mapping"
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    telegram_chat = Column(BigInteger, nullable=False)
    telegram_message = Column(BigInteger, nullable=False)
    discord_channel = Column(BigInteger, nullable=False)
    discord_message = Column(BigInteger, nullable=False)
    discord_attachment = Column(BigInteger)
    created_at = Column(DateTime(), server_default=func.now(), nullable=False)
