import os
from io import BytesIO
import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types.message import ContentType
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InputFile
import app.store.websrv.models as websrv
import app.store.cache.models as cache
import app.tsheebot.models as tsheebot
from tools.helpers import split_fio, echo_error, keys_exists
from tools.cp1251 import decode_cp1251
from app.settings import config


# Команды бота
BOT_COMMANDS = '''start - получение табеля из Паруса
group - выбор другой группы
org - выбор другого учреждения
cancel - отмена текущей команды
reset - отмена авторизации в Парусе
ping - проверка отклика бота
help - что может делать этот бот?'''

# Aiogram Telegram Bot
bot = Bot(token=config['bot_token'])
dp = Dispatcher(bot, storage=MemoryStorage())


# Состояния конечного автомата
class Form(StatesGroup):
    inn = State()    # ввод ИНН учреждения
    org = State()    # выбор учреждения
    fio = State()    # ввод ФИО сотрудника
    group = State()  # выбор группы учреждения


async def receive_timesheet(message: types.Message, state: FSMContext):
    """
    Получение табеля посещаемости из Паруса
    """
    org = await cache.get_user_org(message.from_user.id)
    user = await cache.get_user(message.from_user.id)
    if org and user['org_id'] and user['group']:
        try:
            # Получение табеля посещаемости из Паруса в файл CSV во временную директорию
            content, filename, status, reason = \
                await websrv.receive_timesheet(org['db_key'], org['org_rn'], user['group'])
            # Отправка табеля посещаемости пользователю
            if status == 200:
                await message.reply_document(
                    InputFile(BytesIO(content), filename),
                    caption=f'Учреждение: {org["org_name"]}\nГруппа: {user["group"]}',
                    reply_markup=types.ReplyKeyboardRemove())
            else:
                raise Exception(f'{status} {reason}')
        except Exception as error:
            await echo_error(message, f'Ошибка получения табеля посещаемости из Паруса: {error}')
    else:
        # Авторизация и повторное получение табеля
        await cmd_start(message, state)
    # Завершение команды
    await state.finish()


async def send_timesheet(message: types.Message, state: FSMContext, content, filename):
    """Отправка табеля посещаемости в Парус"""
    org = await cache.get_user_org(message.from_user.id)
    if org:
        # Отправка табеля
        result = await websrv.send_timesheet(org['db_key'], org['company_rn'], content, filename)
        await message.reply(result, reply_markup=types.ReplyKeyboardRemove())
        await state.finish()
        return True
    else:
        return False


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message, state: FSMContext):
    """Авторизация и отправка или получение табеля посещаемости из Паруса"""
    user = await cache.get_user(message.from_user.id)
    if not user:
        # Обработка ИНН, если пользователь не авторизован
        await prompt_to_input_inn(message)
        await Form.inn.set()
    elif not user['org_id']:
        # Обработка учреждения, если оно не выбрано
        await _process_orgs_by_inn(message, state, user)
    elif not user['person_rn']:
        # Обработка ФИО, если его нет
        await prompt_to_input_fio(message)
        await Form.fio.set()
    elif not user['group']:
        # Обработка группы, если её нет
        await prompt_to_input_group(message, state)
        await Form.group.set()
    elif user['org_id'] and user['person_rn'] and user['group']:
        # Получение табеля посещаемости из Паруса
        await receive_timesheet(message, state)


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """Отмена текущей команды"""
    await message.reply('Команда отменена', reply_markup=types.ReplyKeyboardRemove())
    await state.finish()


@dp.message_handler(lambda message: not (message.text.isdigit() and len(message.text) == 10), state=Form.inn)
async def process_inn_invalid(message: types.Message):
    """Проверка ИНН"""
    return await message.reply("ИНН должен содержать 10 цифр")


async def _update_user_org(message: types.Message, user, org):
    user.update({'org_id': org['id']})
    await cache.update_user(user)
    await message.reply(f'Учреждение: {org["org_name"]}')
    await prompt_to_input_fio(message)
    await Form.fio.set()


@dp.message_handler(state=Form.inn)
async def process_inn(message: types.Message, state: FSMContext):
    """Обработка ИНН"""
    org_inn = message.text
    # Создание пользователя с ИНН
    user = {
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'user_first_name': message.from_user.first_name,
        'user_last_name': message.from_user.last_name,
        'org_inn': org_inn,
    }
    await cache.insert_user(user)
    await _process_orgs_by_inn(message, state, user)


