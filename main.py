"""
Телеграм бот взаимодействия мобильного приложения "Табели посещаемости" с учётной системой "Парус"
на основе асинхронной библиотеки aiogram
"""
import logging
from aiogram import Dispatcher
from app.settings import config, config_token, BASE_DIR
from app.store.parus.models import db
from app.tsheebot.bot import bot, dp


async def on_startup(_: Dispatcher):
    logging.info(f'Starting parus connections')
    await db.on_connect()
    logging.info(f'Starting webhook connection')
    from aiogram.types.input_file import InputFile
    from pathlib import Path
    await bot.set_webhook(
       f"{config['webhook']['url']}/bot{config_token['token']}",
       certificate=InputFile(Path(BASE_DIR/config['webhook']['cert_path'])),
       drop_pending_updates=True)


async def on_shutdown(_: Dispatcher):
    logging.info(f'Shutting down parus connections')
    await db.on_disconnect()
    logging.info(f'Shutting down webhook connection')
    await bot.set_webhook('')


if __name__ == '__main__':
    from aiogram.utils.executor import start_webhook
    start_webhook(
        dispatcher=dp,
        webhook_path=f"/bot{config_token['token']}",
        skip_updates=True,
        host=config['webapp']['host'],
        port=config['webapp']['port'],
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )
