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
    fio_split = fio.split(' ', 2)
    return tuple(fio_split[i] if len(fio_split) > i else None for i in range(3))


def temp_file_path(file_name):
    return os.path.join(gettempdir(), file_name)


def keys_exists(keys, dictionary):
    """
    Проверка наличия всех ключей в списке в заданном словаре
    :param keys: список ключей
    :param dictionary: словарь, в котором осуществляется поиск ключей
    :return: True - в словаре есть все ключи, False - в словаре нет хотя бы одного ключа
    """
    if dictionary is not None:
        for key in keys:
            if key not in dictionary:
                return False
        return True
    else:
        return False


async def echo_error(message, error):
    error_message = error or 'Пропущено сообщение об ошибке'
    await message.reply(error_message)
    logging.error(error_message)
