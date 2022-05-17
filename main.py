"""
Телеграм бот взаимодействия мобильного приложения "Табели посещаемости" с учётной системой "Парус"
на основе асинхронной библиотеки aiogram
"""
import logging
import os
from aiogram import Dispatcher
from app.settings import config, BASE_DIR
from app.store.cache.models import db as cache
from app.tsheebot.bot import bot, dp


async def on_startup(_: Dispatcher):
    logging.info(f'Подключение кэша')
    await cache.on_connect()
    logging.info(f'Запуск вебхука')
    from aiogram.types.input_file import InputFile
    from pathlib import Path
    await bot.set_webhook(
       f'{config["webhook"]["url"]}/bot{config["bot_token"]}',
       certificate=InputFile(Path(os.path.join(BASE_DIR, config['webhook']['cert_path']))),
       drop_pending_updates=True)


async def on_shutdown(_: Dispatcher):
    logging.info(f'Останов вебхука')
    await bot.set_webhook('')
    logging.info(f'Отключение кэша')
    await cache.on_disconnect()


if __name__ == '__main__':
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
