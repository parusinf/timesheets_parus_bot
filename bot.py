"""
Телеграм бот взаимодействия мобильного приложения "Табели посещаемости" с учётной системой "Парус"
на основе асинхронной библиотеки aiogram
"""

import logging
import os
import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types.message import ContentType
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from pymongo import MongoClient
import config as cfg
import parus
from helpers import split_fio, temp_file_path, echo_error, keys_exists
from cp1251 import decode_cp1251
from secret_config import BOT_TOKEN

# MongoDB
client = MongoClient(cfg.MONGODB_HOST, cfg.MONGODB_PORT)
db = client['timesheets_parus_bot']
orgs = db['orgs']
users = db['users']

# Aiogram Telegram Bot
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Состояния будут представлены в хранилище как 'Form:<state>'
class Form(StatesGroup):
    inn = State()
    fio = State()
    group = State()


@dp.message_handler(commands='help')
async def cmd_help(message: types.Message):
    """
    Что может делать этот бот?
    """
    await message.reply(
        md.text(
            md.text(
                'Получение и отправка табелей из мобильного приложения ',
                md.link('Табели посещаемости', 'https://github.com/parusinf/timesheets'),
                ' в систему управления ',
                md.link('Парус', 'https://parus.com/'),
            ),
            md.text(md.bold('\nКоманды')),
            md.text(md.link('/start', '/start'), ' - получение табеля из Паруса'),
            md.text(md.link('/group', '/group'), ' - выбор другой группы'),
            md.text(md.link('/org', '/org'), ' - выбор другого учреждения'),
            md.text(md.link('/cancel', '/cancel'), ' - отмена текущей команды'),
            md.text(md.link('/reset', '/reset'), ' - отмена авторизации в Парусе'),
            md.text(md.link('/help', '/help'), ' - что может делать этот бот?'),
            md.text('\nДля отправки табеля в Парус отправьте его боту из мобильного приложения\n'),
            md.text(md.bold('\nРазработчик')),
            md.text(f'{cfg.DEVELOPER_NAME} {cfg.DEVELOPER_TELEGRAM}'),
            sep='\n',
        ),
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def receive_timesheet(message: types.Message, state: FSMContext):
    """
    Получение табеля посещаемости из Паруса
    """
    user = await get_user(state, message.from_user.id)
    if keys_exists(['db_key', 'org_rn', 'group'], user):
        try:
            # Получение табеля посещаемости из Паруса в файл CSV во временную директорию
            file_path = parus.receive_timesheet(user['db_key'], user['org_rn'], user['group'])
            # Отправка табеля посещаемости пользователю
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file:
                    org = await get_org(state, message.from_user.id)
                    org_info = f'Учреждение: {org["org_name"]}\n' if keys_exists(['org_name'], org) else None
                    await message.reply_document(
                        file,
                        caption=f'{org_info}Группа: {user["group"]}',
                        reply_markup=types.ReplyKeyboardRemove())
                # Удаление файла из временной директории
                os.remove(file_path)
        except Exception as error:
            await echo_error(f'Ошибка получения табеля посещаемости из Паруса:\n${error}')
    else:
        # Авторизация и повторное получение табеля
        await cmd_start(message, state)
    # Завершение команды
    await state.finish()


async def send_timesheet(message: types.Message, state: FSMContext, file_path):
    """
    Отправка табеля посещаемости в Парус
    """
    try:
        org = await get_org(state, message.from_user.id)
        if keys_exists(['db_key', 'company_rn', 'org_inn'], org):
            # Отправка табеля
            send_result = parus.send_timesheet(org['db_key'], org['company_rn'], file_path)
            await message.reply(send_result, reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
            return True
    except Exception as error:
        await echo_error(message, f'Ошибка отправки табеля посещаемости в Парус: {error}')
    return False


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Авторизация и отправка или получение табеля посещаемости из Паруса
    """
    user = await get_user(state, message.from_user.id)
    if keys_exists(['org_rn', 'person_rn', 'group'], user):
        # Получение табеля посещаемости из Паруса
        await receive_timesheet(message, state)
    elif not keys_exists(['org_rn'], user):
        # Обработка ИНН, если пользователь не найден
        await prompt_to_input_inn(message)
        await Form.inn.set()
    elif not keys_exists(['person_rn'], user):
        # Обработка ФИО, если его нет
        await prompt_to_input_fio(message)
        await Form.fio.set()
    elif not keys_exists(['group'], user):
        # Обработка группы, если её нет
        await prompt_to_input_group(message, state)
        await Form.group.set()


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Отмена текущей команды
    """
    await message.reply('Команда отменена', reply_markup=types.ReplyKeyboardRemove())
    await state.finish()


@dp.message_handler(lambda message: not (message.text.isdigit() and len(message.text) == 10), state=Form.inn)
async def process_inn_invalid(message: types.Message):
    """
    Проверка ИНН
    """
    return await message.reply("ИНН должен содержать 10 цифр")


@dp.message_handler(state=Form.inn)
async def process_inn(message: types.Message, state: FSMContext):
    """
    Обработка ИНН
    """
    org_inn = message.text
    # Поиск учреждения в MongoDB по ИНН
    org = orgs.find_one({'org_inn': org_inn})
    if not keys_exists(['org_name', 'company_name'], org):
        # Поиск базы данных Паруса и учреждения в ней по ИНН
        org = parus.find_org_by_inn(org_inn)
        if org is not None:
            # Учреждение найдено
            await insert_org(state, org)
        else:
            # Учреждение не найдено
            await message.reply(f'Учреждение с ИНН {org_inn} не подключено к сервису.\n'
                                f'Обратитесь к разработчику {cfg.DEVELOPER_TELEGRAM}')
            await state.finish()
            return
    # Вывод информации об учреждении
    await message.reply(f'Учреждение: {org["org_name"]}\nОрганизация: {org["company_name"]}')
    # Создание пользователя с привязкой к учреждению
    await create_user(state, message.from_user.id, org)
    # Обработка ФИО
    await prompt_to_input_fio(message)
    await Form.fio.set()


@dp.message_handler(state=Form.fio)
async def process_fio(message: types.Message, state: FSMContext):
    """
    Обработка ФИО
    """
    fio = message.text
    family, firstname, lastname = split_fio(fio)
    user = await get_user(state, message.from_user.id)
    if not keys_exists(['db_key', 'org_rn'], user):
        # Авторизация
        await cmd_start(message, state)
        return
    # Поиск сотрудника учреждения по ФИО в Парусе
    try:
        person_rn = parus.find_person_in_org(user['db_key'], user['org_rn'], family, firstname, lastname)
        # Сотрудник учреждения не найден
        if person_rn is None:
            # Сотрудник не найден в Парусе
            await message.reply(f'Сотрудник {fio} в учреждении не найден.\n'
                                f'Обратитесь к разработчику {cfg.DEVELOPER_TELEGRAM}')
            await state.finish()
            return
    except Exception as error:
        await echo_error(message, f'Ошибка поиска сотрудника в Парусе: {error}')
        await state.finish()
        return
    # Сохранение реквизитов сотрудника учреждения
    user.update({'person_rn': person_rn, 'family': family, 'firstname': firstname, 'lastname': lastname})
    await update_user(state, user)
    # Проверка наличия файла с табелем во временной директории
    data = await state.get_data()
    if keys_exists(['file_path'], data):
        file_path = data['file_path']
        if os.path.exists(file_path):
            await send_timesheet(message, state, file_path)
            del data['file_path']
            await state.set_data(data)
    else:
        # Обработка группы
        await prompt_to_input_group(message, state)
        await Form.group.set()


@dp.message_handler(state=Form.group)
async def process_group(message: types.Message, state: FSMContext):
    """
    Обработка группы
    """
    user = await get_user(state, message.from_user.id)
    if user is not None:
        # Сохранение группы
        group = message.text
        user.update({'group': group})
        await update_user(state, user)
        # Получение табеля посещаемости из Паруса
        await receive_timesheet(message, state)
    else:
        # Авторизация
        await cmd_start(message, state)


@dp.message_handler(commands='group')
async def cmd_group(message: types.Message, state: FSMContext):
    """
    Выбор другой группы
    """
    # Удаление группы
    user = await get_user(state, message.from_user.id)
    if keys_exists(['group'], user):
        del user['group']
        await update_user(state, user)
    # Обработка другой группы
    await prompt_to_input_group(message, state)
    await Form.group.set()


@dp.message_handler(commands='org')
async def cmd_org(message: types.Message, state: FSMContext):
    """
    Авторизация другого учреждения
    """
    # Удаление пользователя
    await delete_user(state, message.from_user.id)
    # Обработка другого ИНН
    await cmd_start(message, state)


@dp.message_handler(commands='reset')
async def cmd_reset(message: types.Message, state: FSMContext):
    """
    Удаление авторизации
    """
    await delete_user(state, message.from_user.id)
    await message.reply('Авторизация в Парусе отменена', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(content_types=ContentType.DOCUMENT)
async def process_timesheet(message: types.Message, state: FSMContext):
    """
    Отправка табеля посещаемости в Парус
    """
    # От пользователя получен файл с табелем посещаемости
    if message.document is not None:
        file_name = message.document['file_name']
        file_path = temp_file_path(file_name)
        file_ext = os.path.splitext(file_name)[1]
        if '.csv' == file_ext:
            try:
                # Загрузка файла от пользователя во временную директорию
                await message.document.download(destination_file=file_path)
            except Exception as error:
                await echo_error(message, f'Ошибка загрузки файла с табелем посещаемости: {error}')
            # Проверка авторизации учреждения и пользователя
            org_inn_from_file = get_org_inn_from_file(file_path)
            org = await get_org(state, message.from_user.id)
            user = await get_user(state, message.from_user.id)
            if keys_exists(['org_inn'], org) and org_inn_from_file == org['org_inn'] \
                    and keys_exists(['person_rn'], user):
                # Отправка табеля посещаемости в Парус
                if await send_timesheet(message, state, file_path):
                    return
            # Сохранение пути файла для загрузки после авторизации
            await state.update_data({'file_path': file_path})
            # Удаление авторизации в другом учреждении
            if keys_exists(['org_inn'], org):
                await delete_user(state, message.from_user.id)
            # Авторизация в учреждении с ИНН в табеле
            message.text = org_inn_from_file
            await process_inn(message, state)
        else:
            await echo_error(message, 'Файл не содержит табель посещаемости')


def get_org_inn_from_file(file_path):
    """
    Получение ИНН учреждения из файла табеля
    """
    with open(file_path, 'rb') as file:
        file_content = decode_cp1251(file.read())
    file_lines = file_content.splitlines()
    org_fields = file_lines[1].split(';') if len(file_lines) >= 2 else None
    return org_fields[1] if len(org_fields) >= 2 else None


async def prompt_to_input_inn(message: types.Message):
    """
    Приглашение к вводу ИНН учреждения
    """
    await message.reply("ИНН вашего учреждения?")


async def prompt_to_input_fio(message: types.Message):
    """
    Приглашение к вводу ФИО сотрудника учреждения
    """
    await message.reply('Ваши Фамилия Имя Отчество?')


async def prompt_to_input_group(message: types.Message, state):
    """
    Приглашение к выбору групп учреждения
    """
    user = await get_user(state, message.from_user.id)
    # Получение списка групп учреждения
    if keys_exists(['db_key', 'org_rn'], user):
        try:
            groups = parus.get_groups(user['db_key'], user['org_rn'])
            # Действующие группы в учреждении не найдены
            if groups is None:
                raise AttributeError('Действующие группы в учреждении не найдены')
            # Приглашение к выбору группы учреждения
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            markup.add(*groups.split(';'))
            await message.reply('Выберите группу', reply_markup=markup)
        except Exception as error:
            await echo_error(message, f'Ошибка получения списка групп из Паруса: {error}')
            await state.finish()
    else:
        # Авторизация
        await cmd_start(message, state)


async def get_user(state, user_id):
    data = await state.get_data()
    if 'user' in data:
        return data['user']
    else:
        return users.find_one({'user_id': user_id})


async def create_user(state, user_id, org):
    user = {
        'db_key': org['db_key'],
        'user_id': user_id,
        'org_rn': org['org_rn'],
    }
    await state.update_data({'user': user})
    users.insert_one(user)


async def update_user(state, user):
    await state.update_data({'user': user})
    users.update_one(
        {'user_id': user['user_id']},
        {'$set': user}
    )


async def delete_user(state, user_id):
    data = await state.get_data()
    if keys_exists(['user'], data):
        del data['user']
        await state.set_data(data)
    users.delete_one({'user_id': user_id})


async def get_org(state, user_id):
    data = await state.get_data()
    if keys_exists(['org'], data):
        return data['org']
    else:
        user = await get_user(state, user_id)
        if keys_exists(['org_rn'], user):
            return orgs.find_one({'org_rn': user['org_rn']})
        else:
            return None


async def insert_org(state, org):
    await state.update_data({'org': org})
    orgs.insert_one(org)


async def on_startup(dispatcher):
    logging.info('Starting webhook connection')
    from aiogram.types.input_file import InputFile
    from pathlib import Path
    from secret_config import CERTIFICATE_PATH
    await bot.set_webhook(
       cfg.WEBHOOK_URL,
       certificate=InputFile(Path(CERTIFICATE_PATH)),
       drop_pending_updates=True)


async def on_shutdown(dispatcher):
    await bot.set_webhook('')
    logging.info('Shutting down webhook connection')


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    from aiogram.utils.executor import start_webhook
    start_webhook(
        dispatcher=dp,
        webhook_path=cfg.WEBHOOK_PATH,
        skip_updates=True,
        host=cfg.WEBAPP_HOST,
        port=cfg.WEBAPP_PORT,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )
