"""
Телеграм бот взаимодействия мобильного приложения "Табели посещаемости" с учётной системой "Парус"
на основе асинхронной библиотеки aiogram
"""
import logging
import os
import signal
import sys

from aiogram import Dispatcher
from app.settings import config, BASE_DIR
from app.store.cache.models import db as cache
from app.tsheebot.bot import bot, dp
from app.sys.pid_file import read_pid_file, write_pid_file, remove_pid_file


logging.basicConfig(
    filename=config['log_file'] if config['use_log_file'] else None,
    level=logging.INFO)


async def on_startup(_: Dispatcher):
    logging.info(f'Подключение кэша')
    await cache.on_connect()
    logging.info(f'Подключение вебхука')
    from aiogram.types.input_file import InputFile
    from pathlib import Path
    await bot.set_webhook(
       f'{config["webhook"]["url"]}/bot{config["bot_token"]}',
       certificate=InputFile(Path(os.path.join(BASE_DIR, config['webhook']['cert_path']))),
       drop_pending_updates=True)
    if config['use_pid_file']:
        pid_from_os = write_pid_file()
        pid_info = f' pid={pid_from_os}'
    else:
        pid_info = ''
    logging.info(f'tsheebot запущен{pid_info}')


async def on_shutdown(_: Dispatcher):
    logging.info(f'Отключение вебхука')
    await bot.set_webhook('')
    logging.info(f'Отключение кэша')
    await cache.on_disconnect()
    if config['pid_file']:
        pid_from_file = remove_pid_file()
        pid_info = f' pid={pid_from_file}'
    else:
        pid_info = ''
    logging.info(f'tsheebot остановлен{pid_info}')


def stop(pid):
    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        logging.error(f'Процесс с pid={pid} не найден')


def run(command):
    pid_from_file = read_pid_file()
    if command == 'start':
        if pid_from_file:
            exit()
    elif command == 'stop' and pid_from_file:
        stop(pid_from_file)
        exit()
    elif command == 'restart':
        if pid_from_file:
            stop(pid_from_file)
    else:
        logging.warning(f'Использование: {os.path.join(config.PROGRAM, sys.argv[0])} [start|stop|restart]')


if __name__ == '__main__':
    if config['pid_file'] and len(sys.argv) == 2:
        run(sys.argv[1])
    try:
        from aiogram.utils.executor import start_webhook
        start_webhook(
            dispatcher=dp,
            webhook_path=f'/bot{config["bot_token"]}',
            skip_updates=True,
            host=config['bot']['host'],
            port=config['bot']['port'],
            on_startup=on_startup,
            on_shutdown=on_shutdown,
        )
    except Exception as exception:
        if config['pid_file']:
            remove_pid_file()
        raise exception
