import logging
import traceback

from sqlalchemy import select, update, delete, JSON
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from config import db_url

logger = logging.getLogger(__name__)

engine = create_async_engine(db_url, echo=False)

session_maker = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class User(Base):
    __tablename__ = "user"

    pk: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[str] = mapped_column(String(100), unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)


class Keyword(Base):
    __tablename__ = "keyword"

    pk: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(1024), unique=True)

class AutoliftKeyword(Base):
    __tablename__ = "autolift_keyword"

    pk: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(1024), unique=True)
    position: Mapped[int] = mapped_column()

async def orm_create(session: AsyncSession, model: object, data: dict):
    try:
        obj = model(**data)
        session.add(obj)
        await session.commit()

        return True
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())

        return False

async def orm_read(
    session: AsyncSession, model: object, as_iterable: bool = False, **filters
):
    try:
        query = select(model)
        if filters:
            query = query.filter_by(**filters)

        result = await session.execute(query)
        items = result.scalars().all()

        if len(items) == 1 and as_iterable is False:
            return items[0]

        return items
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())

        return False


async def orm_update(session: AsyncSession, model: object, pk: int, data: dict):
    try:
        await session.execute(update(model).where(model.pk == pk).values(**data))
        return await session.commit()
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())

        return False


async def orm_delete(session: AsyncSession, model: object, pk: int):
    try:
        await session.execute(delete(model).where(model.pk == pk))
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Short error message: {e}")
        logger.error(traceback.format_exc())

        return False
