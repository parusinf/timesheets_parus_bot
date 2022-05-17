"""
Вспомогательные функции
"""


def split_fio(fio):
    """
    Разделение строки "Фамилия Имя Отчество" на кортеж (Фамилия, Имя, Отчество)
    :param fio: строка ФИО
    :return: кортеж ФИО
    """
    fio_split = fio.split(' ', 2)
    return tuple(fio_split[i] if len(fio_split) > i else None for i in range(3))


def temp_filepath(filename):
    from os.path import join
    from tempfile import gettempdir
    return join(gettempdir(), filename)


async def echo_error(message, error):
    error_message = error or 'Пропущено сообщение об ошибке'
    await message.reply(error_message)
    from logging import error
    error(error_message)


def keys_exists(keys, dictionary):
    """
    Проверка наличия всех ключей в списке в заданном словаре
    :param keys: список ключей
    :param dictionary: словарь, в котором осуществляется поиск ключей
    :return: True - в словаре есть все ключи, False - в словаре нет хотя бы одного ключа
    """
    if keys and dictionary:
        return all(key in dictionary.keys() for key in keys)
    else:
        return False


def os_environ(env, default=None):
    from os import environ
    return environ[env] if keys_exists([env], environ) else default
