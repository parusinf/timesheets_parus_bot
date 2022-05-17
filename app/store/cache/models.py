from typing import Optional

from sqlalchemy import exc
from sqlalchemy.future import select
from app.store.cache.accessor import SqliteAccessor, User, Org
from app.store.cache.tools import row_to_dict, rows_to_list

db = SqliteAccessor()


async def get_orgs(org_inn) -> list[dict]:
    async with db.session() as session:
        stmt = select(Org).where(org_inn == Org.org_inn)
        result = await session.execute(stmt)
        return rows_to_list(result)


async def get_org(org_code, org_inn) -> Optional[dict]:
    async with db.session() as session:
        stmt = select(Org).where(org_code == Org.org_code and org_inn == Org.org_inn)
        result = await session.execute(stmt)
        return row_to_dict(result.first())


async def insert_org(org):
    async with db.session() as session:
        async with session.begin():
            session.add(Org(**org))
        try:
            await session.commit()
        except exc.SQLAlchemyError:
            pass


async def insert_orgs(orgs):
    for o in orgs:
        await insert_org(o)


async def get_user(user_id) -> Optional[dict]:
    async with db.session() as session:
        stmt = select(User).where(user_id == User.user_id)
        result = await session.execute(stmt)
        return row_to_dict(result.first())


async def get_user_org(user_id) -> Optional[dict]:
    async with db.session() as session:
        stmt = select(Org).join(User).where(user_id == User.user_id)
        result = await session.execute(stmt)
        return row_to_dict(result.first())


async def insert_user(user):
    async with db.session() as session:
        async with session.begin():
            session.add(User(**user))
        await session.commit()


async def update_user(user):
    async with db.session() as session:
        async with session.begin():
            await session.merge(User(**user))
        await session.commit()


async def delete_user(user_id):
    async with db.session() as session:
        async with session.begin():
            stmt = select(User).where(user_id == User.user_id)
            result = await session.execute(stmt)
            (user,) = result.first()
            await session.delete(user)
        await session.commit()
