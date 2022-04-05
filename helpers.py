"""
Вспомогательные функции
"""

import logging
import os
from tempfile import gettempdir


def split_fio(fio):
    """
    Разделение строки "Фамилия Имя Отчество" на кортеж (Фамилия, Имя, Отчество)
    :param fio: строка ФИО
    :return: кортеж ФИО
    """
    fio_split = fio.split(" ", 2)
    return tuple(fio_split[i] if len(fio_split) > i else None for i in range(3))


def temp_file_path(file_name):
    return os.path.join(gettempdir(), file_name)


async def echo_error(message, error):
    error_message = error or 'Пропущено сообщение об ошибке'
    await message.reply(error_message)
    logging.error(error_message)
