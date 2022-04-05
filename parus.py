"""
Функции для взаимодействия бота с Парусом

В файле secret_config.py должен быть описан словарь parus_db_dict с базами данных Oracle для подключению к Парусу:
parus_db_dict = {
    'unique_db_key': ('<db_user>', '<db_user_password>', '<host>:<port>/<sid>'),
}
"""

import logging
from datetime import datetime
import cx_Oracle
import config as cfg
from secret_config import parus_db_dict
from helpers import temp_file_path
import os
from cp1251 import encode_cp1251, decode_cp1251


os.environ["NLS_LANG"] = cfg.parus_db_encoding


def find_org_by_inn(inn):
    """
    Поиск базы данных Паруса и учреждения в ней по ИНН
    :param inn: ИНН
    """
    # Поиск Паруса, обслуживающего учреждение с заданным ИНН
    for db_key, db in parus_db_dict.items():
        try:
            # Соединение с Парусом
            with cx_Oracle.connect(*db) as connection:
                # Создание курсора
                with connection.cursor() as cursor:
                    # Выходные параметры процедуры Паруса
                    rn_var = cursor.var(int)
                    code_var = cursor.var(str)
                    agent_name_var = cursor.var(str)
                    company_rn_var = cursor.var(int)
                    company_agent_name_var = cursor.var(str)
                    # Вызов процедуры Паруса
                    cursor.callproc('UDO_FIND_PSORG_BY_INN',
                                    [inn, rn_var, code_var, agent_name_var, company_rn_var, company_agent_name_var])
                    rn = rn_var.getvalue()
                    if rn is not None:
                        return {
                            'db_key': db_key,
                            'inn': inn,
                            'rn': rn,
                            'code': code_var.getvalue(),
                            'agent_name': agent_name_var.getvalue(),
                            'company_rn': company_rn_var.getvalue(),
                            'company_agent_name': company_agent_name_var.getvalue(),
                        }
        except cx_Oracle.Error as error:
            logging.error(error)
            continue
    return None


def find_person_in_org(db_key, org_rn, family, firstname, lastname):
    """
    Поиск сотрудника в учреждении
    :param db_key: ключ базы данных Паруса
    :param org_rn: RN учреждения
    :param family: фамилия
    :param firstname: имя
    :param lastname: отчество
    :return: RN сотрудника
    """
    # Соединение с Парусом
    db = parus_db_dict[db_key]
    with cx_Oracle.connect(*db) as connection:
        # Создание курсора
        with connection.cursor() as cursor:
            # Выходные параметры процедуры Паруса
            person_rn_var = cursor.var(int)
            # Вызов процедуры Паруса
            cursor.callproc('UDO_FIND_PERSON_BY_FIO', [org_rn, family, firstname, lastname, person_rn_var])
            return person_rn_var.getvalue()


def get_groups(db_key, org_rn):
    """
    Получение списка групп учреждения
    :param db_key: ключ базы данных Паруса
    :param org_rn: RN учреждения
    :return: список мнемокодов групп через ";"
    """
    # Соединение с Парусом
    db = parus_db_dict[db_key]
    with cx_Oracle.connect(*db) as connection:
        # Создание курсора
        with connection.cursor() as cursor:
            # Выходные параметры процедуры Паруса
            groups_var = cursor.var(str)
            # Вызов процедуры Паруса
            cursor.callproc('UDO_P_PSORG_GET_GROUPS', [org_rn, groups_var])
            return groups_var.getvalue()


def receive_timesheet(db_key, org_rn, group, period=datetime.now()):
    """
    Получение табеля посещаемости группы в файле CSV
    :param db_key: ключ базы данных Паруса
    :param org_rn: RN учреждения
    :param group: мнемокод группы
    :param period: период табеля (любой день месяца)
    :return: имя файла с табелем посещаемости в формате CSV во временной директории
    """
    # Соединение с Парусом
    db = parus_db_dict[db_key]
    with cx_Oracle.connect(*db) as connection:
        # Создание курсора
        with connection.cursor() as cursor:
            # Выходные параметры процедуры Паруса
            file_name_var = cursor.var(str)
            file_content_var = cursor.var(cx_Oracle.DB_TYPE_CLOB)
            # Вызов процедуры Паруса
            cursor.callproc('UDO_P_SEND_TIMESHEET', [org_rn, group, period, file_name_var, file_content_var])
            # Запись табеля посещаемости в файл в кодировке cp1251
            file_path = temp_file_path(file_name_var.getvalue())
            file_content = file_content_var.getvalue().read()
            with open(file_path, 'wb') as file:
                file.write(encode_cp1251(file_content))
            return file_path


def send_timesheet(db_key, company_rn, file_path):
    """
    Получение табеля посещаемости группы в формате CSV
    :param db_key: ключ базы данных Паруса
    :param company_rn: RN организации
    :param file_path: имя файла с табелем посещаемости в формате CSV во временной директории
    :return: результат отправки табеля посещаемости в Парус
    """
    # Соединение с Парусом
    db = parus_db_dict[db_key]
    with cx_Oracle.connect(*db) as connection:
        # Создание курсора
        with connection.cursor() as cursor:
            # Чтение табеля посещаемости из файла в кодировке cp1251
            with open(file_path, 'rb') as file:
                file_content = decode_cp1251(file.read())
            # Выходные параметры процедуры Паруса
            result_var = cursor.var(str)
            # Вызов процедуры Паруса
            cursor.callproc('UDO_P_RECEIVE_TIMESHEET', [company_rn, file_content, result_var])
            connection.commit()
            return result_var.getvalue()
