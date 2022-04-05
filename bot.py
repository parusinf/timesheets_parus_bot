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
from aiogram.utils import executor
from pymongo import MongoClient
import config as cfg
from secret_config import bot_token
import parus
from helpers import split_fio, temp_file_path, echo_error


# MongoDB
client = MongoClient(cfg.mongodb_host, cfg.mongodb_port)
db = client['timesheets_parus_bot']
orgs = db['orgs']
users = db['users']

# Aiogram Telegram Bot
logging.basicConfig(level=logging.INFO)
bot = Bot(token=bot_token)
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
            md.text(f'{cfg.developer_name} {cfg.developer_telegram}'),
            sep='\n',
        ),
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def receive_timesheet(message, state, user):
    """
    Получение табеля посещаемости из Паруса
    """
    # Информирование пользователя о длительной операции
    await message.reply('Получение табеля посещаемости из Паруса...', reply_markup=types.ReplyKeyboardRemove())
    # Получение табеля посещаемости из Паруса в файл CSV во временную директорию
    try:
        file_path = parus.receive_timesheet(user['db_key'], user['org_rn'], user['group'])
        # Отправка пользователю табеля посещаемости
        with open(file_path, 'rb') as file:
            await message.reply_document(file)
        # Удаление файла из временной директории
        os.remove(file_path)
    except Exception as error:
        await message.reply(f'Ошибка получения табеля посещаемости из Паруса:\n${error}')
    # Завершение команды
    await state.finish()


async def prompt_to_input_inn(message):
    """
    Приглашение к вводу ИНН учреждения
    """
    await message.reply("ИНН вашего учреждения?")


async def prompt_to_input_fio(message):
    """
    Приглашение к вводу ФИО сотрудника учреждения
    """
    await message.reply('Ваши Фамилия Имя Отчество?')


