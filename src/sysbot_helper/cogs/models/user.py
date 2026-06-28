from sqlalchemy import BigInteger, Column, String

from . import Base


class User(Base):
    __tablename__ = "user"
    user_id = Column(BigInteger, primary_key=True)
    name = Column(String)

    @classmethod
    async def update(cls, ctx, session):
        user = cls(user_id=ctx.author.id, name=ctx.author.name)
        await session.merge(user)
