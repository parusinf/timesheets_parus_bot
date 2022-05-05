from datetime import datetime
import cx_Oracle
import logging
from typing import Optional
from app.store.parus.accessor import OracleAccessor
from tools.cp1251 import encode_cp1251, decode_cp1251
from tools.helpers import temp_file_path

db = OracleAccessor()


async def get_org_by_inn(inn: str) -> Optional[dict]:
    """Поиск Паруса, обслуживающего учреждение с заданным ИНН"""
    for db_key, pool in db.pool.items():
        try:
            async with pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    rn_var = await cursor.var(int)
                    code_var = await cursor.var(str)
                    agent_name_var = await cursor.var(str)
                    company_rn_var = await cursor.var(int)
                    company_agent_name_var = await cursor.var(str)
                    await cursor.callproc(
                        'UDO_FIND_PSORG_BY_INN',
                        [inn, rn_var, code_var, agent_name_var, company_rn_var, company_agent_name_var])
                    rn = rn_var.getvalue()
                    if rn:
                        return {
                            'db_key': db_key,
                            'org_inn': inn,
                            'org_rn': rn,
                            'org_code': code_var.getvalue(),
                            'org_name': agent_name_var.getvalue(),
                            'company_rn': company_rn_var.getvalue(),
                            'company_name': company_agent_name_var.getvalue(),
                        }
        except cx_Oracle.Error as error:
            logging.error(error)
            continue
    return None


async def find_person_in_org(db_key, org_rn, family, firstname, lastname):
    """Поиск сотрудника в учреждении"""
    pool = db.pool[db_key]
    async with pool.acquire() as connection:
        async with connection.cursor() as cursor:
            person_rn_var = await cursor.var(int)
            await cursor.callproc('UDO_FIND_PERSON_BY_FIO', [org_rn, family, firstname, lastname, person_rn_var])
            return person_rn_var.getvalue()


async def get_groups(db_key, org_rn):
    """Получение списка групп учреждения"""
    pool = db.pool[db_key]
    async with pool.acquire() as connection:
        async with connection.cursor() as cursor:
            groups_var = await cursor.var(str)
            await cursor.callproc('UDO_P_PSORG_GET_GROUPS', [org_rn, groups_var])
            return groups_var.getvalue()


async def receive_timesheet(db_key, org_rn, group, period=datetime.now()):
    """Получение табеля посещаемости группы в файле CSV"""
    pool = db.pool[db_key]
    async with pool.acquire() as connection:
        async with connection.cursor() as cursor:
            file_name_var = await cursor.var(str)
            file_content_var = await cursor.var(cx_Oracle.DB_TYPE_CLOB)
            await cursor.callproc('UDO_P_SEND_TIMESHEET', [org_rn, group, period, file_name_var, file_content_var])
            file_path = temp_file_path(file_name_var.getvalue())
            file_content = file_content_var.getvalue().read()
            with open(file_path, 'wb') as file:
                file.write(encode_cp1251(file_content))
            return file_path


async def send_timesheet(db_key, company_rn, file_path):
    """Отправка табеля посещаемости группы в формате CSV в Парус"""
    pool = db.pool[db_key]
    async with pool.acquire() as connection:
        async with connection.cursor() as cursor:
            # Чтение табеля посещаемости из файла в кодировке cp1251
            with open(file_path, 'rb') as file:
                file_content = decode_cp1251(file.read())
            result_var = await cursor.var(str)
            await cursor.callproc('UDO_P_RECEIVE_TIMESHEET', [company_rn, file_content, result_var])
            await connection.commit()
            return result_var.getvalue()
