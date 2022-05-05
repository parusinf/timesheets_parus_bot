from datetime import datetime
from typing import Optional
from aiogram import types
from aiogram.dispatcher import FSMContext
from motor.motor_asyncio import AsyncIOMotorClient
from app.settings import config
from tools.helpers import keys_exists


# Async MongoDB
client = AsyncIOMotorClient(config['mongodb']['host'], config['mongodb']['port'])
db = client[config['mongodb']['database']]
orgs = db['orgs']
users = db['users']


async def get_user(state: FSMContext, user_id: int) -> Optional[dict]:
    data = await state.get_data()
    if 'user' in data:
        return data['user']
    else:
        user = await users.find_one({'user_id': user_id})
        return dict(user) if user else None


async def create_user(state: FSMContext, message: types.Message, org) -> None:
    user = {
        'db_key': org['db_key'],
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'full_name': message.from_user.full_name,
        'receive_count': 0,
        'send_count': 0,
        'org_rn': org['org_rn'],
    }
    await state.update_data({'user': user})
    await users.insert_one(user)


async def update_user(state: FSMContext, user) -> None:
    await state.update_data({'user': user})
    await users.update_one(
        {'user_id': user['user_id']},
        {'$set': user}
    )


async def delete_user(state: FSMContext, user_id: int) -> None:
    data = await state.get_data()
    if keys_exists(['user'], data):
        del data['user']
        await state.set_data(data)
    await users.delete_one({'user_id': user_id})


async def inc_send_count(state: FSMContext, user_id: int) -> None:
    user = await get_user(state, user_id)
    if user:
        user['last_date'] = datetime.now()
        user['send_count'] += 1
        await update_user(state, user)


async def inc_receive_count(state: FSMContext, user_id: int) -> None:
    user = await get_user(state, user_id)
    if user:
        user['last_date'] = datetime.now()
        user['receive_count'] += 1
        await update_user(state, user)


async def get_org(state: FSMContext, user_id: int) -> Optional[dict]:
    data = await state.get_data()
    if keys_exists(['org'], data):
        return data['org']
    else:
        user = await get_user(state, user_id)
        if keys_exists(['org_rn'], user):
            return await orgs.find_one({'org_rn': user['org_rn']})
        else:
            return None


async def get_org_by_inn(org_inn: str) -> Optional[dict]:
    return await orgs.find_one({'org_inn': org_inn})


async def insert_org(state: FSMContext, org) -> None:
    await state.update_data({'org': org})
    await orgs.insert_one(org)