async def _process_orgs_by_inn(message: types.Message, state: FSMContext, user):
    org_inn = user['org_inn']
    orgs = await tsheebot.get_orgs(org_inn)
    # Учреждение не найдено
    if len(orgs) == 0:
        await message.reply(f'Учреждение с ИНН {org_inn} не подключено к сервису.\n'
                            f'Обратитесь к разработчику {config["developer"]["telegram"]}')
        await state.finish()
    # Найдено одно учреждение
    elif len(orgs) == 1:
        await _update_user_org(message, user, orgs[0])
    # Найдено более одного учреждения
    elif len(orgs) > 1:
        await prompt_to_input_org(message, orgs)
        await Form.org.set()


@dp.message_handler(state=Form.org)
async def process_org(message: types.Message, state: FSMContext):
    """Обработка учреждения"""
    org_code = message.text
    user = await cache.get_user(message.from_user.id)
    if not user['org_inn']:
        await prompt_to_input_inn(message)
        await Form.inn.set()
        return
    # Поиск учреждения по мнемокоду и ИНН
    org = await tsheebot.get_org(org_code, user['org_inn'])
    # Учреждение не найдено
    if not org:
        await message.reply(f'Учреждение с мнемокодом "{org_code}" и ИНН {user["org_inn"]} не подключено к сервису.\n'
                            f'Обратитесь к разработчику {config["developer"]["telegram"]}')
        await state.finish()
    # Учреждение найдено
    else:
        await _update_user_org(message, user, org)


@dp.message_handler(state=Form.fio)
async def process_fio(message: types.Message, state: FSMContext):
    """Обработка ФИО"""
    fio = message.text
    family, firstname, lastname = split_fio(fio)
    user = await cache.get_user(message.from_user.id)
    org = await cache.get_user_org(message.from_user.id)
    # Поиск сотрудника учреждения по ФИО в веб-сервисе
    person_rn = await websrv.get_person(org['db_key'], org['org_rn'], family, firstname, lastname)
    # Сотрудник учреждения найден
    if person_rn:
        # Сохранение реквизитов сотрудника
        user.update({'person_rn': person_rn, 'family': family, 'firstname': firstname, 'lastname': lastname})
        await cache.update_user(user)
        # Отправка табеля, присланного до этого без авторизации
        data = await state.get_data()
        if keys_exists(['content', 'filename'], data):
            content = data['content']
            filename = data['filename']
            if os.path.exists(filename):
                await send_timesheet(message, state, content, filename)
                del data['content']
                del data['filename']
                await state.set_data(data)
        # Обработка группы
        else:
            await prompt_to_input_group(message, state)
            await Form.group.set()
    # Сотрудник не найден в Парусе
    else:
        await message.reply(f'Сотрудник {fio} в учреждении не найден.\n'
                            f'Обратитесь к разработчику {config["developer"]["telegram"]}')
        await state.finish()


@dp.message_handler(state=Form.group)
async def process_group(message: types.Message, state: FSMContext):
    """
    Обработка группы
    """
    user = await cache.get_user(message.from_user.id)
    if user:
        # Сохранение группы
        group = message.text
        user['group'] = group
        await cache.update_user(user)
        # Получение табеля посещаемости из Паруса
        await receive_timesheet(message, state)
    else:
        # Авторизация
        await cmd_start(message, state)


@dp.message_handler(commands='group')
async def cmd_group(message: types.Message, state: FSMContext):
    """Выбор другой группы"""
    # Удаление группы
    user = await cache.get_user(message.from_user.id)
    if user['group']:
        del user['group']
        await cache.update_user(user)
    # Обработка другой группы
    await prompt_to_input_group(message, state)
    await Form.group.set()


@dp.message_handler(commands='org')
async def cmd_org(message: types.Message, state: FSMContext):
    """Авторизация другого учреждения"""
    await cache.delete_user(message.from_user.id)
    await cmd_start(message, state)


@dp.message_handler(commands='reset')
async def cmd_reset(message: types.Message):
    """Удаление авторизации"""
    await cache.delete_user(message.from_user.id)
    await message.reply('Авторизация в Парусе отменена', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands='ping')
