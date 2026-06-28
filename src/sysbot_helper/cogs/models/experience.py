from sqlalchemy import BigInteger, Column, Integer

from . import Base


class Experience(Base):
    __tablename__ = "experience"
    user_id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger, primary_key=True)
    experience = Column(BigInteger, default=0)
    level = Column(Integer, default=0)
