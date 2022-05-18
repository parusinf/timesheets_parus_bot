from sqlalchemy import Column, UniqueConstraint, ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import sessionmaker
from app.settings import config

Base = declarative_base()


class Org(Base):
    __tablename__ = 'org'
    id = Column(Integer, primary_key=True)
    org_rn = Column(Integer, nullable=False)
    org_code = Column(String, nullable=False)
    org_name = Column(String, nullable=False)
    org_inn = Column(String, nullable=False)
    company_rn = Column(Integer, nullable=False)
    db_key = Column(String, nullable=False)
    users = relationship('User', backref='org')
    __table_args__ = (UniqueConstraint('org_code', 'org_inn', name='_org_code_inn_uc'),)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String)
    user_first_name = Column(String)
    user_last_name = Column(String)
    org_inn = Column(String)
    org_id = Column(Integer, ForeignKey(Org.id))
    person_rn = Column(Integer)
    family = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    group = Column(String)
    __table_args__ = (UniqueConstraint('user_id', name='_user_user_id_uc'),)


class SqliteAccessor:
    def __init__(self) -> None:
        self.engine = None
        self.session = None

    async def on_connect(self):
        self.engine = create_async_engine(
            f'sqlite+aiosqlite:///{config["sqlite"]["database"]}?cache=shared',
            echo=config['sqlite']['echo'],
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def on_disconnect(self):
        await self.engine.dispose()