async def cmd_ping(message: types.Message):
    """Проверка отклика бота"""
    await message.reply('pong')


@dp.message_handler(commands='help')
async def cmd_help(message: types.Message):
    """Что может делать этот бот?"""
    def format_command(command_line):
        command, desc = [x.strip() for x in command_line.split('-')]
        return md.text(md.link(f'/{command}', f'/{command}'), f' - {desc}')

    commands = [format_command(cl) for cl in BOT_COMMANDS.splitlines()]
    await message.reply(
        md.text(
            md.text(
                'Получение и отправка табелей из мобильного приложения ',
                md.link('Табели посещаемости', 'https://github.com/parusinf/timesheets'),
                ' в систему управления ',
                md.link('Парус', 'https://parus.com/'),
            ),
            md.text(md.bold('\nКоманды')),
            *commands,
            md.text('\nДля отправки табеля в Парус отправьте его боту из мобильного приложения\n'),
            md.text(md.bold('Разработчик')),
            md.text(f'{config["developer"]["name"]} {config["developer"]["telegram"]}'),
            sep='\n',
        ),
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message_handler(content_types=ContentType.DOCUMENT)
async def process_timesheet(message: types.Message, state: FSMContext):
    """Отправка табеля посещаемости в Парус"""
    # От пользователя получен файл с табелем посещаемости
    if message.document:
        filename = message.document['file_name']
        file_ext = os.path.splitext(filename)[1]
        if '.csv' == file_ext:
            # Загрузка файла от пользователя в байтовый буфер
            buffer = BytesIO()
            await message.document.download(destination_file=buffer)
            content = buffer.read()
            # Проверка авторизации учреждения и пользователя
            org_code, org_inn = _extract_org_code_inn(content)
            org = await cache.get_user_org(message.from_user.id)
            user = await cache.get_user(message.from_user.id)
            if org and org_code == org['org_code'] and org_inn == org['org_inn'] and user['person_rn']:
                # Отправка табеля посещаемости в Парус
                if await send_timesheet(message, state, content, filename):
                    return
            # Сохранение табеля для загрузки после авторизации
            await state.update_data({'content': content, 'filename': filename})
            # Удаление авторизации в другом учреждении
            if org:
                await cache.delete_user(message.from_user.id)
            # Авторизация в учреждении с ИНН в табеле
            message.text = org_inn
            await process_inn(message, state)
        else:
            await echo_error(message, 'Файл не содержит табель посещаемости')


def _extract_org_code_inn(content):
    """Извлечение мнемокода и ИНН учреждения из табеля"""
    decoded = decode_cp1251(content)
    lines = decoded.splitlines()
    org_fields = lines[1].split(';') if len(lines) >= 2 else None
    return org_fields[:2] if len(org_fields) >= 2 else None


async def prompt_to_input_inn(message: types.Message):
    """Приглашение к вводу ИНН учреждения"""
    await message.reply('ИНН вашего учреждения?')


async def prompt_to_input_fio(message: types.Message):
    """Приглашение к вводу ФИО сотрудника учреждения"""
    await message.reply('Ваши Фамилия Имя Отчество?', reply_markup=types.ReplyKeyboardRemove())


async def prompt_to_input_group(message: types.Message, state: FSMContext):
    """Приглашение к выбору групп учреждения"""
    org = await cache.get_user_org(message.from_user.id)
    # Получение списка групп учреждения
    if org:
        try:
            group_codes = await websrv.get_groups(org['db_key'], org['org_rn'])
            # Действующие группы в учреждении не найдены
            if not group_codes:
                raise Exception('Действующие группы в учреждении не найдены')
            # Приглашение к выбору группы учреждения
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            markup.add(*group_codes)
            await message.reply('Выберите группу', reply_markup=markup)
        except Exception as error:
            await echo_error(message, f'Ошибка получения списка групп из Паруса: {error}')
            await state.finish()
    else:
        # Авторизация
        await cmd_start(message, state)


async def prompt_to_input_org(message: types.Message, orgs):
    """Приглашение к выбору учреждения"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    org_codes = [o['org_code'] for o in orgs]
    markup.add(*org_codes)
    await message.reply('Выберите учреждение', reply_markup=markup)