async def prompt_to_input_group(message, db_key, org_rn):
    """
    Приглашение к выбору групп учреждения
    """
    # Информирование пользователя о длительной операции
    await message.reply('Получение списка групп...')
    # Получение списка групп учреждения
    groups = parus.get_groups(db_key, org_rn)
    # Действующие группы в учреждении не найдены
    if groups is None:
        raise AttributeError('Действующие группы в учреждении не найдены')
    # Приглашение к выбору группы учреждения
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add(*groups.split(';'))
    await message.reply('Выберите группу', reply_markup=markup)


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Авторизация и отправка табеля посещаемости
    """
    # Поиск пользователя в MongoDB
    user = await users.find_one({'user_id': message.from_user.id})
    if user is None:
        # Обработка ИНН, если его нет
        await prompt_to_input_inn(message)
        await Form.inn.set()
    elif 'person_rn' not in user:
        # Обработка ФИО, если его нет
        await prompt_to_input_fio(message)
        await Form.fio.set()
    elif 'group' not in user:
        # Обработка группы, если её нет
        try:
            await prompt_to_input_group(message, user['db_key'], user['org_rn'])
            await Form.group.set()
        except Exception as error:
            await echo_error(message, f'Ошибка получения списка групп из Паруса: {error}')
            await state.finish()
    else:
        # Получение табеля посещаемости из Паруса
        await receive_timesheet(message, state, user)


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
    inn = message.text
    # Поиск учреждения в MongoDB по ИНН
    org = await orgs.find_one({'inn': inn})
    if org is None:
        # Информирование пользователя о длительной операции
        await message.reply('Авторизация учреждения...')
        # Поиск базы данных Паруса и учреждения в ней по ИНН
        org = parus.find_org_by_inn(inn)
        if org is not None:
            # Учреждение найдено
            await orgs.insert_one(org)
        else:
            # Учреждение не найдено
            await message.reply(f'Учреждение с ИНН {inn} не подключено к сервису.\n'
                                f'Обратитесь к разработчику {cfg.developer_telegram}')
            await state.finish()
            return
    # Вывод информации об учреждении
    await message.reply(f'Учреждение: {org["agent_name"]}\nОрганизация: {org["company_agent_name"]}')
    # Добавление пользователя с привязкой к учреждению в MongoDB
    await users.insert_one({
        'db_key': org['db_key'],
        'user_id': message.from_user.id,
        'chat_id': message.chat.id,
        'org_rn': org['rn'],
    })
    # Следующее состояние: обработка ФИО
    await prompt_to_input_fio(message)
    await Form.next()


@dp.message_handler(state=Form.fio)
async def process_fio(message: types.Message, state: FSMContext):
    """
    Обработка ФИО
    """
    fio = message.text
    family, firstname, lastname = split_fio(fio)
    lastname_str = f'"{lastname}"' if lastname is not None else 'без отчества'
    # Поиск пользователя в MongoDB
    user = await users.find_one({'user_id': message.from_user.id})
    # Поиск учреждения в MongoDB
    await message.reply('Авторизация пользователя...')
    # Поиск сотрудника учреждения по ФИО в Парусе
    try:
        person_rn = parus.find_person_in_org(user['db_key'], user['org_rn'], family, firstname, lastname)
        # Сотрудник учреждения не найден
        if person_rn is None:
            org = await orgs.find_one({'rn': user['org_rn']})
            # Сотрудник не найден в Парусе
            await message.reply(f'Сотрудник (фамилия: "{family}", имя: "{firstname}", отчество: {lastname_str}) '
                                f'в учреждении "{org["agent_name"]}" не найден.\n'
                                f'Обратитесь к разработчику {cfg.developer_telegram}')
            await state.finish()
            return
    except Exception as error:
        await echo_error(message, f'Ошибка поиска сотрудника в Парусе: {error}')
        await state.finish()
        return
    # Сотрудник учреждения найден
    lastname_with_space = f' {lastname}' if lastname is not None else None
    await message.reply(f'{firstname}{lastname_with_space}, добро пожаловать!')
    await users.update_one(
        {'user_id': message.from_user.id},
        {'$set': {'person_rn': person_rn, 'family': family, 'firstname': firstname, 'lastname': lastname}}
    )
    # Следующее состояние: обработка группы
    await prompt_to_input_group(message, user['db_key'], user['org_rn'])
    await Form.next()


@dp.message_handler(state=Form.group)
async def process_group(message: types.Message, state: FSMContext):
    """
    Обработка группы
    """
    group = message.text
    user = await users.find_one({'user_id': message.from_user.id})
    # Поиск группы учреждения в Парусе
    # Сохранение группы
    await users.update_one(
        {'user_id': message.from_user.id},
        {'$set': {'group': group}}
    )
    user['group'] = group
    # Получение табеля посещаемости из Паруса
    await receive_timesheet(message, state, user)


@dp.message_handler(commands='group')
async def cmd_group(message: types.Message, state: FSMContext):
    """
    Выбор другой группы
    """
    # Удаление группы
    await users.update_one(
        {'user_id': message.from_user.id},
        {'$unset': {'group': 1}}
    )
    # Обработка другой группы
    await cmd_start(message, state)


@dp.message_handler(commands='org')
async def cmd_org(message: types.Message, state: FSMContext):
    """
    Авторизация другого учреждения
    """
    # Удаление учреждения и группы
    await users.delete_one({'user_id': message.from_user.id})
    # Обработка другого ИНН
    await cmd_start(message, state)


@dp.message_handler(commands='reset')
async def cmd_reset(message: types.Message):
    """
    Удаление авторизации
    """
    await users.delete_one({'user_id': message.from_user.id})
    await message.reply('Авторизация удалена', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(content_types=ContentType.DOCUMENT)
async def process_timesheet(message: types.Message):
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
                # Загрузка файла во временную директорию
                await message.document.download(destination_file=file_path)
                # Поиск пользователя в MongoDB
                user = await users.find_one({'user_id': message.from_user.id})
                # Поиск учреждения в MongoDB
                org = await orgs.find_one({'rn': user['org_rn']})
                # Информирование пользователя о длительной операции
                await message.reply('Отправка табеля посещаемости в Парус...', reply_markup=types.ReplyKeyboardRemove())
                send_result = parus.send_timesheet(org['db_key'], org['company_rn'], file_path)
                await message.reply(send_result)
            except Exception as error:
                await echo_error(message, f'Ошибка загрузки файла с табелем посещаемости: {error}')
        else:
            await echo_error(message, 'Файл не содержит табель посещаемости')


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
